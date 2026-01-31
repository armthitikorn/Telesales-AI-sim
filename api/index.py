from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai
import requests
import json

app = Flask(__name__)

# --- [ตั้งค่า API Keys] ---
# แนะนำให้ใส่ใน Environment Variables ของ Vercel เพื่อความปลอดภัย
GENAI_API_KEY = "AIzaSyClIiuD-GJ_9O0D6fL_YbvihYubpkAdWo8"
TTS_API_KEY = "AIzaSyA_8E0ic0mjLWNBfjHDUXCXUNW_IV3-hGs"


genai.configure(api_key=GENAI_API_KEY)

# ตั้งค่าโมเดลคุณวีณา (ใช้ Gemini 2.5 Flash เสมอตามคำแนะนำ)
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction="""คุณคือ 'คุณวีณา' ลูกค้าผู้หญิงอายุ 40 ปี น้ำเสียงสุภาพ ใจดี แต่มีความกังวลเรื่องสุขภาพ 
    - นิสัย: ชอบเล่าเรื่อง และมักจะถามคำถามกลับเพื่อให้พนักงานอธิบาย 
    - สุขภาพ: มีโรคประจำตัวคือความดันสูง (บอกเมื่อถูกถามเท่านั้น) แต่ไม่มีเบาหวาน 
    - เป้าหมาย: สนใจประกันสุขภาพและออมทรัพย์ให้ตัวเองและครอบครัว"""
)

def get_audio_base64(text):
    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={TTS_API_KEY}"
    payload = {
        "input": {"text": text},
        "voice": {"languageCode": "th-TH", "name": "th-TH-Standard-A"},
        "audioConfig": {"audioEncoding": "MP3"}
    }
    response = requests.post(url, json=payload)
    return response.json().get("audioContent") if response.status_code == 200 else None

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>คุณวีณา: Telesale Simulator AI</title>
    <style>
        body { font-family: 'Sarabun', sans-serif; background: #fdf2f8; display: flex; justify-content: center; padding: 20px; }
        .card { width: 100%; max-width: 600px; background: white; border-radius: 20px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); padding: 25px; text-align: center; }
        .avatar { width: 100px; height: 100px; background: #ec4899; border-radius: 50%; margin: 0 auto 15px; display: flex; align-items: center; justify-content: center; color: white; font-size: 40px; }
        #status { color: #666; margin-bottom: 20px; font-weight: bold; min-height: 24px; }
        #chat-box { height: 300px; overflow-y: auto; border: 1px solid #eee; padding: 15px; margin-bottom: 20px; text-align: left; background: #fafafa; border-radius: 12px; }
        .mic-btn { width: 80px; height: 80px; border-radius: 50%; border: none; background: #ec4899; color: white; font-size: 35px; cursor: pointer; transition: 0.3s; }
        .mic-btn.active { background: #be185d; transform: scale(1.1); box-shadow: 0 0 20px rgba(236, 72, 153, 0.5); }
        .eval-btn { background: #1e293b; color: white; border: none; padding: 12px 24px; border-radius: 10px; cursor: pointer; margin-top: 15px; display: none; width: 100%; font-weight: bold; }
        .eval-result { display: none; margin-top: 20px; padding: 20px; background: #fffbeb; border: 1px solid #fde68a; border-radius: 12px; text-align: left; white-space: pre-line; }
    </style>
</head>
<body>
    <div class="card">
        <div class="avatar">👩</div>
        <h2 style="color: #be185d; margin-bottom: 5px;">คุณวีณา (Simulator)</h2>
        <p style="color: #666; font-size: 14px; margin-bottom: 20px;">กดไมค์เพื่อเริ่มบทสนทนาทางโทรศัพท์</p>
        
        <div id="status">แตะไมค์แล้วเริ่มพูดได้เลย</div>
        <div id="chat-box"></div>
        
        <button id="mic-btn" class="mic-btn" onclick="toggleListen()">🎤</button>
        <button id="end-btn" class="eval-btn" onclick="requestEvaluation()">จบการสนทนาและประเมินผล</button>
        
        <div id="eval-area" class="eval-result"></div>
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
            recognition.start();
            document.getElementById('mic-btn').classList.add('active');
            document.getElementById('status').innerText = "กำลังฟัง...";
        }

        async function sendToAI(text) {
            const chatBox = document.getElementById('chat-box');
            chatBox.innerHTML += `<div><b>พนักงาน:</b> ${text}</div>`;
            history.push("พนักงาน: " + text);
            document.getElementById('status').innerText = "คุณวีณากำลังคิด...";

            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: text})
            });
            const data = await res.json();

            chatBox.innerHTML += `<div style="color:#be185d"><b>คุณวีณา:</b> ${data.reply}</div>`;
            history.push("คุณวีณา: " + data.reply);
            chatBox.scrollTop = chatBox.scrollHeight;
            document.getElementById('end-btn').style.display = 'block';

            if(data.audio) {
                const audio = new Audio("data:audio/mp3;base64," + data.audio);
                audio.play();
                document.getElementById('status').innerText = "คุณวีณากำลังพูด...";
                audio.onended = () => document.getElementById('status').innerText = "แตะไมค์คุยต่อ...";
            }
        }

        async function requestEvaluation() {
            document.getElementById('status').innerText = "โค้ชกำลังประเมินผล...";
            document.getElementById('mic-btn').style.display = 'none';
            document.getElementById('end-btn').disabled = true;

            const res = await fetch('/api/evaluate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({history: history.join("\\n")})
            });
            const data = await res.json();
            
            const evalArea = document.getElementById('eval-area');
            evalArea.innerHTML = "<h3>📊 ผลการประเมิน</h3>" + data.evaluation;
            evalArea.style.display = 'block';
            document.getElementById('status').innerText = "ประเมินผลสำเร็จ";
        }
    </script>
</body>
</html>
"""

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
    # ใช้ Gemini 2.5 Flash ในการประเมินผลอย่างละเอียด
    prompt = f"""คุณคือโค้ชสอนการขายประกัน (Sales Coach) โปรดประเมินบทสนทนานี้ตามเกณฑ์:
    1. Emotion (การรับรู้อารมณ์ลูกค้า)
    2. Tone (ความสุภาพและน้ำเสียง)
    3. Sentence Structure (การเลือกใช้รูปประโยค)
    4. Health Questioning (การถามถึงสุขภาพ)
    
    ให้คะแนนแต่ละข้อเต็ม 10 และสรุปข้อควรปรับปรุง:
    {history}"""
    
    evaluation = model.generate_content(prompt)
    return jsonify({"evaluation": evaluation.text})

if __name__ == "__main__":
    app.run(debug=True)
