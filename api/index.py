import os
import requests
import re
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai

app = Flask(__name__)

# --- [ส่วนที่ 1: การตั้งค่า - ใส่ API Key ใน Environment Variables ของ Vercel] ---
GENAI_API_KEY = os.environ.get("GENAI_API_KEY")
TTS_API_KEY = os.environ.get("TTS_API_KEY")

genai.configure(api_key=GENAI_API_KEY)
# ใช้ Gemini 2.5 Flash ตามที่อาร์มต้องการ
model = genai.GenerativeModel(model_name="gemini-2.5-flash")

# --- [ส่วนที่ 2: ตั้งค่าลูกค้าชายเพียงคนเดียว] ---
CUSTOMER_NAME = "คุณวิรัช"
CUSTOMER_PROMPT = "คุณคือ 'วิรัช' ลูกค้าผู้ชาย อายุ 45 ปี พูดจาสุภาพแต่ปฏิเสธเก่ง ลงท้ายด้วย 'ครับ' เท่านั้น"

def get_male_audio(text):
    if not TTS_API_KEY: return None
    
    # ล้างข้อความสัญลักษณ์ต่างๆ ออกก่อนส่งไปอ่าน
    clean_text = re.sub(r'\(.*?\)', '', text).replace('*', '').strip()
    
    url = f"https://texttospeech.googleapis.com/v1beta1/text:synthesize?key={TTS_API_KEY}"
    
    # Payload ที่บังคับเป็นเสียงผู้ชายไทย (Neural2-B + MALE)
    payload = {
        "input": {"text": clean_text},
        "voice": {
            "languageCode": "th-TH",
            "name": "th-TH-Neural2-B",
            "ssmlGender": "MALE"
        },
        "audioConfig": {
            "audioEncoding": "MP3",
            "pitch": -2.0,  # ปรับเสียงให้ต่ำลงเพื่อความเป็นผู้ชายวัยทำงาน
            "speakingRate": 1.0
        }
    }
    
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.json().get("audioContent")
    except:
        return None

# --- [ส่วนที่ 3: หน้าจอ UI แบบเรียบง่ายที่สุด] ---
HTML_UI = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Test Male Voice</title>
    <style>
        body { font-family: sans-serif; text-align: center; padding: 50px; background: #f0f2f5; }
        .chat-container { max-width: 500px; margin: auto; background: white; padding: 20px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .btn { background: #1a73e8; color: white; border: none; padding: 15px 30px; border-radius: 30px; cursor: pointer; font-size: 18px; }
        #status { margin-top: 20px; color: #555; }
    </style>
</head>
<body>
    <div class="chat-container">
        <h2>ทดสอบเสียงผู้ชาย: {{ name }}</h2>
        <p>ลองพูดว่า: "สวัสดีครับคุณวิรัช"</p>
        <button class="btn" onclick="startListen()">🎤 แตะเพื่อพูด</button>
        <div id="status">รอการเชื่อมต่อ...</div>
        <div id="response-text" style="margin-top:20px; font-weight:bold; color:#1e3a8a;"></div>
    </div>

    <script>
        const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
        recognition.lang = 'th-TH';
        const player = new Audio();

        function startListen() {
            recognition.start();
            document.getElementById('status').innerText = "กำลังฟัง...";
        }

        recognition.onresult = async (event) => {
            const text = event.results[0][0].transcript;
            document.getElementById('status').innerText = "คุณพูดว่า: " + text;
            
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ message: text })
            });
            const data = await res.json();
            
            document.getElementById('response-text').innerText = data.reply;
            if(data.audio) {
                player.src = "data:audio/mp3;base64," + data.audio;
                player.play();
                document.getElementById('status').innerText = "ลำโพงกำลังเล่นเสียงผู้ชาย...";
            }
        };
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_UI, name=CUSTOMER_NAME)

@app.route('/api/chat', methods=['POST'])
def chat():
    user_input = request.json.get("message")
    
    # เรียก Gemini สร้างคำตอบ
    prompt = f"{CUSTOMER_PROMPT}\nพนักงานพูดว่า: {user_input}\nจงตอบกลับสั้นๆ:"
    response = model.generate_content(prompt)
    reply = response.text
    
    # สร้างเสียง (บังคับชาย)
    audio = get_male_audio(reply)
    
    return jsonify({"reply": reply, "audio": audio})

if __name__ == "__main__":
    app.run(debug=True)
