import os
import requests
import re
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai

app = Flask(__name__)

# --- [ส่วนที่ 1: ตั้งค่า AI] ---
GENAI_API_KEY = os.environ.get("GENAI_API_KEY")
TTS_API_KEY = os.environ.get("TTS_API_KEY")
genai.configure(api_key=GENAI_API_KEY)
model = genai.GenerativeModel(model_name="gemini-2.5-flash")

# --- [ส่วนที่ 2: ตั้งค่าเสียง - ใช้ Neural2 (ตัวท็อปของ Google Cloud)] ---
CUSTOMERS = {
    "1": {"name": "น้องฟ้า", "desc": "SuperSmartSave 20/9", "prompt": "คุณคือ 'ฟ้า' อายุ 25 ปี ลงท้าย 'ค่ะ'", "voice": {"name": "th-TH-Neural2-A", "pitch": 0.0, "rate": 1.0}},
    "2": {"name": "คุณวิรัช", "desc": "Double Sure Health", "prompt": "คุณคือ 'วิรัช' อายุ 45 ปี ลงท้าย 'ครับ'", "voice": {"name": "th-TH-Neural2-B", "pitch": -1.0, "rate": 1.0}},
    "3": {"name": "คุณป้ามาลี", "desc": "Wealth 888", "prompt": "คุณคือ 'ป้ามาลี' ลงท้าย 'ค่ะ/จ๊ะ'", "voice": {"name": "th-TH-Neural2-A", "pitch": -2.0, "rate": 0.9}},
    "4": {"name": "แม่แอน", "desc": "ยาก: ปฏิเสธหนักมาก", "prompt": "คุณคือ 'แอน' ลงท้าย 'ค่ะ'", "voice": {"name": "th-TH-Neural2-A", "pitch": 0.0, "rate": 1.0}},
    "5": {"name": "คุณอัครเดช", "desc": "ยากมาก: นักธุรกิจ", "prompt": "คุณคือ 'อัครเดช' ลงท้าย 'ครับ'", "voice": {"name": "th-TH-Neural2-B", "pitch": -1.5, "rate": 1.05}}
}

def get_audio_base64(text, voice_config):
    if not TTS_API_KEY: return None
    clean_text = re.sub(r'[*#_]', '', text)
    clean_text = re.sub(r'\(.*?\)', '', clean_text).strip()
    
    # เรียก API สร้างเสียง
    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={TTS_API_KEY}"
    payload = {
        "input": {"text": clean_text},
        "voice": {"languageCode": "th-TH", "name": voice_config["name"]},
        "audioConfig": {"audioEncoding": "MP3", "pitch": voice_config["pitch"], "speakingRate": voice_config["rate"]}
    }
    
    try:
        res = requests.post(url, json=payload, timeout=10)
        res_data = res.json()
        
        # หาก Google ส่ง Error กลับมา (เช่น API ยังไม่ได้ Enable)
        if "error" in res_data:
            print(f"TTS Error: {res_data['error']['message']}")
            return None
            
        return res_data.get("audioContent")
    except Exception as e:
        print(f"Request Fail: {e}")
        return None

# --- [ส่วนที่ 3: UI - เพิ่มการแจ้งเตือนสถานะเสียง] ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Telesales Simulator AI</title>
    <style>
        body { font-family: sans-serif; background: #f0f2f5; padding: 20px; }
        .card { background: white; padding: 15px; margin: 10px 0; border-radius: 10px; cursor: pointer; border-left: 5px solid #1e3a8a; }
        #chat { height: 350px; overflow-y: auto; background: #fff; padding: 15px; border-radius: 10px; margin-bottom: 20px; border: 1px solid #ddd; }
        .btn-mic { width: 70px; height: 70px; border-radius: 50%; background: #be123c; color: white; border: none; font-size: 30px; cursor: pointer; }
    </style>
</head>
<body>
    <div id="lobby">
        <h2>🏆 เลือกบททดสอบ</h2>
        <input type="text" id="staff-name" placeholder="ชื่อพนักงาน" style="width: 100%; padding: 10px; margin-bottom: 15px;">
        <div id="customer-list"></div>
    </div>

    <div id="app" style="display:none;">
        <h3 id="active-name"></h3>
        <div id="chat"></div>
        <div style="text-align:center;">
            <button class="btn-mic" onclick="listen()">🎤</button>
            <p id="status" style="font-weight:bold;">แตะไมค์เพื่อพูด</p>
        </div>
    </div>

    <script>
        var history_log = [];
        var activeLvl = "";
        var player = new Audio();
        var recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
        recognition.lang = 'th-TH';

        var custs = {{ CUSTOMERS | tojson | safe }};
        var list = document.getElementById('customer-list');
        for (var k in custs) {
            let lvl = k;
            let d = document.createElement('div');
            d.className = 'card';
            d.innerHTML = '<b>'+custs[lvl].name+'</b><br>'+custs[lvl].desc;
            d.onclick = () => {
                if(!document.getElementById('staff-name').value) return alert("ระบุชื่อก่อน");
                activeLvl = lvl;
                document.getElementById('lobby').style.display='none';
                document.getElementById('app').style.display='block';
                document.getElementById('active-name').innerText = "ลูกค้า: " + custs[lvl].name;
            };
            list.appendChild(d);
        }

        recognition.onresult = (e) => { talk(e.results[0][0].transcript); };

        async function talk(t) {
            document.getElementById('status').innerText = "⌛ กำลังประมวลผล...";
            document.getElementById('chat').innerHTML += "<div><b>คุณ:</b> "+t+"</div>";
            
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: t, lvl: activeLvl, history: history_log})
            });
            const data = await res.json();
            
            document.getElementById('chat').innerHTML += "<div><b>ลูกค้า:</b> "+data.reply+"</div>";
            document.getElementById('chat').scrollTop = document.getElementById('chat').scrollHeight;

            if (data.audio) {
                player.src = "data:audio/mp3;base64," + data.audio;
                player.play();
                document.getElementById('status').innerText = "✅ พร้อมคุยต่อ";
            } else {
                document.getElementById('status').innerText = "❌ เสียงไม่ทำงาน (เช็ก API Key หรือการ Enable API)";
            }
        }

        function listen() {
            player.pause();
            recognition.start();
            document.getElementById('status').innerText = "🔴 กำลังฟัง...";
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
    lvl, user_msg, history = data.get('lvl'), data.get('message'), data.get('history', [])
    cust = CUSTOMERS[lvl]
    full_prompt = f"System: {cust['prompt']}\\nHistory: {history}\\nUser: {user_msg}"
    response = model.generate_content(full_prompt)
    reply_text = response.text
    audio_data = get_audio_base64(reply_text, cust['voice'])
    return jsonify({"reply": reply_text, "audio": audio_data})

if __name__ == "__main__":
    app.run(debug=True)
