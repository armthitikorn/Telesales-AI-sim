import os
import requests
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai

app = Flask(__name__)

# --- [ส่วนที่ 1: ตั้งค่า API Keys] ---
# หากรันใน Vercel ให้ใช้แบบนี้ (ปลอดภัย):
GENAI_API_KEY = os.environ.get("GENAI_API_KEY")
TTS_API_KEY = os.environ.get("TTS_API_KEY")

# หากจะทดสอบในเครื่องแบบวางรหัสตรงๆ ให้แก้เป็น (ระวังอย่าเผลอส่งขึ้น GitHub นะครับ):
# GENAI_API_KEY = "วางรหัส Gemini ที่นี่"
# TTS_API_KEY = "วางรหัส Google TTS ที่นี่"

genai.configure(api_key=GENAI_API_KEY)

# --- [ส่วนที่ 2: ตั้งค่าตัวละครคุณวีณา] ---
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction="""คุณคือ 'คุณวีณา' ลูกค้าผู้หญิงอายุ 40 ปี น้ำเสียงสุภาพ ใจดี แต่มีความกังวลเรื่องสุขภาพ 
    - นิสัย: ชอบเล่าเรื่อง และมักจะถามคำถามกลับเพื่อให้พนักงานอธิบาย 
    - สุขภาพ: มีโรคประจำตัวคือความดันสูง (บอกเมื่อถูกถามเท่านั้น) 
    - เป้าหมาย: สนใจประกันสุขภาพและออมทรัพย์ให้ตัวเองและครอบครัว"""
)

# --- [ส่วนที่ 3: ฟังก์ชันเรียกเสียงพูด (TTS)] ---
def get_audio_base64(text):
    if not TTS_API_KEY:
        return None
    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={TTS_API_KEY}"
    payload = {
        "input": {"text": text},
        "voice": {"languageCode": "th-TH", "name": "th-TH-Standard-A"},
        "audioConfig": {"audioEncoding": "MP3"}
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            return response.json().get("audioContent")
    except:
        return None
    return None

# --- [ส่วนที่ 4: หน้าเว็บ Interface] ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>คุณวีณา AI Simulator</title>
    <style>
        body { font-family: 'Sarabun', sans-serif; background: #fdf2f8; display: flex; justify-content: center; padding: 20px; }
        .card { width: 100%; max-width: 600px; background: white; border-radius: 20px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); padding: 25px; text-align: center; }
        #chat-box { height: 300px; overflow-y: auto; border: 1px solid #eee; padding: 15px; margin-bottom: 20px; text-align: left; background: #fafafa; border-radius: 12px; }
        .mic-btn { width: 80px; height: 80px; border-radius: 50%; border: none; background: #ec4899; color: white; font-size: 35px; cursor: pointer; }
        .mic-btn.active { background: #be185d; box-shadow: 0 0 15px rgba(236, 72, 153, 0.5); }
    </style>
</head>
<body>
    <div class="card">
        <h2 style="color: #be185d;">👩 คุณวีณา (Simulator)</h2>
        <div id="status">กดไมค์เพื่อเริ่มคุย...</div>
        <div id="chat-box"></div>
        <button id="mic-btn" class="mic-btn" onclick="toggleListen()">🎤</button>
        <button id="eval-btn" style="margin-top:20px; display:none;" onclick="requestEvaluation()">จบการสนทนาและประเมินผล</button>
        <div id="eval-result" style="display:none; margin-top:20px; text-align:left; background:#fffbeb; padding:15px; border-radius:10px;"></div>
    </div>

    <script>
        let history = [];
        const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
        recognition.lang = 'th-TH';

        recognition.onresult = (e) => sendToAI(e.results[0][0].transcript);
        
        function toggleListen() {
            recognition.start();
            document.getElementById('mic-btn').classList.add('active');
            document.getElementById('status').innerText = "กำลังฟัง...";
        }

        async function sendToAI(text) {
            document.getElementById('mic-btn').classList.remove('active');
            const chatBox = document.getElementById('chat-box');
            chatBox.innerHTML += `<div><b>คุณ:</b> ${text}</div>`;
            history.push("พนักงาน: " + text);

            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: text})
            });
            const data = await res.json();

            chatBox.innerHTML += `<div style="color:#be185d"><b>คุณวีณา:</b> ${data.reply}</div>`;
            history.push("คุณวีณา: " + data.reply);
            chatBox.scrollTop = chatBox.scrollHeight;
            document.getElementById('eval-btn').style.display = 'block';

            if(data.audio) {
                const audio = new Audio("data:audio/mp3;base64," + data.audio);
                audio.play();
            }
            document.getElementById('status').innerText = "แตะไมค์เพื่อคุยต่อ...";
        }

        async function requestEvaluation() {
            document.getElementById('status').innerText = "กำลังประเมินผล...";
            const res = await fetch('/api/evaluate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({history: history.join("\\n")})
            });
            const data = await res.json();
            document.getElementById('eval-result').innerHTML = "<h3>📊 ผลการประเมิน</h3>" + data.evaluation;
            document.getElementById('eval-result').style.display = 'block';
        }
    </script>
</body>
</html>
"""

# --- [ส่วนที่ 5: Routes ของ Server] ---
@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/chat', methods=['POST'])
def chat():
    user_msg = request.json.get('message')
    response = model.generate_content(user_msg)
    reply_text = response.text
    audio_data = get_audio_base64(reply_text)
    return jsonify({"reply": reply_text, "audio": audio_data})

@app.route('/api/evaluate', methods=['POST'])
def evaluate():
    history = request.json.get('history')
    prompt = f"คุณคือโค้ชสอนการขายประกัน ประเมินบทสนทนานี้: {history}"
    evaluation = model.generate_content(prompt)
    return jsonify({"evaluation": evaluation.text})

if __name__ == "__main__":
    app.run(debug=True)
    
