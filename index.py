import os
import requests
import re
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai

app = Flask(__name__)

# --- [ส่วนที่ 1: ตั้งค่า AI - ใช้ API Key ใหม่จาก Google Cloud] ---
GENAI_API_KEY = os.environ.get("GENAI_API_KEY")
TTS_API_KEY = os.environ.get("TTS_API_KEY")
genai.configure(api_key=GENAI_API_KEY)

# บังคับใช้ Gemini 2.5 Flash ตามความต้องการของคุณ
model = genai.GenerativeModel(model_name="gemini-2.5-flash")

# --- [ส่วนที่ 2: ลอจิกการขายประกัน (Cold Call) และความจำ] ---
COLD_CALL_RULES = """
คุณคือลูกค้าที่มีความจำดีเยี่ยมและเข้มงวด:
1. [การจดจำ]: คุณต้องอ่านประวัติการสนทนาทั้งหมดอย่างละเอียด หากพนักงานแจ้งชื่อ, เลขใบอนุญาต หรือขออัดเสียงไปแล้ว "ห้ามถามซ้ำ" และ "ห้ามทำเป็นลืม"
2. [คำแทนตัว]: ผู้หญิงใช้ 'ฉัน/เรา', ผู้ชายใช้ 'ผม' (ห้ามเรียกชื่อตัวเอง และห้ามมีหัวข้อชื่อนำหน้าข้อความ)
3. [ลำดับสาย]: เริ่มจากระแวง -> ปฏิเสธ 4-5 รอบ -> ยอมฟังเมื่อพูดถูกต้องตามกฎ คปภ.
"""

# ตั้งค่าลูกค้าโดยใช้โมเดลเสียง Neural2 (A = หญิง, B = ชาย) เพื่อความเป็นธรรมชาติ
CUSTOMERS = {
    "1": {
        "name": "น้องฟ้า", 
        "desc": "SuperSmartSave 20/9", 
        "prompt": COLD_CALL_RULES + "คุณคือ 'ฟ้า' อายุ 25 ปี ลงท้าย 'ค่ะ' ถามเรื่องออมเงิน", 
        "voice": {"name": "th-TH-Neural2-A", "pitch": 0.8, "rate": 1.05}
    },
    "2": {
        "name": "คุณวิรัช", 
        "desc": "Double Sure Health", 
        "prompt": COLD_CALL_RULES + "คุณคือ 'วิรัช' อายุ 45 ปี ลงท้าย 'ครับ' ถามเรื่องสุขภาพ", 
        "voice": {"name": "th-TH-Neural2-B", "pitch": -0.5, "rate": 1.0}
    },
    "3": {
        "name": "คุณป้ามาลี", 
        "desc": "Wealth 888", 
        "prompt": COLD_CALL_RULES + "คุณคือ 'ป้ามาลี' ลงท้าย 'ค่ะ/จ๊ะ' ถามเรื่องมรดก", 
        "voice": {"name": "th-TH-Neural2-A", "pitch": -2.0, "rate": 0.9}
    },
    "4": {
        "name": "แม่แอน", 
        "desc": "ยาก: ปฏิเสธหนักมาก", 
        "prompt": COLD_CALL_RULES + "คุณคือ 'แอน' ยุ่งมากและปฏิเสธเก่ง", 
        "voice": {"name": "th-TH-Neural2-A", "pitch": 0.0, "rate": 1.0}
    },
    "5": {
        "name": "คุณอัครเดช", 
        "desc": "ยากมาก: นักธุรกิจ (ปิดการขายยาก)", 
        "prompt": COLD_CALL_RULES + "คุณคือ 'อัครเดช' เน้นความคุ้มค่าและเวลาน้อย", 
        "voice": {"name": "th-TH-Neural2-B", "pitch": -1.2, "rate": 1.05}
    }
}

def get_audio_base64(text, voice_config):
    if not TTS_API_KEY: return None
    # ลบส่วนหัวข้อออกเพื่อให้เสียงอ่านลื่นไหล
    clean_text = re.sub(r'^.*?:', '', text)
    clean_text = re.sub(r'\(.*?\)', '', clean_text).strip()
    if not clean_text: return None

    # เรียกใช้ Google Cloud Text-to-Speech API
    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={TTS_API_KEY}"
    payload = {
        "input": {"text": clean_text},
        "voice": {"languageCode": "th-TH", "name": voice_config["name"]},
        "audioConfig": {
            "audioEncoding": "MP3", 
            "pitch": voice_config["pitch"], 
            "speakingRate": voice_config["rate"],
            "sampleRateHertz": 44100
        }
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.json().get("audioContent")
    except:
        return None

# --- [ส่วนที่ 3: HTML UI - โครงสร้างเดิมที่คุณคุ้นเคย] ---
# (ใช้ HTML_TEMPLATE เดิมของคุณได้เลย แต่เปลี่ยนปุ่มไมค์ให้ดูทันสมัยขึ้น)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <title>Telesales Simulator AI HD</title>
    <style>
        :root { --blue: #1e3a8a; --red: #be123c; }
        body { font-family: sans-serif; background: #f1f5f9; padding: 20px; }
        .card { background: white; padding: 15px; margin: 10px 0; border-radius: 12px; border-left: 8px solid var(--blue); cursor: pointer; text-align: left; }
        #chat-box { height: 400px; overflow-y: auto; background: white; padding: 15px; border-radius: 10px; margin-bottom: 20px; border: 1px solid #ddd; }
        .btn-mic { width: 80px; height: 80px; border-radius: 50%; border: none; background: var(--red); color: white; font-size: 35px; cursor: pointer; }
        .msg { margin-bottom: 10px; padding: 10px; border-radius: 10px; max-width: 80%; }
        .staff { background: var(--blue); color: white; margin-left: auto; }
        .customer { background: #e2e8f0; }
    </style>
</head>
<body>
    <div id="lobby">
        <h1>🏆 Telesales Simulator AI</h1>
        <input type="text" id="staff-name" placeholder="ระบุชื่อพนักงาน" style="width: 100%; padding: 12px; margin-bottom: 10px;">
        <div id="customer-list"></div>
    </div>

    <div id="main-app" style="display:none;">
        <h2 id="active-name"></h2>
        <div id="chat-box" style="display:flex; flex-direction:column;"></div>
        <div style="text-align:center;">
            <button class="btn-mic" onclick="toggleListen()">🎤</button>
            <p id="status">แตะไมค์เพื่อพูด</p>
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
            d.innerHTML = '<b>'+custs[lvl].name+'</b><br><small>'+custs[lvl].desc+'</small>';
            d.onclick = function() {
                if(!document.getElementById('staff-name').value) return alert("ระบุชื่อก่อนครับ");
                activeLvl = lvl;
                document.getElementById('lobby').style.display='none';
                document.getElementById('main-app').style.display='block';
                document.getElementById('active-name').innerText = "ลูกค้า: " + custs[lvl].name;
            };
            list.appendChild(d);
        }

        recognition.onresult = function(e) {
            var t = e.results[0][0].transcript;
            sendToAI(t);
        };

        async function sendToAI(t) {
            document.getElementById('status').innerText = "⌛ ลูกค้ากำลังคิด...";
            document.getElementById('chat-box').innerHTML += '<div class="msg staff"><b>คุณ:</b> '+t+'</div>';
            
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: t, lvl: activeLvl, history: history_log})
            });
            const data = await res.json();
            
            document.getElementById('chat-box').innerHTML += '<div class="msg customer"><b>'+custs[activeLvl].name+':</b> '+data.reply+'</div>';
            history_log.push("พนักงาน: "+t);
            history_log.push(custs[activeLvl].name + ": " + data.reply);
            document.getElementById('chat-box').scrollTop = document.getElementById('chat-box').scrollHeight;

            if (data.audio) {
                player.src = "data:audio/mp3;base64," + data.audio;
                player.play();
                player.onended = () => { document.getElementById('status').innerText = "✅ พร้อมคุยต่อ"; };
            }
        }

        function toggleListen() {
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
    context = "\\n".join(history)
    full_prompt = f"System: {cust['prompt']}\\nHistory:\\n{context}\\nUser: {user_msg}"
    response = model.generate_content(full_prompt)
    reply_text = response.text
    audio_data = get_audio_base64(reply_text, cust['voice'])
    return jsonify({"reply": reply_text, "audio": audio_data})

if __name__ == "__main__":
    app.run(debug=True)
