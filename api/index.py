import os
import requests
import re
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai

app = Flask(__name__)

# --- [ส่วนที่ 1: ตั้งค่า API] ---
GENAI_API_KEY = os.environ.get("GENAI_API_KEY")
TTS_API_KEY = os.environ.get("TTS_API_KEY")
genai.configure(api_key=GENAI_API_KEY)
model = genai.GenerativeModel(model_name="gemini-2.5-flash")

# --- [ส่วนที่ 2: ตั้งค่าเสียงระดับพรีเมียม (Neural2)] ---
# ผมเลือก Neural2-A สำหรับผู้หญิง และ Neural2-B สำหรับผู้ชาย เพราะเนียนที่สุดในตอนนี้
CUSTOMERS = {
    "1": {"name": "น้องฟ้า", "desc": "วัยรุ่น - SuperSmartSave 20/9", 
          "prompt": "คุณคือ 'ฟ้า' อายุ 25 ปี ลงท้าย 'ค่ะ' คุยแบบคนรุ่นใหม่", 
          "voice": {"name": "th-TH-Neural2-A", "pitch": 1.2, "rate": 1.05}},
    
    "2": {"name": "คุณวิรัช", "desc": "วัยทำงาน - Double Sure Health", 
          "prompt": "คุณคือ 'วิรัช' อายุ 45 ปี ลงท้าย 'ครับ' เสียงเข้มขรึม", 
          "voice": {"name": "th-TH-Neural2-B", "pitch": -1.0, "rate": 1.0}},
    
    "3": {"name": "คุณป้ามาลี", "desc": "ผู้สูงอายุ - Wealth 888", 
          "prompt": "คุณคือ 'ป้ามาลี' ลงท้าย 'ค่ะ/จ๊ะ' พูดช้าๆ ใจดี", 
          "voice": {"name": "th-TH-Neural2-A", "pitch": -2.5, "rate": 0.85}},
    
    "4": {"name": "แม่แอน", "desc": "คุณแม่ - ยาก: ปฏิเสธหนัก", 
          "prompt": "คุณคือ 'แอน' คุณแม่ลูกอ่อน ยุ่งตลอดเวลา", 
          "voice": {"name": "th-TH-Neural2-A", "pitch": 0.5, "rate": 1.1}},
    
    "5": {"name": "คุณอัครเดช", "desc": "นักธุรกิจ - ยากมาก: เน้นคุ้มค่า", 
          "prompt": "คุณคือ 'อัครเดช' นักธุรกิจมาดเนี้ยบ พูดจาฉะฉาน", 
          "voice": {"name": "th-TH-Neural2-B", "pitch": -0.5, "rate": 1.05}}
}

def get_audio_base64(text, voice_config):
    if not TTS_API_KEY: return None
    # ลบสัญลักษณ์พิเศษออกเพื่อให้ AI อ่านไม่สะดุด
    clean_text = re.sub(r'[*#_]', '', text)
    clean_text = re.sub(r'\(.*?\)', '', clean_text).strip()
    
    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={TTS_API_KEY}"
    
    payload = {
        "input": {"text": clean_text},
        "voice": {
            "languageCode": "th-TH", 
            "name": voice_config["name"]
        },
        "audioConfig": {
            "audioEncoding": "MP3", 
            "pitch": voice_config["pitch"], 
            "speakingRate": voice_config["rate"]
        }
    }
    
    try:
        res = requests.post(url, json=payload, timeout=7)
        return res.json().get("audioContent")
    except:
        return None

# --- [ส่วนที่ 3: HTML UI (แบบเน้นความเร็ว)] ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <title>Sales Mastery Simulator Pro</title>
    <style>
        body { font-family: sans-serif; background: #f0f4f8; margin: 0; padding: 20px; text-align: center; }
        .container { max-width: 500px; margin: auto; background: white; padding: 20px; border-radius: 20px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); }
        .card { background: #fff; border: 1px solid #e2e8f0; padding: 15px; margin: 10px 0; border-radius: 12px; cursor: pointer; border-left: 6px solid #1e3a8a; text-align: left; }
        #chat { height: 350px; overflow-y: auto; text-align: left; padding: 10px; background: #f8fafc; margin-bottom: 20px; border-radius: 10px; }
        .btn-mic { width: 80px; height: 80px; border-radius: 50%; border: none; background: #be123c; color: white; font-size: 30px; cursor: pointer; }
        .msg { margin-bottom: 12px; line-height: 1.4; }
    </style>
</head>
<body>
    <div id="lobby" class="container">
        <h2 style="color: #1e3a8a">🏆 Sales Simulator Pro</h2>
        <input type="text" id="staff" placeholder="ชื่อพนักงาน" style="width: 90%; padding: 12px; margin-bottom: 15px; border-radius: 8px; border: 1px solid #cbd5e1;">
        <div id="list"></div>
    </div>

    <div id="app" class="container" style="display:none;">
        <h3 id="c-name" style="color: #1e3a8a"></h3>
        <div id="chat"></div>
        <button id="mic" class="btn-mic" onclick="listen()">🎤</button>
        <p id="status">แตะไมค์เพื่อพูด</p>
    </div>

    <script>
        var history_log = [];
        var activeLvl = "";
        var player = new Audio();
        var recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
        recognition.lang = 'th-TH';

        var custs = {{ CUSTOMERS | tojson | safe }};
        var listDiv = document.getElementById('list');
        for (let k in custs) {
            let d = document.createElement('div');
            d.className = 'card';
            d.innerHTML = '<b>' + custs[k].name + '</b><br><small>' + custs[k].desc + '</small>';
            d.onclick = () => {
                if(!document.getElementById('staff').value) return alert("ระบุชื่อก่อน");
                activeLvl = k;
                document.getElementById('lobby').style.display='none';
                document.getElementById('app').style.display='block';
                document.getElementById('c-name').innerText = "คุยกับ: " + custs[k].name;
            };
            listDiv.appendChild(d);
        }

        recognition.onresult = (e) => {
            let t = e.results[0][0].transcript;
            talk(t);
        };

        async function talk(t) {
            document.getElementById('status').innerText = "⌛ ลูกค้ากำลังคิด...";
            document.getElementById('chat').innerHTML += "<div><b>คุณ:</b> "+t+"</div>";
            
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: t, lvl: activeLvl, history: history_log})
            });
            const data = await res.json();
            
            document.getElementById('chat').innerHTML += "<div><b>"+custs[activeLvl].name+":</b> "+data.reply+"</div>";
            document.getElementById('chat').scrollTop = document.getElementById('chat').scrollHeight;
            history_log.push("พนักงาน: "+t);
            history_log.push(custs[activeLvl].name + ": " + data.reply);

            if(data.audio) {
                player.src = "data:audio/mp3;base64," + data.audio;
                player.play();
                player.onended = () => { document.getElementById('status').innerText = "✅ คุยต่อได้"; };
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
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
