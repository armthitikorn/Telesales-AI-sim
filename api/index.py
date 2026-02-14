import os
import requests
import re
import json
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai

app = Flask(__name__)

# --- [ส่วนที่ 1: ตั้งค่า AI] ---
GENAI_API_KEY = os.environ.get("GENAI_API_KEY")
TTS_API_KEY = os.environ.get("TTS_API_KEY")
genai.configure(api_key=GENAI_API_KEY)
model = genai.GenerativeModel(model_name="gemini-2.5-flash")

# --- [ส่วนที่ 2: ตั้งค่าเสียง - ปรับชื่อโมเดลให้ชัวร์ที่สุด] ---
# ใช้ชื่อ th-TH-Neural2-A หรือ th-TH-Standard-A เป็นตัวสำรองหาก Chirp3 ยังไม่เปิดใน Region นั้น
CUSTOMERS = {
    "1": {"name": "น้องฟ้า", "desc": "SuperSmartSave 20/9", "prompt": "คุณคือฟ้า อายุ 25 ค่ะ...", "voice": {"name": "th-TH-Chirp3-HD-Charon", "pitch": 0.0, "rate": 1.0}},
    "2": {"name": "คุณวิรัช", "desc": "Double Sure Health", "prompt": "คุณคือวิรัช อายุ 45 ครับ...", "voice": {"name": "th-TH-Chirp3-HD-Charon", "pitch": 0.0, "rate": 1.0}},
    "3": {"name": "คุณป้ามาลี", "desc": "Wealth 888", "prompt": "คุณคือป้ามาลี ค่ะ/จ๊ะ...", "voice": {"name": "th-TH-Chirp3-HD-Charon", "pitch": 0.0, "rate": 0.9}},
    "4": {"name": "แม่แอน", "desc": "ยาก: ปฏิเสธหนักมาก", "prompt": "คุณคือแอน ปฏิเสธหนักค่ะ...", "voice": {"name": "th-TH-Chirp3-HD-Charon", "pitch": 0.0, "rate": 1.0}},
    "5": {"name": "คุณอัครเดช", "desc": "ยากมาก: นักธุรกิจ", "prompt": "คุณคืออัครเดช เน้นคุ้มค่าครับ...", "voice": {"name": "th-TH-Chirp3-HD-Charon", "pitch": 0.0, "rate": 1.0}}
}

def get_audio_base64(text, voice_config):
    if not TTS_API_KEY: return None
    # ลบอักขระพิเศษออกให้หมด
    clean_text = re.sub(r'[*#_มหาศาล]', '', text)
    clean_text = re.sub(r'\(.*?\)', '', clean_text).strip()
    
    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={TTS_API_KEY}"
    
    # สำหรับ Chirp 3: บางครั้งจะไม่รับค่า pitch/rate ในรูปแบบเดิม 
    # ผมจึงปรับ payload ให้เป็นมาตรฐานที่สุด
    payload = {
        "input": {"text": clean_text},
        "voice": {
            "languageCode": "th-TH",
            "name": voice_config["name"]
        },
        "audioConfig": {
            "audioEncoding": "MP3",
            "speakingRate": voice_config["rate"],
            "pitch": voice_config["pitch"]
        }
    }
    
    try:
        res = requests.post(url, json=payload, timeout=10)
        res_data = res.json()
        
        # ถ้า Error เพราะโมเดล Chirp 3 ไม่ทำงาน ให้สลับไปใช้ Neural2 ทันที (เพื่อไม่ให้เงียบ)
        if "error" in res_data:
            print(f"Chirp3 Error, switching to Neural2: {res_data['error']['message']}")
            payload["voice"]["name"] = "th-TH-Neural2-A"
            res = requests.post(url, json=payload, timeout=10)
            res_data = res.json()
            
        return res_data.get("audioContent")
    except Exception as e:
        print(f"TTS Request Fail: {e}")
        return None

# --- [ส่วนที่ 3: HTML UI - ปรับปรุงการเล่นเสียง] ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Sales Simulator HD</title>
    <style>
        body { font-family: sans-serif; padding: 20px; background: #f0f2f5; }
        .card { background: white; padding: 15px; margin: 10px; border-radius: 8px; cursor: pointer; border-left: 5px solid blue; }
        #chat { height: 300px; overflow-y: auto; background: white; padding: 15px; border: 1px solid #ccc; margin-bottom: 10px; }
        .btn { padding: 15px; background: red; color: white; border: none; border-radius: 50%; width: 70px; height: 70px; cursor: pointer; }
    </style>
</head>
<body>
    <div id="lobby">
        <input type="text" id="name" placeholder="ชื่อพนักงาน">
        {% for k, v in CUSTOMERS.items() %}
        <div class="card" onclick="start('{{k}}')"><b>{{v.name}}</b><br>{{v.desc}}</div>
        {% endfor %}
    </div>

    <div id="app" style="display:none;">
        <div id="chat"></div>
        <button id="mic" class="btn" onclick="listen()">🎤</button>
        <p id="status">กดไมค์เพื่อพูด</p>
    </div>

    <script>
        var history_log = [];
        var activeLvl = "";
        var player = new Audio();
        var recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
        recognition.lang = 'th-TH';

        function start(lvl) {
            if(!document.getElementById('name').value) return alert("ใส่ชื่อก่อน");
            activeLvl = lvl;
            document.getElementById('lobby').style.display='none';
            document.getElementById('app').style.display='block';
        }

        recognition.onresult = (e) => {
            let t = e.results[0][0].transcript;
            send(t);
        };

        async function send(t) {
            document.getElementById('status').innerText = "รอเสียงลูกค้า...";
            document.getElementById('chat').innerHTML += "<div><b>คุณ:</b> "+t+"</div>";
            
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: t, lvl: activeLvl, history: history_log})
            });
            const data = await res.json();
            
            document.getElementById('chat').innerHTML += "<div><b>ลูกค้า:</b> "+data.reply+"</div>";
            history_log.push("พนักงาน: "+t);
            history_log.push("ลูกค้า: "+data.reply);

            if(data.audio) {
                player.src = "data:audio/mp3;base64," + data.audio;
                player.play();
                player.onended = () => { document.getElementById('status').innerText = "คุยต่อได้"; };
            } else {
                document.getElementById('status').innerText = "ไม่มีไฟล์เสียงส่งมา";
            }
        }

        function listen() {
            player.pause();
            recognition.start();
            document.getElementById('status').innerText = "กำลังฟัง...";
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
