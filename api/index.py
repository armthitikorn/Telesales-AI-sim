import os
import requests
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai

app = Flask(__name__)

# --- [ส่วนที่ 1: ตั้งค่า API Keys] ---
GENAI_API_KEY = os.environ.get("GENAI_API_KEY")
TTS_API_KEY = os.environ.get("TTS_API_KEY")

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
        print("Log: TTS_API_KEY is missing")
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
        else:
            # เพิ่มการ Print Error ออกมาดูใน Vercel Logs
            print(f"Log TTS Error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"Log Connection Error: {str(e)}")
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
        .mic-btn { width: 80px; height: 80px; border-radius: 50%; border: none; background: #ec4899; color: white; font-size: 35px; cursor: pointer; transition: 0.3s; }
        .mic-btn.active { background: #be185d; transform: scale(1.1); box-shadow: 0 0 15px rgba(236, 72, 153, 0.5); }
        .eval-btn { background: #1e293b; color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; display: none; margin: 0 auto; }
    </style>
</head>
<body>
    <div class="card">
        <h2 style="color: #be185d;">👩 คุณวีณา (Simulator)</h2>
        <div id="status">กดไมค์เพื่อเริ่มคุย...</div>
        <div id="chat-box"></div>
        <button id="mic-btn" class="mic-btn" onclick="toggleListen()">🎤</button>
        <br><br>
        <button id="eval-btn" class="eval-btn" onclick="requestEvaluation()">จบการสนทนาและประเมินผล</button>
        <div id="eval-result" style="display:none; margin-top:20px; text-align:left; background:#fffbeb; padding:15px; border-radius:10px; white-space: pre-line;"></div>
    </div>

    <script>
        let history = [];
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        let recognition;

        if (SpeechRecognition) {
            recognition = new SpeechRecognition();
            recognition.lang = 'th-TH';
            recognition.onresult = (e) => sendToAI(e.results[0][0].transcript);
            recognition.onend = () => document.getElementById('mic-btn').classList.remove('active');
        }

        function toggleListen() {
            if (!recognition) return alert("Browser ของคุณไม่รองรับระบบสั่งการด้วยเสียง");
            recognition.start();
            document.getElementById('mic-btn').classList.add('active');
            document.getElementById('status').innerText = "กำลังฟัง...";
        }

        async function sendToAI(text) {
            const chatBox = document.getElementById('chat-box');
            chatBox.innerHTML += `<div><b>พนักงาน:</b> ${text}</div>`;
            history.push("พนักงาน: " + text);
            document.getElementById('status').innerText = "คุณวีณากำลังคิด...";

            try {
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
                    audio.play().catch(e => console.log("Audio play blocked by browser"));
                    document.getElementById('status').innerText = "คุณวีณากำลังพูด...";
                    audio.onended = () => document.getElementById('status').innerText = "แตะไมค์เพื่อคุยต่อ...";
                } else {
                    document.getElementById('status').innerText = "แตะไมค์เพื่อคุยต่อ (ไม่มีเสียง)";
                }
            } catch (e) {
                document.getElementById('status').innerText = "เกิดข้อผิดพลาดในการเชื่อมต่อ";
            }
        }

        async function requestEvaluation() {
            document.getElementById('status').innerText = "โค้ชกำลังประเมินผล...";
            const res = await fetch('/api/evaluate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({history: history.join("\\n")})
            });
            const data = await res.json();
            const evalArea = document.getElementById('eval-result');
            evalArea.innerHTML = "<h3>📊 ผลการประเมิน</h3>" + data.evaluation;
            evalArea.style.display = 'block';
            document.getElementById('status').innerText = "ประเมินผลสำเร็จ";
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
    try:
        user_msg = request.json.get('message')
        response = model.generate_content(user_msg)
        reply_text = response.text
        audio_data = get_audio_base64(reply_text)
        return jsonify({"reply": reply_text, "audio": audio_data})
    except Exception as e:
        print(f"Chat Error: {str(e)}")
        return jsonify({"reply": "ขออภัยค่ะ ระบบขัดข้องนิดหน่อย", "audio": None}), 500

@app.route('/api/evaluate', methods=['POST'])
def evaluate():
    history = request.json.get('history')
    prompt = f"คุณคือโค้ชสอนการขายประกัน ประเมินบทสนทนานี้ให้คะแนนเต็ม 10 และบอกจุดเด่นจุดด้อย: {history}"
    evaluation = model.generate_content(prompt)
    return jsonify({"evaluation": evaluation.text})

if __name__ == "__main__":
    app.run(debug=True)
