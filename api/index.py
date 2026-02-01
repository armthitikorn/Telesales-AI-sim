import os
import requests
import re
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai

app = Flask(__name__)

# --- [ส่วนที่ 1: ตั้งค่า API Keys] ---
GENAI_API_KEY = os.environ.get("GENAI_API_KEY")
TTS_API_KEY = os.environ.get("TTS_API_KEY")
genai.configure(api_key=GENAI_API_KEY)

# --- [ส่วนที่ 2: ข้อมูลลูกค้า 5 ระดับ พร้อมตั้งค่าเสียง] ---
CUSTOMERS = {
    "1": {
        "name": "น้องสุดา (Level 1)",
        "desc": "เด็กจบใหม่ - เปิดใจง่าย สนใจประกันเล่มแรก",
        "prompt": "คุณคือสุดา อายุ 23 เพิ่งทำงาน สดใส เป็นกันเอง สนใจประกันอุบัติเหตุและสุขภาพเบี้ยต่ำ ตกลงง่ายถ้าพนักงานพูดจาสุภาพ ห้ามมีวงเล็บในคำพูด",
        "voice": {"name": "th-TH-Standard-A", "pitch": 4.0, "rate": 1.1} # เสียงผู้หญิง สูง สดใส
    },
    "2": {
        "name": "คุณสมชาย (Level 2)",
        "desc": "คุณลุงใจดี - ขี้เหงา ชวนคุยนอกเรื่องเก่ง",
        "prompt": "คุณคือคุณลุงสมชาย อายุ 65 ใจดี ชอบเล่าเรื่องอดีต พนักงานต้องนิ่งและดึงกลับมาเรื่องขายให้ได้ถึงจะตกลงทำเพื่อหลาน ห้ามมีวงเล็บในคำพูด",
        "voice": {"name": "th-TH-Standard-B", "pitch": -3.0, "rate": 0.9} # เสียงผู้ชาย ทุ้ม ช้า แบบคนแก่
    },
    "3": {
        "name": "คุณกัญญา (Level 3)",
        "desc": "พนักงานออฟฟิศ - เน้นตัวเลขและความคุ้มค่า",
        "prompt": "คุณคือกัญญา อายุ 30 เนี้ยบ ถามเรื่อง IRR และความคุ้มครองละเอียด ถ้าตอบไม่ชัดเจนจะเริ่มรำคาญ ห้ามมีวงเล็บในคำพูด",
        "voice": {"name": "th-TH-Standard-A", "pitch": 0.0, "rate": 1.0} # เสียงผู้หญิง ปกติ มั่นใจ
    },
    "4": {
        "name": "คุณประเสริฐ (Level 4)",
        "desc": "เจ้าของอู่ - โผงผาง ไม่เชื่อใจประกัน",
        "prompt": "คุณคือประเสริฐ อายุ 50 ดุ พูดเสียงดัง เคยมีประสบการณ์เคลมยาก พนักงานต้องใช้ความจริงใจอย่างมากถึงจะยอม ห้ามมีวงเล็บในคำพูด",
        "voice": {"name": "th-TH-Standard-B", "pitch": -2.0, "rate": 1.0} # เสียงผู้ชาย เข้มแข็ง
    },
    "5": {
        "name": "คุณวีณา (Level 5 - Boss)",
        "desc": "นักธุรกิจหญิง - ยากที่สุด! ยุ่งตลอดเวลา และต้องถามสามี",
        "prompt": "คุณคือวีณา อายุ 40 ใจแข็งมาก ปฏิเสธว่าติดประชุมตลอด พนักงานต้องใช้จิตวิทยาขั้นสูง และจบด้วยการขอไปปรึกษาสามี พนักงานต้องแก้จุดนี้ให้ได้ถึงจะปิดการขายสำเร็จ ห้ามมีวงเล็บในคำพูด",
        "voice": {"name": "th-TH-Standard-A", "pitch": -1.5, "rate": 0.95} # เสียงผู้หญิง สุขุม น่าเกรงขาม
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
        "audioConfig": {
            "audioEncoding": "MP3",
            "pitch": voice_config["pitch"],
            "speakingRate": voice_config["rate"]
        }
    }
    try:
        response = requests.post(url, json=payload)
        return response.json().get("audioContent") if response.status_code == 200 else None
    except: return None

# --- [ส่วนที่ 4: หน้าเว็บ Interface (Lobby + Chat)] ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sales Mastery Simulator</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;600&display=swap" rel="stylesheet">
    <style>
        :root { --blue: #1e3a8a; --red: #be123c; --gold: #b45309; --gray: #f1f5f9; }
        body { font-family: 'Sarabun', sans-serif; background: #cbd5e1; margin:0; }
        
        /* Lobby Style */
        #lobby { padding: 20px; max-width: 600px; margin: auto; text-align: center; }
        .cust-card { background: white; padding: 15px; margin: 10px 0; border-radius: 12px; cursor: pointer; border-left: 8px solid var(--blue); transition: 0.3s; display: flex; align-items: center; justify-content: space-between; }
        .cust-card:hover { transform: translateX(10px); background: #f8fafc; }
        .lvl-badge { background: var(--red); color: white; padding: 5px 10px; border-radius: 20px; font-size: 0.7rem; }
        .locked { filter: grayscale(1); opacity: 0.6; }

        /* Chat Style */
        #main-app { display: none; max-width: 500px; margin: auto; background: white; height: 100vh; display: none; flex-direction: column; }
        .header { background: var(--blue); color: white; padding: 15px; text-align: center; border-bottom: 4px solid var(--red); }
        #chat-box { flex: 1; overflow-y: auto; padding: 15px; background: #f8fafc; display: flex; flex-direction: column; gap: 10px; }
        .msg { padding: 10px 15px; border-radius: 15px; max-width: 85%; line-height: 1.4; font-size: 0.95rem; }
        .staff { align-self: flex-end; background: var(--blue); color: white; border-bottom-right-radius: 2px; }
        .customer { align-self: flex-start; background: white; color: #1e293b; border-bottom-left-radius: 2px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .controls { padding: 20px; background: white; border-top: 1px solid #e2e8f0; display: flex; flex-direction: column; align-items: center; gap: 10px; }
        .btn-mic { width: 70px; height: 70px; border-radius: 50%; border: none; background: var(--red); color: white; font-size: 30px; cursor: pointer; box-shadow: 0 4px 12px rgba(190, 18, 60, 0.4); }
        .btn-mic.active { animation: pulse 1s infinite; background: #9f1239; }
        @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(190, 18, 60, 0.7); } 70% { box-shadow: 0 0 0 15px rgba(190, 18, 60, 0); } 100% { box-shadow: 0 0 0 0 rgba(190, 18, 60, 0); } }

        /* Certificate / Evaluation Modal */
        #result-modal { display: none; position: fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.9); z-index: 1000; padding: 20px; box-sizing: border-box; overflow-y: auto; }
        .modal-body { background: white; padding: 30px; border-radius: 15px; max-width: 600px; margin: auto; }
        .cert-frame { border: 15px double var(--gold); padding: 30px; text-align: center; background: #fffcf0; position: relative; }
    </style>
</head>
<body>

    <div id="lobby">
        <h1 style="color: var(--blue)">🏆 Sales Mastery Academy</h1>
        <p>เลือกด่านของคุณเพื่อเริ่มการฝึกฝน</p>
        <div id="customer-list"></div>
    </div>

    <div id="main-app">
        <div class="header">
            <button onclick="location.reload()" style="float:left; background:none; border:none; color:white; cursor:pointer;">⬅️ ออก</button>
            <h2 id="active-cust-name">ลูกค้า</h2>
            <div id="status">แตะไมค์เพื่อคุย</div>
        </div>
        <div id="chat-box"></div>
        <div class="controls">
            <button id="mic-btn" class="btn-mic" onclick="toggleListen()">🎤</button>
            <button id="eval-btn" style="display:none; width:100%; padding:10px; border-radius:20px; border:1px solid var(--blue); color:var(--blue); background:none; cursor:pointer;" onclick="showEvaluation()">🏁 จบการสนทนาและประเมิน</button>
        </div>
    </div>

    <div id="result-modal">
        <div class="modal-body">
            <div id="pdf-area">
                <div id="eval-content"></div>
                <div id="cert-area" style="display:none; margin-top:20px;">
                    <div class="cert-frame">
                        <p style="font-size: 0.8rem; letter-spacing: 2px;">CERTIFICATE OF EXCELLENCE</p>
                        <h1 style="color: var(--gold); margin: 10px 0;">ยอดนักขายระดับตำนาน</h1>
                        <p>ขอมอบให้พนักงานผู้ทรงเกียรติที่พิชิต</p>
                        <h2 style="color: var(--blue);">ด่านที่ 5 : คุณวีณา</h2>
                        <p>ด้วยทักษะการโน้มน้าวและขจัดข้อโต้แย้งระดับสูง</p>
                        <p style="font-size: 0.8rem; margin-top: 30px;"><i>ได้รับเมื่อวันที่ 1 กุมภาพันธ์ 2026</i></p>
                    </div>
                </div>
            </div>
            <button onclick="downloadPDF()" style="width:100%; padding:15px; background:var(--blue); color:white; border:none; border-radius:8px; margin-top:15px; cursor:pointer;">💾 ดาวน์โหลดผลประเมิน (PDF)</button>
            <button onclick="location.reload()" style="width:100%; padding:10px; background:none; border:none; color:gray; cursor:pointer;">กลับหน้าหลัก</button>
        </div>
    </div>

    <script>
        let history = [];
        let activeLevel = "";
        const customers = {{ CUSTOMERS | tojson }};
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        let recognition = new SpeechRecognition();
        recognition.lang = 'th-TH';

        // สร้างรายการลูกค้าใน Lobby
        const listDiv = document.getElementById('customer-list');
        Object.keys(customers).forEach(lvl => {
            const c = customers[lvl];
            listDiv.innerHTML += `
                <div class="cust-card" onclick="startChat('${lvl}')">
                    <div style="text-align:left">
                        <span class="lvl-badge">Level ${lvl}</span>
                        <div style="font-weight:600; margin-top:5px;">${c.name}</div>
                        <div style="font-size:0.75rem; color:gray;">${c.desc}</div>
                    </div>
                    <div>➡️</div>
                </div>
            `;
        });

        function startChat(lvl) {
            activeLevel = lvl;
            document.getElementById('lobby').style.display = 'none';
            document.getElementById('main-app').style.display = 'flex';
            document.getElementById('active-cust-name').innerText = customers[lvl].name;
        }

        recognition.onresult = (e) => sendToAI(e.results[0][0].transcript);
        recognition.onend = () => document.getElementById('mic-btn').classList.remove('active');

        function toggleListen() {
            recognition.start();
            document.getElementById('mic-btn').classList.add('active');
            document.getElementById('status').innerText = "กำลังฟัง...";
        }

        async function sendToAI(text) {
            const chatBox = document.getElementById('chat-box');
            chatBox.innerHTML += `<div class="msg staff"><b>คุณ:</b> ${text}</div>`;
            history.push("พนักงาน: " + text);

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
                const audio = new Audio("data:audio/mp3;base64," + data.audio);
                audio.play();
                document.getElementById('status').innerText = "ลูกค้ากำลังพูด...";
                audio.onended = () => document.getElementById('status').innerText = "คุยต่อได้เลย";
            }
        }

        async function showEvaluation() {
            document.getElementById('result-modal').style.display = 'block';
            document.getElementById('eval-content').innerText = "กำลังตรวจคะแนน...";
            
            const res = await fetch('/api/evaluate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({history: history.join("\\n")})
            });
            const data = await res.json();
            document.getElementById('eval-content').innerHTML = "<h2>📊 ผลการประเมิน</h2>" + data.evaluation.replace(/\\n/g, '<br>');
            
            // ใบเซอร์จะออกเฉพาะเมื่อชนะ Level 5
            if (activeLevel === "5" && data.is_closed) {
                document.getElementById('cert-area').style.display = 'block';
            }
        }

        function downloadPDF() {
            const element = document.getElementById('pdf-area');
            html2pdf().from(element).save('Sales_Master_Report.pdf');
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
    lvl = data.get('lvl')
    user_msg = data.get('message')
    cust = CUSTOMERS[lvl]
    
    response = model.generate_content(f"System: {cust['prompt']}\\nUser: {user_msg}")
    reply_text = response.text
    audio_data = get_audio_base64(reply_text, cust['voice'])
    return jsonify({"reply": reply_text, "audio": audio_data})

@app.route('/api/evaluate', methods=['POST'])
def evaluate():
    history = request.json.get('history')
    prompt = f"คุณคือโค้ชสอนการขายชั้นครู ประเมินบทสนทนาอย่างละเอียด 1-10 คะแนน และสรุปว่า 'ปิดการขายสำเร็จหรือไม่' ถ้าสำเร็จให้ตอบคำว่า [CLOSED_SUCCESS] ไว้ด้วย: {history}"
    evaluation = model.generate_content(prompt).text
    is_closed = "[CLOSED_SUCCESS]" in evaluation
    return jsonify({"evaluation": evaluation, "is_closed": is_closed})

if __name__ == "__main__":
    app.run(debug=True)
