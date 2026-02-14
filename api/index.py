import os
import requests
import re
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai

app = Flask(__name__)

# --- [ส่วนที่ 1: ตั้งค่า AI - บังคับใช้ Gemini 2.5 Flash] ---
GENAI_API_KEY = os.environ.get("GENAI_API_KEY")
TTS_API_KEY = os.environ.get("TTS_API_KEY")
genai.configure(api_key=GENAI_API_KEY)
model = genai.GenerativeModel(model_name="gemini-2.5-flash")

# --- [ส่วนที่ 2: ลอจิก Cold Call และ ความจำ] ---
COLD_CALL_RULES = """
คุณคือลูกค้าที่มีความจำดีเยี่ยมและเข้มงวด:
1. [การจดจำ]: คุณต้องอ่านประวัติการสนทนาทั้งหมดอย่างละเอียด หากพนักงานแจ้งชื่อ, เลขใบอนุญาต หรือขออัดเสียงไปแล้ว "ห้ามถามซ้ำ" และ "ห้ามทำเป็นลืม"
2. [คำแทนตัว]: ผู้หญิงใช้ 'ฉัน/เรา', ผู้ชายใช้ 'ผม' (ห้ามเรียกชื่อตัวเอง และห้ามมีหัวข้อชื่อนำหน้าข้อความ)
3. [ลำดับสาย]: เริ่มจากระแวง -> ปฏิเสธ 4-5 รอบ -> ยอมฟังเมื่อพูดถูกต้องตามกฎ คปภ.
"""

# ตั้งค่าลูกค้าโดยใช้ Chirp 3 เป็นตัวหลัก
CUSTOMERS = {
    "1": {"name": "น้องฟ้า", "desc": "SuperSmartSave 20/9", "prompt": COLD_CALL_RULES + "คุณคือ 'ฟ้า' อายุ 25 ปี ลงท้าย 'ค่ะ'", "voice": {"name": "th-TH-Chirp3-HD-Charon", "pitch": 0.0, "rate": 1.05}},
    "2": {"name": "คุณวิรัช", "desc": "Double Sure Health", "prompt": COLD_CALL_RULES + "คุณคือ 'วิรัช' อายุ 45 ปี ลงท้าย 'ครับ'", "voice": {"name": "th-TH-Chirp3-HD-Charon", "pitch": 0.0, "rate": 1.0}},
    "3": {"name": "คุณป้ามาลี", "desc": "Wealth 888", "prompt": COLD_CALL_RULES + "คุณคือ 'ป้ามาลี' ลงท้าย 'ค่ะ/จ๊ะ'", "voice": {"name": "th-TH-Chirp3-HD-Charon", "pitch": 0.0, "rate": 0.9}},
    "4": {"name": "แม่แอน", "desc": "ยาก: ปฏิเสธหนักมาก", "prompt": COLD_CALL_RULES + "คุณคือ 'แอน' ลงท้าย 'ค่ะ'", "voice": {"name": "th-TH-Chirp3-HD-Charon", "pitch": 0.0, "rate": 1.0}},
    "5": {"name": "คุณอัครเดช", "desc": "ยากมาก: นักธุรกิจ", "prompt": COLD_CALL_RULES + "คุณคือ 'อัครเดช' ลงท้าย 'ครับ'", "voice": {"name": "th-TH-Chirp3-HD-Charon", "pitch": 0.0, "rate": 1.0}}
}

def get_audio_base64(text, voice_config):
    if not TTS_API_KEY: return None
    clean_text = re.sub(r'[*#_]', '', text)
    clean_text = re.sub(r'\(.*?\)', '', clean_text).strip()
    if not clean_text: return None
    
    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={TTS_API_KEY}"
    
    # 1. พยายามเรียก Chirp 3 (HD)
    payload = {
        "input": {"text": clean_text},
        "voice": {"languageCode": "th-TH", "name": voice_config["name"]},
        "audioConfig": {"audioEncoding": "MP3", "pitch": voice_config["pitch"], "speakingRate": voice_config["rate"]}
    }
    
    try:
        res = requests.post(url, json=payload, timeout=10)
        res_data = res.json()
        
        # 2. ถ้า Chirp 3 Error (เช่น 403 Forbidden หรือ 400 Bad Request)
        if "error" in res_data:
            print(f"Chirp3 Error: {res_data['error'].get('message')}. Switching to Fallback Voice.")
            # สลับเป็นโมเดลมาตรฐานที่ชัวร์ที่สุด
            payload["voice"]["name"] = "th-TH-Standard-A" 
            res = requests.post(url, json=payload, timeout=10)
            res_data = res.json()
            
        return res_data.get("audioContent")
    except Exception as e:
        print(f"TTS Error: {e}")
        return None

# --- [ส่วนที่ 3: HTML UI] ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Sales Mastery Simulator</title>
    <style>
        :root { --blue: #1e3a8a; --red: #be123c; --gray: #94a3b8; }
        body { font-family: sans-serif; background: #f1f5f9; margin:0; padding: 20px; }
        #lobby { max-width: 500px; margin: auto; text-align: center; }
        .card { background: white; padding: 15px; margin: 10px 0; border-radius: 10px; border-left: 5px solid var(--blue); cursor: pointer; text-align: left; }
        #app { display: none; max-width: 600px; margin: auto; background: white; border-radius: 15px; overflow: hidden; height: 80vh; display: none; flex-direction: column; }
        #chat { flex: 1; overflow-y: auto; padding: 20px; background: #f8fafc; }
        .controls { padding: 20px; border-top: 1px solid #eee; text-align: center; }
        .btn-mic { width: 70px; height: 70px; border-radius: 50%; border: none; background: var(--red); color: white; font-size: 30px; cursor: pointer; }
        .msg { margin-bottom: 10px; padding: 10px; border-radius: 10px; max-width: 80%; }
        .staff { background: var(--blue); color: white; align-self: flex-end; margin-left: auto; }
        .customer { background: #e2e8f0; color: #1e293b; }
    </style>
</head>
<body>
    <div id="lobby">
        <h2>🏆 เลือกบททดสอบ</h2>
        <input type="text" id="staff-name" placeholder="ชื่อพนักงาน" style="width: 100%; padding: 10px; margin-bottom: 10px;">
        <div id="customer-list"></div>
    </div>

    <div id="app">
        <div id="chat" style="display: flex; flex-direction: column;"></div>
        <div class="controls">
            <button id="mic-btn" class="btn-mic" onclick="toggleListen()">🎤</button>
            <p id="status">แตะไมค์เพื่อพูด</p>
        </div>
    </div>

    <script>
        var history_log = [];
        var activeLvl = "";
        var isThinking = false;
        var customers = {{ CUSTOMERS | tojson | safe }};
        var player = new Audio();
        var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        var recognition = new SpeechRecognition();
        recognition.lang = 'th-TH';

        var list = document.getElementById('customer-list');
        for (var k in customers) {
            let lvl = k;
            let d = document.createElement('div');
            d.className = 'card';
            d.innerHTML = '<b>' + customers[lvl].name + '</b><br><small>' + customers[lvl].desc + '</small>';
            d.onclick = () => { startApp(lvl); };
            list.appendChild(d);
        }

        function startApp(lvl) {
            if(!document.getElementById('staff-name').value) return alert("ระบุชื่อก่อน");
            activeLvl = lvl;
            document.getElementById('lobby').style.display = 'none';
            document.getElementById('app').style.display = 'flex';
        }

        recognition.onresult = (e) => {
            let t = e.results[0][0].transcript;
            sendToAI(t);
        };

        async function sendToAI(t) {
            isThinking = true;
            document.getElementById('status').innerText = "⌛ รอการตอบกลับ...";
            let box = document.getElementById('chat');
            box.innerHTML += '<div class="msg staff">' + t + '</div>';
            
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: t, lvl: activeLvl, history: history_log})
            });
            const data = await res.json();
            
            box.innerHTML += '<div class="msg customer"><b>' + customers[activeLvl].name + ':</b> ' + data.reply + '</div>';
            history_log.push("พนักงาน: " + t);
            history_log.push(customers[activeLvl].name + ": " + data.reply);
            box.scrollTop = box.scrollHeight;

            if (data.audio) {
                player.src = "data:audio/mp3;base64," + data.audio;
                player.play();
                player.onended = () => { isThinking = false; document.getElementById('status').innerText = "✅ พร้อมคุยต่อ"; };
            } else {
                isThinking = false;
                document.getElementById('status').innerText = "⚠️ ไม่มีเสียง (เช็ก API Key)";
            }
        }

        function toggleListen() {
            if(isThinking) return;
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
