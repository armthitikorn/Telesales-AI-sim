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

# --- [ส่วนที่ 2: ข้อมูลลูกค้า (เน้นย้ำลำดับการคุย)] ---
CUSTOMERS = {
    "1": {
        "name": "น้องฟ้า (Level 1 - The Trust Master)",
        "desc": "วัยทำงาน 25 ปี - กลัวมิจฉาชีพและไม่ยอมให้ข้อมูลส่วนตัว",
        "prompt": "คุณคือ 'ฟ้า' ลูกค้าขี้ระแวง ห้ามพูดก่อนพนักงานทักเด็ดขาด และห้ามพูดซ้ำเรื่องเดิมที่คุยไปแล้วใน History",
        "voice": {"name": "th-TH-Standard-A", "pitch": 2.5, "rate": 1.05} 
    },
    "2": {"name": "คุณวิรัช (Level 2)", "desc": "วัยสร้างตัว 45 ปี", "prompt": "คุณคือวิรัช เน้นความมั่นคง", "voice": {"name": "th-TH-Standard-B", "pitch": -1.0, "rate": 1.0}},
    "3": {"name": "คุณป้ามาลี (Level 3)", "desc": "จอมละเอียด", "prompt": "คุณคือป้ามาลี ถามเก่ง", "voice": {"name": "th-TH-Standard-A", "pitch": -2.0, "rate": 0.9}},
    "4": {"name": "แม่แอน (Level 4)", "desc": "ทำประกันให้ลูก", "prompt": "คุณคือแอน อยากทำประกันให้ลูก", "voice": {"name": "th-TH-Standard-A", "pitch": 1.0, "rate": 1.0}},
    "5": {"name": "คุณอัครเดช (Level 5)", "desc": "นักธุรกิจใหญ่", "prompt": "คุณคืออัครเดช เน้นทุนสูง", "voice": {"name": "th-TH-Standard-B", "pitch": -3.0, "rate": 0.95}}
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
        return response.json().get("audioContent")
    except: return None

# --- [ส่วนที่ 3: UI ที่เน้นระบบล็อกไมค์แบบเด็ดขาด] ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Sales Mastery Academy</title>
    <style>
        :root { --blue: #1e3a8a; --red: #be123c; --gray: #94a3b8; }
        body { font-family: 'Sarabun', sans-serif; background: #f1f5f9; margin:0; touch-action: manipulation; }
        #lobby { padding: 20px; max-width: 600px; margin: auto; text-align: center; }
        .cust-card { background: white; padding: 15px; margin: 10px 0; border-radius: 12px; border-left: 8px solid var(--blue); text-align: left; cursor: pointer; }
        #main-app { display: none; flex-direction: column; height: 100vh; background: white; }
        .header { background: var(--blue); color: white; padding: 15px; text-align: center; }
        #chat-box { flex: 1; overflow-y: auto; padding: 15px; display: flex; flex-direction: column; gap: 10px; background: #f8fafc; }
        .msg { padding: 10px 15px; border-radius: 15px; max-width: 80%; font-size: 0.95rem; }
        .staff { align-self: flex-end; background: var(--blue); color: white; }
        .customer { align-self: flex-start; background: #e2e8f0; }
        .controls { padding: 25px; background: white; border-top: 1px solid #ddd; text-align: center; }
        .btn-mic { width: 80px; height: 80px; border-radius: 50%; border: none; background: var(--red); color: white; font-size: 35px; cursor: pointer; transition: 0.3s; box-shadow: 0 4px 10px rgba(0,0,0,0.2); }
        .btn-mic:disabled { background: var(--gray); transform: scale(0.9); opacity: 0.6; }
        .btn-mic.active { animation: pulse 1s infinite; background: #9f1239; }
        @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(190, 18, 60, 0.7); } 70% { box-shadow: 0 0 0 20px rgba(190, 18, 60, 0); } 100% { box-shadow: 0 0 0 0 rgba(190, 18, 60, 0); } }
    </style>
</head>
<body>
    <div id="lobby">
        <h1 style="color: var(--blue)">🏆 Sales Mastery</h1>
        <div id="customer-list"></div>
    </div>

    <div id="main-app">
        <div class="header">
            <button onclick="location.reload()" style="float:left; color:white; background:none; border:none;">⬅️</button>
            <h2 id="active-cust-name" style="margin:0;">ลูกค้า</h2>
            <div id="status" style="font-size: 0.8rem; margin-top:5px;">รอการสนทนา...</div>
        </div>
        <div id="chat-box"></div>
        <div class="controls">
            <button id="mic-btn" class="btn-mic" onclick="toggleListen()">🎤</button>
            <p id="hint" style="font-size: 0.7rem; color: #666; margin-top: 10px;">แตะหนึ่งครั้งเพื่อพูด</p>
            <button id="eval-btn" style="display:none; width:100%; margin-top:10px; padding:10px; border-radius:20px; border:1px solid var(--blue); background:none; color:var(--blue);" onclick="showEvaluation()">🏁 จบและประเมินผล</button>
        </div>
    </div>

    <script>
        let history = [];
        let activeLevel = "";
        let isLocked = false;
        const customers = {{ CUSTOMERS | tojson | safe }};
        
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        let recognition = new SpeechRecognition();
        recognition.lang = 'th-TH';
        recognition.continuous = false; // ฟังแค่ประโยคเดียวแล้วหยุดทันที
        recognition.interimResults = false;

        let audioPlayer = new Audio();

        // แสดงรายชื่อลูกค้า
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

        // --- ระบบล็อกไมค์เด็ดขาด ---
        recognition.onresult = (e) => {
            const text = e.results[0][0].transcript.trim();
            recognition.abort(); // ตัดไฟไมค์ทันทีที่ได้ยินเสียง!
            if (text.length > 1) {
                sendToAI(text);
            } else {
                resetMicUI();
            }
        };

        recognition.onend = () => {
            document.getElementById('mic-btn').classList.remove('active');
        };

        function toggleListen() {
            if (isLocked) return;
            
            // ล้างค่าเก่าและหยุดเสียงลูกค้าก่อนเริ่มฟัง
            audioPlayer.pause();
            audioPlayer.currentTime = 0;
            try { recognition.abort(); } catch(e) {}

            unlockAudio();
            
            // หน่วงเวลาเล็กน้อยเพื่อให้เบราว์เซอร์ล้าง Echo เก่า (Mobile Fix)
            setTimeout(() => {
                recognition.start();
                document.getElementById('mic-btn').classList.add('active');
                document.getElementById('status').innerText = "👂 กำลังฟังคุณ...";
            }, 300);
        }

        async function sendToAI(text) {
            isLocked = true; // ล็อกปุ่มทันที
            const micBtn = document.getElementById('mic-btn');
            micBtn.disabled = true;

            const chatBox = document.getElementById('chat-box');
            chatBox.innerHTML += `<div class="msg staff"><b>คุณ:</b> ${text}</div>`;
            history.push("พนักงาน: " + text);
            chatBox.scrollTop = chatBox.scrollHeight;

            document.getElementById('status').innerText = "⌛ ลูกค้ากำลังคิด...";

            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: text, lvl: activeLevel, history: history})
                });
                const data = await res.json();
                
                chatBox.innerHTML += `<div class="msg customer"><b>${customers[activeLevel].name}:</b> ${data.reply}</div>`;
                history.push(customers[activeLevel].name + ": " + data.reply);
                chatBox.scrollTop = chatBox.scrollHeight;

                if (data.audio) {
                    audioPlayer.src = "data:audio/mp3;base64," + data.audio;
                    await audioPlayer.play();
                    document.getElementById('status').innerText = "🔈 ลูกค้ากำลังพูด...";
                    
                    // ปลดล็อกเมื่อลูกค้าพูดจบเท่านั้น!
                    audioPlayer.onended = () => { resetMicUI(); };
                } else {
                    resetMicUI();
                }
            } catch (e) { resetMicUI(); }
        }

        function resetMicUI() {
            isLocked = false;
            const micBtn = document.getElementById('mic-btn');
            micBtn.disabled = false;
            document.getElementById('status').innerText = "✅ คุยต่อได้เลย";
            document.getElementById('eval-btn').style.display = 'block';
        }

        function unlockAudio() {
            const silent = new Audio("data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=");
            silent.play().catch(() => {});
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
    lvl, user_msg = data.get('lvl'), data.get('message')
    history = data.get('history', [])
    cust = CUSTOMERS[lvl]
    context = "\\n".join(history[-6:])
    full_prompt = f"System: {cust['prompt']}\\n\\nHistory:\\n{context}\\nUser: {user_msg}"
    response = model.generate_content(full_prompt)
    reply_text = response.text
    audio_data = get_audio_base64(reply_text, cust['voice'])
    return jsonify({"reply": reply_text, "audio": audio_data})

if __name__ == "__main__":
    app.run(debug=True)
