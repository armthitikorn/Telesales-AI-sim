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

# --- [ส่วนที่ 2: ข้อมูลลูกค้า (ปรับจูนเสียงผู้ชายใหม่)] ---
CUSTOMERS = {
    "1": {
        "name": "น้องฟ้า (Level 1)",
        "desc": "วัยทำงาน 25 ปี - ขี้ระแวงและกลัวมิจฉาชีพ",
        "prompt": "คุณคือ 'ฟ้า' (ผู้หญิง) อายุ 25 ปี ต้องพูดลงท้ายว่า 'ค่ะ' เสมอ คุณกังวลเรื่องแก๊งคอลเซ็นเตอร์มาก ตอบสั้นๆ ไม่เกิน 2 ประโยค ห้ามขายของเอง",
        "voice": {"name": "th-TH-Standard-A", "pitch": 0.0, "rate": 1.0} 
    },
    "2": {
        "name": "คุณวิรัช (Level 2)",
        "desc": "วัยสร้างตัว 45 ปี - เน้นความทางการและความมั่นคง",
        "prompt": "คุณคือ 'วิรัช' (ผู้ชาย) อายุ 45 ปี เป็นคนสุขุม ต้องพูดลงท้ายว่า 'ครับ' เสมอ คุณจะรอฟังพนักงานนำเสนอข้อมูลที่น่าเชื่อถือเท่านั้น ถ้าพนักงานพูดจาไม่สุภาพคุณจะตำหนิทันที ตอบโต้ทุกครั้งที่พนักงานพูดมา ห้ามเงียบเด็ดขาด",
        "voice": {"name": "th-TH-Standard-B", "pitch": 0.0, "rate": 1.0}
    },
    "3": {
        "name": "คุณป้ามาลี (Level 3)",
        "desc": "จอมละเอียด - ถามเยอะ ขี้สงสัย แต่ชอบคนปากหวาน",
        "prompt": "คุณคือ 'ป้ามาลี' (ผู้หญิง) เป็นป้าที่ช่างถาม ต้องพูดลงท้ายว่า 'ค่ะ' หรือ 'จ๊ะ' คุณจะถามรายละเอียดจุกจิก พนักงานต้องใจเย็นและชมคุณบ่อยๆ",
        "voice": {"name": "th-TH-Standard-A", "pitch": -2.0, "rate": 0.9}
    },
    "4": {
        "name": "แม่แอน (Level 4)",
        "desc": "คุณแม่ลูกอ่อน - อยากทำประกันสุขภาพให้ลูก 9 ขวบ",
        "prompt": "คุณคือ 'แอน' (ผู้หญิง) ห่วงลูกมาก ต้องพูดลงท้ายว่า 'ค่ะ' คุณกังวลเรื่องค่าใช้จ่าย พนักงานต้องโน้มน้าวเรื่องความปลอดภัยของลูกคุณถึงจะยอมฟัง",
        "voice": {"name": "th-TH-Standard-A", "pitch": 0.0, "rate": 1.0}
    },
    "5": {
        "name": "คุณอัครเดช (Level 5)",
        "desc": "นักธุรกิจใหญ่ - เวลาน้อย เน้นทุนประกันสูง",
        "prompt": "คุณคือ 'อัครเดช' (ผู้ชาย) นักธุรกิจรวยมาก ต้องพูดลงท้ายว่า 'ครับ' คุณไม่ชอบฟังคำเกริ่นนำ ถ้าพนักงานไม่เข้าเรื่องทุนประกันสูงๆ หรือความคุ้มค่าระดับพรีเมียม คุณจะวางสายทันที ตอบโต้สั้นๆ และทรงพลัง",
        "voice": {"name": "th-TH-Standard-B", "pitch": 0.0, "rate": 1.0}
    }
}

model = genai.GenerativeModel(model_name="gemini-2.5-flash")

def get_audio_base64(text, voice_config):
    if not TTS_API_KEY: return None
    # ลบข้อความในวงเล็บออกก่อนส่งไปสร้างเสียง
    clean_text = re.sub(r'\(.*?\)', '', text).strip()
    if not clean_text: return None
    
    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={TTS_API_KEY}"
    payload = {
        "input": {"text": clean_text},
        "voice": {"languageCode": "th-TH", "name": voice_config["name"]},
        "audioConfig": {"audioEncoding": "MP3", "pitch": voice_config["pitch"], "speakingRate": voice_config["rate"]}
    }
    try:
        response = requests.post(url, json=payload)
        return response.json().get("audioContent") if response.status_code == 200 else None
    except: return None

# --- [ส่วนที่ 3: UI ระบบอัตโนมัติ] ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Sales Mastery</title>
    <style>
        :root { --blue: #1e3a8a; --red: #be123c; }
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
        .btn-mic:disabled { background: #ccc; }
        .btn-mic.active { animation: pulse 1s infinite; }
        @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(190, 18, 60, 0.7); } 70% { box-shadow: 0 0 0 20px rgba(190, 18, 60, 0); } 100% { box-shadow: 0 0 0 0 rgba(190, 18, 60, 0); } }
    </style>
</head>
<body>
    <div id="lobby">
        <h1 style="color: var(--blue)">🏆 Sales Mastery Academy</h1>
        <div id="customer-list"></div>
    </div>

    <div id="main-app">
        <div class="header">
            <button onclick="location.reload()" style="float:left; color:white; background:none; border:none; padding:10px;">⬅️</button>
            <h2 id="active-cust-name" style="margin:0;">ลูกค้า</h2>
            <div id="status" style="font-size: 0.8rem;">แตะไมค์เพื่อคุย</div>
        </div>
        <div id="chat-box"></div>
        <div class="controls">
            <button id="mic-btn" class="btn-mic" onclick="toggleListen()">🎤</button>
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
        recognition.continuous = false;

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
            if (text.length > 1 && !isProcessing) {
                sendToAI(text);
            }
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
                    document.getElementById('status').innerText = "🔈 ลูกค้ากำลังพูด...";
                    await audioPlayer.play();
                    audioPlayer.onended = () => { resetUI(); };
                } else { resetUI(); }
            } catch (e) { resetUI(); }
        }

        function resetUI() {
            isProcessing = false;
            document.getElementById('mic-btn').disabled = false;
            document.getElementById('status').innerText = "✅ คุยต่อได้เลย";
        }

        function unlockAudio() {
            const silent = new Audio("data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=");
            silent.play().catch(e => {});
        }
    </script>
</body>
</html>
