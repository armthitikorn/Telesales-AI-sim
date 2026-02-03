import os
import requests
import re
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai
from datetime import datetime

app = Flask(__name__)

# --- [ส่วนที่ 1: ตั้งค่า API Keys] ---
GENAI_API_KEY = os.environ.get("GENAI_API_KEY")
TTS_API_KEY = os.environ.get("TTS_API_KEY")
genai.configure(api_key=GENAI_API_KEY)

# --- [ส่วนที่ 2: ข้อมูลลูกค้า (Stable Voice A)] ---
CUSTOMERS = {
    "1": {"name": "น้องฟ้า (Level 1)", "desc": "ขี้ระแวง - กลัวมิจฉาชีพ", "prompt": "คุณคือ 'ฟ้า' (ผู้หญิง) อายุ 25 ปี พูดลงท้ายว่า 'ค่ะ' เสมอ ตอบสั้นและระแวง", "voice": {"name": "th-TH-Standard-A", "pitch": 2.0, "rate": 1.0}},
    "2": {"name": "คุณวิรัช (Level 2)", "desc": "สุขุม - เน้นความมั่นคง", "prompt": "คุณคือ 'วิรัช' (ผู้ชาย) อายุ 45 ปี พูดลงท้ายว่า 'ครับ' เสมอ ตอบโต้ด้วยเหตุผล", "voice": {"name": "th-TH-Standard-A", "pitch": -4.0, "rate": 0.95}},
    "3": {"name": "คุณป้ามาลี (Level 3)", "desc": "จอมละเอียด - ถามเยอะ", "prompt": "คุณคือ 'ป้ามาลี' (ผู้หญิง) พูดลงท้ายว่า 'ค่ะ/จ๊ะ' ถามจุกจิกเรื่องเงิน", "voice": {"name": "th-TH-Standard-A", "pitch": -1.5, "rate": 0.9}},
    "4": {"name": "แม่แอน (Level 4)", "desc": "คุณแม่ลูกอ่อน - ห่วงลูก", "prompt": "คุณคือ 'แอน' (ผู้หญิง) พูดลงท้ายว่า 'ค่ะ' กังวลค่าใช้จ่ายเพื่อลูก", "voice": {"name": "th-TH-Standard-A", "pitch": 0.5, "rate": 1.0}},
    "5": {"name": "คุณอัครเดช (Level 5)", "desc": "นักธุรกิจใหญ่ - เวลาน้อย", "prompt": "คุณคือ 'อัครเดช' (ผู้ชาย) พูดลงท้ายว่า 'ครับ' เน้นทุนประกันสูงและเร็ว", "voice": {"name": "th-TH-Standard-A", "pitch": -5.0, "rate": 1.0}}
}

model = genai.GenerativeModel(model_name="gemini-2.5-flash")

def get_audio_base64(text, voice_config):
    if not TTS_API_KEY: return None
    clean_text = re.sub(r'\(.*?\)', '', text).strip()
    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={TTS_API_KEY}"
    payload = {
        "input": {"text": clean_text},
        "voice": {"languageCode": "th-TH", "name": voice_config["name"]},
        "audioConfig": {"audioEncoding": "MP3", "pitch": voice_config["pitch"], "speakingRate": voice_config["rate"]}
    }
    try:
        res = requests.post(url, json=payload)
        return res.json().get("audioContent")
    except: return None

# --- [ส่วนที่ 3: UI พร้อมระบบใบประกาศ] ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Sales Mastery Academy</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <style>
        :root { --blue: #1e3a8a; --red: #be123c; --gold: #b45309; }
        body { font-family: 'Sarabun', sans-serif; background: #f1f5f9; margin:0; }
        #lobby { padding: 20px; text-align: center; }
        .cust-card { background: white; padding: 15px; margin: 10px 0; border-radius: 12px; border-left: 8px solid var(--blue); cursor: pointer; text-align: left; }
        #main-app { display: none; flex-direction: column; height: 100vh; background: white; }
        .header { background: var(--blue); color: white; padding: 15px; text-align: center; }
        #chat-box { flex: 1; overflow-y: auto; padding: 15px; display: flex; flex-direction: column; gap: 10px; background: #f8fafc; }
        .msg { padding: 10px 15px; border-radius: 15px; max-width: 85%; }
        .staff { align-self: flex-end; background: var(--blue); color: white; }
        .customer { align-self: flex-start; background: #e2e8f0; }
        .controls { padding: 20px; text-align: center; background: white; border-top: 1px solid #ddd; }
        .btn-mic { width: 80px; height: 80px; border-radius: 50%; border: none; background: var(--red); color: white; font-size: 35px; cursor: pointer; }
        
        /* สไตล์ใบประกาศ */
        #cert-area { display:none; }
        .certificate { 
            width: 800px; height: 550px; padding: 40px; border: 15px double var(--gold); 
            background: white; position: relative; text-align: center; color: #333; margin: auto;
        }
        .cert-header { color: var(--blue); font-size: 40px; font-weight: bold; margin-bottom: 10px; }
        .cert-body { font-size: 22px; margin-top: 20px; }
        .cert-name { font-size: 35px; color: var(--red); text-decoration: underline; margin: 20px 0; display: block; }
        .cert-seal { position: absolute; bottom: 40px; right: 40px; width: 120px; opacity: 0.8; }
        
        #result-modal { display: none; position: fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.9); z-index: 1000; padding: 20px; overflow-y: auto; }
        .modal-body { background: white; padding: 25px; border-radius: 15px; max-width: 600px; margin: auto; }
    </style>
</head>
<body>
    <div id="lobby">
        <h1 style="color: var(--blue)">🏅 Sales Mastery Academy</h1>
        <div id="customer-list"></div>
    </div>

    <div id="main-app">
        <div class="header">
            <button onclick="location.reload()" style="float:left; color:white; background:none; border:none;">⬅️</button>
            <h2 id="active-cust-name" style="margin:0;">ลูกค้า</h2>
            <div id="status" style="font-size: 0.8rem;">แตะไมค์เพื่อเริ่มคุย</div>
        </div>
        <div id="chat-box"></div>
        <div class="controls">
            <button id="mic-btn" class="btn-mic" onclick="toggleListen()">🎤</button>
            <button id="eval-btn" style="display:none; width:100%; margin-top:15px; padding:12px; border-radius:25px; border:1px solid var(--blue); background:none; color:var(--blue);" onclick="showEvaluation()">🏁 จบการสนทนาและประเมินผล</button>
        </div>
    </div>

    <div id="result-modal">
        <div class="modal-body">
            <div id="eval-content"></div>
            <button id="download-cert-btn" style="display:none; width:100%; margin-top:15px; padding:15px; background:var(--gold); color:white; border:none; border-radius:8px; font-weight:bold; cursor:pointer;" onclick="generatePDF()">📜 รับใบประกาศนียบัตร (Level <span id="cert-lvl"></span>)</button>
            <button onclick="location.reload()" style="width:100%; padding:10px; background:var(--blue); color:white; border:none; border-radius:8px; margin-top:10px;">กลับหน้าหลัก</button>
        </div>
    </div>

    <div id="cert-area">
        <div id="certificate" class="certificate">
            <div class="cert-header">CERTIFICATE OF ACHIEVEMENT</div>
            <p class="cert-body">ขอรับรองว่าท่านได้ผ่านการทดสอบจำลองการขายประกันภัย</p>
            <p class="cert-body" style="font-weight:bold;">ระดับความยาก: <span id="pdf-level"></span></p>
            <span class="cert-name">พนักงานผู้ทรงเกียรติ</span>
            <p class="cert-body">ท่านได้แสดงทักษะการรับมือและโน้มน้าวใจลูกค้า <br> ตามมาตรฐาน Sales Mastery Academy</p>
            <p style="margin-top:40px;">ออกให้ ณ วันที่: <span id="cert-date"></span></p>
            <div class="cert-seal"><img src="https://cdn-icons-png.flaticon.com/512/190/190411.png" width="100"></div>
        </div>
    </div>

    <script>
        let history = [];
        let activeLevel = "";
        let isProcessing = false;
        const customers = {{ CUSTOMERS | tojson | safe }};
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        let recognition = new SpeechRecognition();
        recognition.lang = 'th-TH';

        let audioPlayer = new Audio();

        Object.keys(customers).forEach(lvl => {
            document.getElementById('customer-list').innerHTML += `<div class="cust-card" onclick="startChat('${lvl}')"><b>Level ${lvl}: ${customers[lvl].name}</b><br><small>${customers[lvl].desc}</small></div>`;
        });

        function startChat(lvl) {
            activeLevel = lvl;
            document.getElementById('lobby').style.display = 'none';
            document.getElementById('main-app').style.display = 'flex';
            document.getElementById('active-cust-name').innerText = customers[lvl].name;
            unlockAudio();
        }

        recognition.onresult = (e) => {
            const text = e.results[0][0].transcript;
            if (text.length > 1 && !isProcessing) { sendToAI(text); }
        };

        recognition.onend = () => document.getElementById('mic-btn').classList.remove('active');

        function toggleListen() {
            if (isProcessing) return;
            unlockAudio();
            audioPlayer.pause();
            recognition.start();
            document.getElementById('mic-btn').classList.add('active');
            document.getElementById('status').innerText = "👂 กำลังฟัง...";
        }

        async function sendToAI(text) {
            isProcessing = true;
            document.getElementById('mic-btn').disabled = true;
            const chatBox = document.getElementById('chat-box');
            chatBox.innerHTML += `<div class="msg staff"><b>คุณ:</b> $\{text}</div>`;
            history.push("พนักงาน: " + text);
            chatBox.scrollTop = chatBox.scrollHeight;

            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: text, lvl: activeLevel, history: history})
                });
                const data = await res.json();
                chatBox.innerHTML += `<div class="msg customer"><b>$\{customers[activeLevel].name}:</b> $\{data.reply}</div>`;
                history.push(customers[activeLevel].name + ": " + data.reply);
                chatBox.scrollTop = chatBox.scrollHeight;

                if (data.audio) {
                    audioPlayer.src = "data:audio/mp3;base64," + data.audio;
                    await audioPlayer.play();
                    audioPlayer.onended = () => { resetUI(); };
                } else { resetUI(); }
            } catch (e) { resetUI(); }
        }

        function resetUI() {
            isProcessing = false;
            document.getElementById('mic-btn').disabled = false;
            document.getElementById('status').innerText = "✅ คุยต่อได้เลย";
            document.getElementById('eval-btn').style.display = 'block';
        }

        async function showEvaluation() {
            document.getElementById('result-modal').style.display = 'block';
            document.getElementById('eval-content').innerText = "⌛ กำลังวิเคราะห์ผล...";
            const res = await fetch('/api/evaluate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({history: history.join("\\n")})
            });
            const data = await res.json();
            document.getElementById('eval-content').innerHTML = "<h2>📊 ผลการทดสอบ</h2>" + data.evaluation.replace(/\\n/g, '<br>');
            
            // ถ้าผ่าน (จำลองว่าผ่านเสมอเพื่อทดสอบ) ให้โชว์ปุ่มรับใบประกาศ
            document.getElementById('download-cert-btn').style.display = 'block';
            document.getElementById('cert-lvl').innerText = activeLevel;
        }

        function generatePDF() {
            const element = document.getElementById('certificate');
            document.getElementById('pdf-level').innerText = customers[activeLevel].name;
            document.getElementById('cert-date').innerText = new Date().toLocaleDateString('th-TH');
            
            // ตั้งค่า PDF
            const opt = {
                margin: 0,
                filename: `Certificate_Level_$\{activeLevel}.pdf`,
                image: { type: 'jpeg', quality: 0.98 },
                html2canvas: { scale: 2 },
                jsPDF: { unit: 'in', format: 'letter', orientation: 'landscape' }
            };
            
            document.getElementById('cert-area').style.display = 'block';
            html2pdf().set(opt).from(element).save().then(() => {
                document.getElementById('cert-area').style.display = 'none';
            });
        }

        function unlockAudio() {
            const silent = new Audio("data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=");
            silent.play().catch(e => {});
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE, CUSTOMERS=CUSTOMERS)

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    lvl, user_msg, history = data.get('lvl'), data.get('message'), data.get('history', [])
    cust = CUSTOMERS[lvl]
    context = "\\n".join(history[-6:])
    full_prompt = f"System: {cust['prompt']}\\n\\nHistory:\\n{context}\\nUser: {user_msg}"
    response = model.generate_content(full_prompt)
    reply_text = response.text
    audio_data = get_audio_base64(reply_text, cust['voice'])
    return jsonify({"reply": reply_text, "audio": audio_data})

@app.route('/api/evaluate', methods=['POST'])
def evaluate():
    history = request.json.get('history')
    prompt = f"ประเมินบทสนทนานี้และให้คะแนน 1-10 พร้อมคำแนะนำสั้นๆ: {history}"
    evaluation = model.generate_content(prompt).text
    return jsonify({"evaluation": evaluation})

if __name__ == "__main__":
    app.run(debug=True)
