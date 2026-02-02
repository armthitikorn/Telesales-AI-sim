import os
import requests
import re
import random
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai

app = Flask(__name__)

# --- [ส่วนที่ 1: ตั้งค่า API Keys] ---
GENAI_API_KEY = os.environ.get("GENAI_API_KEY")
TTS_API_KEY = os.environ.get("TTS_API_KEY")
genai.configure(api_key=GENAI_API_KEY)

# --- [ส่วนที่ 2: ข้อมูลลูกค้า 5 ระดับ] ---
CUSTOMERS = {
    "1": {
        "name": "น้องฟ้า (Level 1)",
        "desc": "วัยทำงาน 25 ปี - สนใจสะสมทรัพย์และลดหย่อนภาษี",
        "prompt": "คุณคือ 'ฟ้า' อายุ 25 เริ่มทำงาน อยากออมเงินและลดหย่อนภาษี พนักงานต้องแนะนำแบบสะสมทรัพย์ให้เห็นภาพความคุ้มค่า คุณจะตกลงง่ายถ้าพนักงานอธิบายเรื่องภาษีชัดเจน ห้ามมีวงเล็บในคำพูด",
        "voice": {"name": "th-TH-Standard-A", "pitch": 3.0, "rate": 1.1} 
    },
    "2": {
        "name": "คุณวิรัช (Level 2)",
        "desc": "วัยสร้างตัว 45 ปี - เน้นความมั่นคงและสุขภาพ",
        "prompt": "คุณคือ 'วิรัช' อายุ 45 อยากได้ความมั่นคงให้ชีวิต สนใจทั้งสุขภาพและเงินออม พนักงานต้องนำเสนออย่างเป็นทางการและครบถ้วนถึงจะยอมรับโครงการ ห้ามมีวงเล็บในคำพูด",
        "voice": {"name": "th-TH-Standard-B", "pitch": -1.0, "rate": 1.0}
    },
    "3": {
        "name": "คุณป้ามาลี (Level 3)",
        "desc": "จอมละเอียด - ถามเยอะ ขี้สงสัย แต่ชอบคำชม",
        "prompt": "คุณคือ 'ป้ามาลี' จุกจิก ถามเก่งมาก พนักงานต้องใจเย็น ตอบคำถามให้ครบ และต้องมีคำชม/การให้เกียรติในบทสนทนา คุณถึงจะซื้อทั้งสุขภาพและออมทรัพย์ ห้ามมีวงเล็บในคำพูด",
        "voice": {"name": "th-TH-Standard-A", "pitch": -2.0, "rate": 0.9}
    },
    "4": {
        "name": "แม่แอน (Level 4)",
        "desc": "คุณแม่ลูกอ่อน - อยากทำประกันให้ลูก (9 ขวบ)",
        "prompt": "คุณคือ 'แอน' อยากทำประกันสุขภาพให้ลูกชายอายุ 9 ขวบ คุณจะฟังพนักงานนำเสนออย่างดี แต่ตอนจบคุณจะปฏิเสธเป็นนิสัย พนักงานต้องใช้การโน้มน้าวเรื่องความเสี่ยงของลูกถึงจะปิดการขายได้ ห้ามมีวงเล็บในคำพูด",
        "voice": {"name": "th-TH-Standard-A", "pitch": 1.0, "rate": 1.0}
    },
    "5": {
        "name": "คุณอัครเดช (Level 5 - BOSS)",
        "desc": "นักธุรกิจใหญ่ - เน้นทุนสูงเท่านั้น (ทุนต่ำไม่คุย)",
        "prompt": "คุณคือ 'อัครเดช' รวยและยุ่งมาก ถ้าพนักงานเสนอทุนประกันน้อยๆ คุณจะวางสายทันที ต้องเสนอทุนสูงสุดและพูดจาน่าเชื่อถือ โน้มน้าวเก่งระดับมือโปรถึงจะปิดการขายได้ ห้ามมีวงเล็บในคำพูด",
        "voice": {"name": "th-TH-Standard-B", "pitch": -3.0, "rate": 0.95}
    }
}

model = genai.GenerativeModel(model_name="gemini-2.5-flash")

def get_audio_base64(text, voice_config):
    if not TTS_API_KEY: return None
    clean_text = re.sub(r'\(.*?\)', '', text)
    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={TTS_API_KEY}"
    payload = {
        "input": {"text": clean_text},
        "voice": {"languageCode": "th-TH", "name": voice_config["name"]},
        "audioConfig": {"audioEncoding": "MP3", "pitch": voice_config["pitch"], "speakingRate": voice_config["rate"]}
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            return response.json().get("audioContent")
        return None
    except:
        return None

# --- [ส่วนที่ 3: UI และ Logic หน้าบ้าน] ---
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
        #lobby { padding: 20px; max-width: 600px; margin: auto; text-align: center; }
        .cust-card { background: white; padding: 15px; margin: 10px 0; border-radius: 12px; cursor: pointer; border-left: 8px solid var(--blue); box-shadow: 0 2px 5px rgba(0,0,0,0.1); text-align: left; transition: 0.2s; }
        .cust-card:hover { transform: scale(1.02); }
        #main-app { display: none; flex-direction: column; height: 100vh; background: white; }
        .header { background: var(--blue); color: white; padding: 15px; text-align: center; border-bottom: 4px solid var(--red); }
        #chat-box { flex: 1; overflow-y: auto; padding: 15px; background: #f8fafc; display: flex; flex-direction: column; gap: 10px; }
        .msg { padding: 10px 15px; border-radius: 15px; max-width: 85%; font-size: 0.95rem; line-height: 1.4; }
        .staff { align-self: flex-end; background: var(--blue); color: white; border-bottom-right-radius: 2px; }
        .customer { align-self: flex-start; background: #e2e8f0; color: #1e293b; border-bottom-left-radius: 2px; }
        .controls { padding: 20px; background: white; border-top: 1px solid #ddd; text-align: center; }
        .btn-mic { width: 70px; height: 70px; border-radius: 50%; border: none; background: var(--red); color: white; font-size: 30px; cursor: pointer; }
        .btn-mic.active { animation: pulse 1s infinite; background: #9f1239; }
        @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(190, 18, 60, 0.7); } 70% { box-shadow: 0 0 0 15px rgba(190, 18, 60, 0); } 100% { box-shadow: 0 0 0 0 rgba(190, 18, 60, 0); } }
        #result-modal { display: none; position: fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.9); z-index: 1000; padding: 20px; box-sizing: border-box; overflow-y: auto; }
        .modal-body { background: white; padding: 25px; border-radius: 15px; max-width: 600px; margin: auto; }
        .cert-frame { border: 10px double var(--gold); padding: 20px; text-align: center; background: #fffcf0; margin-top: 20px; }
    </style>
</head>
<body>
    <div id="lobby">
        <h1 style="color: var(--blue)">🏆 Sales Mastery Academy</h1>
        <p>เลือกด่านเพื่อเริ่มการทดสอบ (ใบเซอร์ฯ อยู่ที่ Level 5)</p>
        <div id="customer-list"></div>
    </div>

    <div id="main-app">
        <div class="header">
            <button onclick="location.reload()" style="float:left; color:white; background:none; border:none; cursor:pointer; font-size: 1.2rem;">⬅️</button>
            <h2 id="active-cust-name" style="margin:0; font-size:1.1rem;">ลูกค้า</h2>
            <div id="status" style="font-size: 0.7rem; opacity: 0.8;">แตะไมค์เพื่อคุย</div>
        </div>
        <div id="chat-box"></div>
        <div class="controls">
            <button id="mic-btn" class="btn-mic" onclick="toggleListen()">🎤</button>
            <button id="eval-btn" style="display:none; margin-top:10px; width:100%; padding:12px; border-radius:25px; border:1px solid var(--blue); color:var(--blue); background:none; cursor:pointer; font-weight:bold;" onclick="showEvaluation()">🏁 จบการสนทนาและประเมิน</button>
        </div>
    </div>

    <div id="result-modal">
        <div class="modal-body">
            <div id="pdf-area">
                <div id="eval-content"></div>
                <div id="cert-area" style="display:none;">
                    <div class="cert-frame">
                        <h2 style="color: var(--gold); margin: 5px 0;">ใบประกาศเกียรติคุณ</h2>
                        <p style="font-size: 0.8rem;">ขอมอบให้พนักงานขายยอดเยี่ยมผู้พิชิตด่านสูงสุด</p>
                        <h1 style="color: var(--blue); font-size: 1.5rem; margin: 10px 0;">MASTER OF TELESALES</h1>
                        <p style="font-size: 0.9rem;"><i>ปิดการขายลูกค้า Level 5 สำเร็จ</i></p>
                    </div>
                </div>
            </div>
            <button onclick="downloadPDF()" style="width:100%; padding:15px; background:var(--blue); color:white; border:none; margin-top:15px; border-radius:8px; cursor:pointer; font-weight:bold;">💾 ดาวน์โหลด PDF</button>
            <button onclick="location.reload()" style="width:100%; padding:10px; background:none; border:none; color:gray; cursor:pointer; margin-top:10px;">กลับหน้าหลัก</button>
        </div>
    </div>

    <script>
        let history = [];
        let activeLevel = "";
        const customers = {{ CUSTOMERS | tojson }};
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        let recognition = new (SpeechRecognition || window.webkitSpeechRecognition)();
        recognition.lang = 'th-TH';

        let audioPlayer = new Audio(); // สร้างตัวเล่นเสียงรอไว้ตัวเดียวเพื่อ iOS

        function unlockAudio() {
            audioPlayer.play().catch(() => {}); // ยืนยันสิทธิ์การเล่นเสียงบน iPhone
        }

        const listDiv = document.getElementById('customer-list');
        Object.keys(customers).forEach(lvl => {
            const c = customers[lvl];
            listDiv.innerHTML += `<div class="cust-card" onclick="startChat('${lvl}')"><b>Level ${lvl}: ${c.name}</b><br><small style="color:#666">${c.desc}</small></div>`;
        });

        function startChat(lvl) {
            activeLevel = lvl;
            document.getElementById('lobby').style.display = 'none';
            document.getElementById('main-app').style.display = 'flex';
            document.getElementById('active-cust-name').innerText = customers[lvl].name;
            unlockAudio();
        }

        recognition.onresult = (e) => sendToAI(e.results[0][0].transcript);
        recognition.onend = () => document.getElementById('mic-btn').classList.remove('active');

        function toggleListen() {
            unlockAudio();
            recognition.start();
            document.getElementById('mic-btn').classList.add('active');
            document.getElementById('status').innerText = "กำลังฟัง...";
        }

        async function sendToAI(text) {
            const chatBox = document.getElementById('chat-box');
            chatBox.innerHTML += `<div class="msg staff"><b>คุณ:</b> ${text}</div>`;
            history.push("พนักงาน: " + text);
            document.getElementById('status').innerText = "ลูกค้ากำลังคิด...";

            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: text, lvl: activeLevel})
            });
            const data = await res.json();
            
            chatBox.innerHTML += `<div class="msg customer"><b>${customers[activeLevel].name}:</b> ${data.reply}</div>`;
            history.push(customers[activeLevel].name + ": " + data.reply);
            chatBox.scrollTop = chatBox.scrollHeight;
            document.getElementById('eval-btn').style.display = 'block';

            if(data.audio) {
                audioPlayer.src = "data:audio/mp3;base64," + data.audio;
                audioPlayer.play();
                document.getElementById('status').innerText = "ลูกค้ากำลังพูด...";
                audioPlayer.onended = () => document.getElementById('status').innerText = "คุยต่อได้เลย";
            }
        }

        async function showEvaluation() {
            document.getElementById('result-modal').style.display = 'block';
            document.getElementById('eval-content').innerText = "กำลังประมวลผลตามกฎ คปภ...";
            const res = await fetch('/api/evaluate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({history: history.join("\\n")})
            });
            const data = await res.json();
            document.getElementById('eval-content').innerHTML = "<h2>📊 ผลการประเมิน</h2>" + data.evaluation.replace(/\\n/g, '<br>');
            if (activeLevel === "5" && data.is_closed) document.getElementById('cert-area').style.display = 'block';
        }

        function downloadPDF() {
            const element = document.getElementById('pdf-area');
            html2pdf().from(element).save('Evaluation_Report.pdf');
        }
    </script>
</body>
</html>
"""

# --- [ส่วนที่ 4: Routes ของ Server] ---
@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE, CUSTOMERS=CUSTOMERS)

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    lvl, user_msg = data.get('lvl'), data.get('message')
    cust = CUSTOMERS[lvl]
    response = model.generate_content(f"System: {cust['prompt']}\\nUser: {user_msg}")
    reply_text = response.text
    audio_data = get_audio_base64(reply_text, cust['voice'])
    return jsonify({"reply": reply_text, "audio": audio_data})

@app.route('/api/evaluate', methods=['POST'])
def evaluate():
    history = request.json.get('history')
    prompt = f"""คุณคือโค้ชสอนการขายประกันทางโทรศัพท์ ประเมินบทสนทนานี้ตามหลักเกณฑ์ดังนี้:
    1. การเปิดตัวตามกฎ คปภ. (ต้องระบุชื่อ-นามสกุลพนักงาน, ชื่อบริษัทประกัน, เลขใบอนุญาต และแจ้งวัตถุประสงค์การโทร)
    2. ทักษะการโน้มน้าวและขจัดข้อโต้แย้งตามระดับความยากของลูกค้า
    3. ความถูกต้องและครบถ้วนของข้อมูลโครงการที่นำเสนอ
    4. สรุปว่า 'ปิดการขายสำเร็จหรือไม่' (ถ้าสำเร็จให้มีคำว่า [CLOSED_SUCCESS] ในคำตอบ)
    ประเมินจากบทสนทนานี้: {history}"""
    evaluation = model.generate_content(prompt).text
    is_closed = "[CLOSED_SUCCESS]" in evaluation
    return jsonify({"evaluation": evaluation, "is_closed": is_closed})

if __name__ == "__main__":
    app.run(debug=True)
