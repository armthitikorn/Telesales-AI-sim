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

# --- [ส่วนที่ 2: ตั้งค่าตัวละครคุณวีณา (Natural Prompt)] ---
# ปรับให้เป็นธรรมชาติ ไม่พูดคำในวงเล็บ และดำเนินตาม Scenario ที่กำหนด
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction="""คุณคือ 'คุณวีณา' ลูกค้าผู้หญิงอายุ 40 ปี 
    กฎเหล็ก:
    1. ห้ามใส่ท่าทางในวงเล็บ เช่น (ยิ้ม) หรือ (หัวเราะ) ในคำพูดเด็ดขาด ให้ตอบเป็นประโยคพูดปกติเท่านั้น
    2. สถานการณ์การสนทนา:
       - ช่วงแรก: คุณยุ่งอยู่และไม่อยากคุย จะปฏิเสธสายในตอนต้น พนักงานต้องโน้มน้าวให้คุณยอมฟัง
       - ช่วงกลาง: ถ้าพนักงานพูดจาดีและโน้มน้าวได้น่าสนใจ คุณจะเริ่มฟังและถามคำถามเกี่ยวกับสุขภาพ (คุณมีความดันสูง)
       - ช่วงปิดการขาย: คุณจะมีข้อโต้แย้งเสมอ และสุดท้าย "ต้อง" จบด้วยการขอกลับไปปรึกษาสามีหรือคนที่บ้านก่อน ไม่ตกลงซื้อทันที
    3. บุคลิก: สุภาพ แต่มีความระมัดระวังในการตัดสินใจ"""
)

# --- [ส่วนที่ 3: ฟังก์ชันเรียกเสียงพูด (TTS) พร้อมระบบลบข้อความส่วนเกิน] ---
def get_audio_base64(text):
    if not TTS_API_KEY:
        return None
    
    # ลบข้อความในวงเล็บออก (ถ้ามีหลุดมา) เพื่อไม่ให้ AI อ่านออกมา
    clean_text = re.sub(r'\(.*?\)', '', text)
    
    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={TTS_API_KEY}"
    payload = {
        "input": {"text": clean_text},
        "voice": {"languageCode": "th-TH", "name": "th-TH-Standard-A"},
        "audioConfig": {"audioEncoding": "MP3"}
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            return response.json().get("audioContent")
        else:
            print(f"Log TTS Error {response.status_code}")
            return None
    except Exception as e:
        print(f"Log Connection Error: {str(e)}")
        return None

# --- [ส่วนที่ 4: หน้าเว็บ Interface (Modern & Responsive)] ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Veen-a AI Simulator</title>
    <link href="https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary-blue: #1e3a8a;
            --accent-red: #dc2626;
            --bg-light: #f8fafc;
            --white: #ffffff;
        }
        * { box-sizing: border-box; }
        body { 
            font-family: 'Sarabun', sans-serif; 
            background: var(--bg-light); 
            margin: 0; 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            min-height: 100vh;
        }
        .container { 
            width: 100%; 
            max-width: 500px; 
            height: 100vh; 
            max-height: 800px;
            background: var(--white); 
            display: flex; 
            flex-direction: column; 
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }
        /* Responsive for Desktop/Tablets */
        @media (min-width: 768px) {
            .container { border-radius: 20px; height: 90vh; }
        }
        .header { 
            padding: 20px; 
            background: var(--primary-blue); 
            color: white; 
            text-align: center; 
            border-bottom: 4px solid var(--accent-red);
        }
        .header h2 { margin: 0; font-size: 1.2rem; }
        #status { font-size: 0.8rem; opacity: 0.8; margin-top: 5px; }
        
        #chat-box { 
            flex: 1; 
            overflow-y: auto; 
            padding: 20px; 
            display: flex; 
            flex-direction: column; 
            gap: 15px; 
            background: #f1f5f9;
        }
        .msg { max-width: 85%; padding: 12px 16px; border-radius: 15px; font-size: 0.95rem; line-height: 1.4; }
        .msg-staff { align-self: flex-end; background: var(--primary-blue); color: white; border-bottom-right-radius: 2px; }
        .msg-veena { align-self: flex-start; background: var(--white); color: #334155; border-bottom-left-radius: 2px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }

        .controls { 
            padding: 20px; 
            background: var(--white); 
            display: flex; 
            flex-direction: column; 
            align-items: center; 
            gap: 10px;
            border-top: 1px solid #e2e8f0;
        }
        .mic-btn { 
            width: 70px; height: 70px; 
            border-radius: 50%; 
            border: none; 
            background: var(--accent-red); 
            color: white; 
            font-size: 28px; 
            cursor: pointer; 
            transition: 0.3s;
            box-shadow: 0 4px 15px rgba(220, 38, 38, 0.3);
        }
        .mic-btn.active { transform: scale(1.1); background: #991b1b; animation: pulse 1.5s infinite; }
        @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0.4); } 70% { box-shadow: 0 0 0 15px rgba(220, 38, 38, 0); } 100% { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0); } }

        .eval-btn { 
            padding: 10px 20px; 
            border-radius: 25px; 
            border: 1px solid var(--primary-blue); 
            background: transparent; 
            color: var(--primary-blue); 
            font-weight: 600; 
            cursor: pointer; 
            display: none;
            width: 100%;
        }
        .eval-btn:hover { background: var(--primary-blue); color: white; }

        #eval-result { 
            display: none; 
            position: absolute; 
            top: 10%; left: 5%; right: 5%; bottom: 10%; 
            background: white; 
            padding: 25px; 
            border-radius: 15px; 
            z-index: 10; 
            overflow-y: auto; 
            box-shadow: 0 0 50px rgba(0,0,0,0.5); 
        }
        .close-eval { color: var(--accent-red); float: right; cursor: pointer; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>👩 คุณวีณา (Simulator)</h2>
            <div id="status">แตะไมค์เพื่อเริ่มบทสนทนา</div>
        </div>
        <div id="chat-box"></div>
        <div class="controls">
            <button id="mic-btn" class="mic-btn" onclick="toggleListen()">🎤</button>
            <button id="eval-btn" class="eval-btn" onclick="requestEvaluation()">จบการสนทนาและดูผลประเมิน</button>
        </div>
    </div>

    <div id="eval-result">
        <span class="close-eval" onclick="document.getElementById('eval-result').style.display='none'">[ปิด]</span>
        <div id="eval-content"></div>
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
            if (!recognition) return alert("Browser ไม่รองรับระบบเสียง");
            recognition.start();
            document.getElementById('mic-btn').classList.add('active');
            document.getElementById('status').innerText = "กำลังฟัง...";
        }

        async function sendToAI(text) {
            const chatBox = document.getElementById('chat-box');
            chatBox.innerHTML += `<div class="msg msg-staff"><b>พนักงาน:</b> ${text}</div>`;
            history.push("พนักงาน: " + text);
            document.getElementById('status').innerText = "คุณวีณากำลังคิด...";
            chatBox.scrollTop = chatBox.scrollHeight;

            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: text})
                });
                const data = await res.json();

                chatBox.innerHTML += `<div class="msg msg-veena"><b>คุณวีณา:</b> ${data.reply}</div>`;
                history.push("คุณวีณา: " + data.reply);
                chatBox.scrollTop = chatBox.scrollHeight;
                document.getElementById('eval-btn').style.display = 'block';

                if(data.audio) {
                    const audio = new Audio("data:audio/mp3;base64," + data.audio);
                    audio.play();
                    document.getElementById('status').innerText = "คุณวีณากำลังพูด...";
                    audio.onended = () => document.getElementById('status').innerText = "คุยต่อได้เลย...";
                }
            } catch (e) {
                document.getElementById('status').innerText = "Error: เชื่อมต่อไม่ได้";
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
            document.getElementById('eval-content').innerHTML = "<h3>📊 ผลการประเมินการขาย</h3>" + data.evaluation.replace(/\\n/g, '<br>');
            document.getElementById('eval-result').style.display = 'block';
            document.getElementById('status').innerText = "ประเมินสำเร็จ";
        }
    </script>
</body>
</html>
"""

# --- [ส่วนที่ 5: Routes] ---
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
    prompt = f"คุณคือโค้ชสอนการขายประกัน ประเมินบทสนทนานี้ให้คะแนนเต็ม 10 ในด้าน: 1.การข้ามข้อโต้แย้งตอนต้น 2.การถามคำถามสุขภาพ 3.การโน้มน้าวตอนปิดการขาย และ 4.การรับมือเมื่อลูกค้าขอไปปรึกษาสามี: {history}"
    evaluation = model.generate_content(prompt)
    return jsonify({"evaluation": evaluation.text})

if __name__ == "__main__":
    app.run(debug=True)
