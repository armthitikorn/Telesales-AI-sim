import os
import requests
import re
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai

app = Flask(__name__)

# --- [ส่วนที่ 1: การตั้งค่า API Keys] ---
# ดึงค่าจาก Environment Variables ของ Vercel
GENAI_API_KEY = os.environ.get("GENAI_API_KEY")
TTS_API_KEY = os.environ.get("TTS_API_KEY")

genai.configure(api_key=GENAI_API_KEY)
# ใช้ Gemini 2.5 Flash สำหรับระบบ Simulator
model = genai.GenerativeModel(model_name="gemini-2.5-flash")

# --- [ส่วนที่ 2: ตั้งค่าลูกค้าคุณวิรัช (ผู้ชาย)] ---
CUSTOMER_NAME = "คุณวิรัช"
CUSTOMER_PROMPT = "คุณคือ 'วิรัช' ลูกค้าผู้ชาย อายุ 45 ปี พูดจาสุภาพแต่ปฏิเสธเก่ง ลงท้ายด้วย 'ครับ' เท่านั้น ห้ามตอบรับง่ายๆ"

def get_male_audio(text):
    if not TTS_API_KEY: 
        print("ยังไม่ได้ใส่ TTS_API_KEY")
        return None
    
    # ล้างข้อความส่วนเกินก่อนส่งไปอ่าน
    clean_text = re.sub(r'\(.*?\)', '', text).replace('*', '').strip()
    if not clean_text: return None
    
    url = f"https://texttospeech.googleapis.com/v1beta1/text:synthesize?key={TTS_API_KEY}"
    
    # Payload บังคับเสียงผู้ชายตัวใหม่ของ Google (Chirp 3 HD) ตามที่คุณระบุ
    payload = {
        "input": {"text": clean_text},
        "voice": {
            "languageCode": "th-TH",
            "name": "th-TH-Chirp3-HD-Achird" # รหัสเสียงผู้ชายภาษาไทย
        },
        "audioConfig": {
            "audioEncoding": "MP3"
            # ห้ามใส่ pitch หรือ speakingRate เด็ดขาด
        }
    }
    
    try:
        res = requests.post(url, json=payload, timeout=10)
        res_json = res.json()
        
        if "audioContent" in res_json:
            return res_json["audioContent"]
        else:
            # พิมพ์ Error ออกมาทาง Console เพื่อให้เราดูใน Vercel Logs ได้ถ้ามันไม่ทำงาน
            print(f"Google TTS Error: {res_json}") 
            return None
    except Exception as e:
        print(f"Request Error: {e}")
        return None

# --- [ส่วนที่ 3: หน้าจอ UI ทดสอบ] ---
HTML_UI = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <title>Google TTS: Chirp HD Male Voice Test</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: sans-serif; text-align: center; padding: 20px; background: #f0f2f5; }
        .chat-container { max-width: 500px; margin: auto; background: white; padding: 30px; border-radius: 15px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
        .btn { background: #1a73e8; color: white; border: none; padding: 15px 30px; border-radius: 30px; cursor: pointer; font-size: 18px; width: 100%; margin-top: 10px; }
        .btn:disabled { background: #ccc; cursor: not-allowed; }
        #status { margin-top: 20px; color: #555; font-size: 14px; }
        .msg-box { margin-top: 20px; text-align: left; padding: 15px; border-radius: 10px; background: #f8fafc; border-left: 5px solid #1a73e8; display: none; }
    </style>
</head>
<body>
    <div class="chat-container">
        <h2 style="color: #1a73e8;">ทดสอบเสียงผู้ชาย (Chirp 3 HD)</h2>
        <p>ลูกค้า: <b>{{ name }}</b></p>
        <p style="color: gray; font-size: 14px;">ลองกดไมค์แล้วพูดทักทายคุณวิรัชดูครับ</p>
        
        <button id="mic-btn" class="btn" onclick="startListen()">🎤 กดเพื่อพูด</button>
        <div id="status">รอการเชื่อมต่อ...</div>
        
        <div id="reply-box" class="msg-box">
            <b>คุณวิรัชตอบ:</b> <span id="response-text"></span>
        </div>
    </div>

    <script>
        const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
        recognition.lang = 'th-TH';
        const player = new Audio();

        function startListen() {
            document.getElementById('mic-btn').disabled = true;
            recognition.start();
            document.getElementById('status').innerText = "กำลังฟังเสียงของคุณ...";
        }

        recognition.onresult = async (event) => {
            const text = event.results[0][0].transcript;
            document.getElementById('status').innerText = "คุณพูดว่า: " + text + "\\nกำลังรอระบบประมวลผล...";
            
            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ message: text })
                });
                const data = await res.json();
                
                document.getElementById('reply-box').style.display = "block";
                document.getElementById('response-text').innerText = data.reply;
                
                if(data.audio) {
                    player.src = "data:audio/mp3;base64," + data.audio;
                    player.play();
                    document.getElementById('status').innerText = "✅ กำลังเล่นเสียงคุณวิรัช (ผู้ชาย)";
                } else {
                    document.getElementById('status').innerText = "❌ ไม่มีไฟล์เสียงส่งกลับมา (เช็ค Logs ใน Vercel)";
                }
            } catch (e) {
                document.getElementById('status').innerText = "❌ เกิดข้อผิดพลาดในการเชื่อมต่อ";
            }
            
            document.getElementById('mic-btn').disabled = false;
        };
        
        recognition.onerror = function(e) {
            document.getElementById('status').innerText = "เกิดข้อผิดพลาดกับไมโครโฟน: " + e.error;
            document.getElementById('mic-btn').disabled = false;
        }
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
    
    # 1. ให้ Gemini 2.5 Flash คิดคำตอบ
    prompt = f"{CUSTOMER_PROMPT}\nพนักงานขายพูดว่า: {user_input}\nจงตอบกลับสั้นๆ สวมบทบาทลูกค้า:"
    response = model.generate_content(prompt)
    reply = response.text
    
    # 2. ส่งข้อความไปทำเสียงผู้ชายด้วย Chirp 3 HD
    audio_base64 = get_male_audio(reply)
    
    return jsonify({"reply": reply, "audio": audio_base64})

if __name__ == "__main__":
    app.run(debug=True)
