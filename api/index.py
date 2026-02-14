import os
import requests
import re
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai

app = Flask(__name__)

# --- [ส่วนที่ 1: ตั้งค่า AI - ใช้รหัสจากโปรเจกต์ Postsitive] ---
# แนะนำให้ใช้ API Key 1 จากโปรเจกต์ new-record-3ccd6 ใน Vercel
GENAI_API_KEY = os.environ.get("GENAI_API_KEY") 
TTS_API_KEY = os.environ.get("TTS_API_KEY")

genai.configure(api_key=GENAI_API_KEY)
# บังคับใช้ Gemini 2.5 Flash ตามแผนงานของคุณ
model = genai.GenerativeModel(model_name="gemini-2.5-flash")

# --- [ส่วนที่ 2: ลอจิก Cold Call และ ความจำ] ---
COLD_CALL_RULES = """
คุณคือลูกค้าที่มีความจำดีเยี่ยมและเข้มงวด:
1. [การจดจำ]: คุณต้องอ่านประวัติการสนทนาทั้งหมดอย่างละเอียด หากพนักงานแจ้งชื่อ, เลขใบอนุญาต หรือขออัดเสียงไปแล้ว "ห้ามถามซ้ำ" และ "ห้ามทำเป็นลืม"
2. [คำแทนตัว]: ผู้หญิงใช้ 'ฉัน/เรา', ผู้ชายใช้ 'ผม' (ห้ามเรียกชื่อตัวเอง และห้ามมีหัวข้อชื่อนำหน้าข้อความ)
3. [ลำดับสาย]: เริ่มจากระแวง -> ปฏิเสธ 4-5 รอบ -> ยอมฟังเมื่อพูดถูกต้องตามกฎ คปภ.
"""

# ปรับปรุงเสียงลูกค้าให้เป็นธรรมชาติด้วย Neural2 (หรือ Chirp 3 หากเปิด API แล้ว)
CUSTOMERS = {
    "1": {"name": "น้องฟ้า", "desc": "SuperSmartSave 20/9", "prompt": COLD_CALL_RULES + "คุณคือ 'ฟ้า' อายุ 25 ปี ลงท้าย 'ค่ะ'", "voice": {"name": "th-TH-Neural2-A", "pitch": 1.0, "rate": 1.05}},
    "2": {"name": "คุณวิรัช", "desc": "Double Sure Health", "prompt": COLD_CALL_RULES + "คุณคือ 'วิรัช' อายุ 45 ปี ลงท้าย 'ครับ'", "voice": {"name": "th-TH-Neural2-B", "pitch": -1.0, "rate": 1.0}},
    "3": {"name": "คุณป้ามาลี", "desc": "Wealth 888", "prompt": COLD_CALL_RULES + "คุณคือ 'ป้ามาลี' ลงท้าย 'ค่ะ/จ๊ะ'", "voice": {"name": "th-TH-Neural2-A", "pitch": -2.0, "rate": 0.9}},
    "4": {"name": "แม่แอน", "desc": "ยาก: ปฏิเสธหนักมาก", "prompt": COLD_CALL_RULES + "คุณคือ 'แอน' ลงท้าย 'ค่ะ'", "voice": {"name": "th-TH-Neural2-A", "pitch": 0.5, "rate": 1.1}},
    "5": {"name": "คุณอัครเดช", "desc": "ยากมาก: นักธุรกิจ", "prompt": COLD_CALL_RULES + "คุณคือ 'อัครเดช' ลงท้าย 'ครับ'", "voice": {"name": "th-TH-Neural2-B", "pitch": -2.0, "rate": 1.05}}
}

def get_audio_base64(text, voice_config):
    if not TTS_API_KEY: return None
    # ลบสัญลักษณ์พิเศษเพื่อให้ AI อ่านลื่นไหล
    clean_text = re.sub(r'[*#_]', '', text)
    clean_text = re.sub(r'\(.*?\)', '', clean_text).strip()
    if not clean_text: return None
    
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
    except: return None

# --- [ส่วนที่ 3: UI และ JavaScript (โครงสร้างเดิม)] ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Sales Mastery Simulator HD</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <style>
        :root { --blue: #1e3a8a; --red: #be123c; --gray: #94a3b8; --gold: #b45309; }
        body { font-family: sans-serif; background: #f1f5f9; margin:0; }
        #lobby { padding: 20px; text-align: center; max-width: 600px; margin: auto; }
        input { padding: 15px; width: 85%; border-radius: 8px; border: 1px solid #ddd; font-size: 18px; margin-bottom: 20px; }
        .card { background: white; padding: 15px; margin: 10px 0; border-radius: 12px; border-left: 8px solid var(--blue); text-align: left; cursor: pointer; }
        #main-app { display: none; flex-direction: column; height: 100vh; background: white; }
        .header { background: var(--blue); color: white; padding: 15px; text-align: center; }
        #chat-box { flex: 1; overflow-y: auto; padding: 15px; display: flex; flex-direction: column; gap: 10px; background: #f8fafc; }
        .msg { padding: 10px 15px; border-radius: 15px; max-width: 85%; line-height: 1.4; }
        .staff { align-self: flex-end; background: var(--blue); color: white; }
        .customer { align-self: flex-start; background: #e2e8f0; color: #1e293b; }
        .controls { padding: 20px; text-align: center; background: white; border-top: 1px solid #ddd; }
        .btn-mic { width: 90px; height: 90px; border-radius: 50%; border: none; background: var(--red); color: white; font-size: 40px; cursor: pointer; }
    </style>
</head>
<body>
    <div id="lobby">
        <h1 style="color: var(--blue)">🏆 Sales Mastery HD</h1>
        <input type="text" id="staff-name" placeholder="ระบุชื่อพนักงาน">
        <div id="customer-list"></div>
    </div>

    <div id="main-app">
        <div class="header"><h2 id="active-name" style="margin:0;">ลูกค้า</h2></div>
        <div id="chat-box"></div>
        <div class="controls">
            <button id="mic-btn" class="btn-mic" onclick="toggleListen()">🎤</button>
            <p id="status" style="margin-top:10px;">แตะไมค์เพื่อพูด</p>
            <button id="eval-btn" style="display:none; width:100%; padding:15px; border-radius:30px; border:2px solid var(--blue); color:var(--blue); background:none; font-weight:bold; margin-top:10px;" onclick="showEvaluation()">🏁 ประเมินผล</button>
        </div>
    </div>

    <script>
        var history_log = [];
        var activeLvl = "";
        var isThinking = false;
        var customers = {{ CUSTOMERS | tojson | safe }};
        var player = new Audio();
        var recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
        recognition.lang = 'th-TH';

        var list = document.getElementById('customer-list');
        for (var k in customers) {
            (function(lvl){
                var d = document.createElement('div');
                d.className = 'card';
                d.onclick = function(){
                    if(!document.getElementById('staff-name').value) return alert("ระบุชื่อก่อนครับ");
                    activeLvl = lvl;
                    document.getElementById('lobby').style.display = 'none';
                    document.getElementById('main-app').style.display = 'flex';
                    document.getElementById('active-name').innerText = customers[lvl].name;
                };
                d.innerHTML = '<b>' + customers[lvl].name + '</b><br><small>' + customers[lvl].desc + '</small>';
                list.appendChild(d);
            })(k);
        }

        recognition.onresult = function(e) {
            var t = e.results[0][0].transcript;
            sendToAI(t);
        };

        function toggleListen() {
            if (isThinking) return;
            player.pause();
            recognition.start();
            document.getElementById('status').innerText = "🔴 กำลังฟัง...";
        }

        async function sendToAI(t) {
            isThinking = true;
            document.getElementById('status').innerText = "⌛ ลูกค้ากำลังคิด...";
            var box = document.getElementById('chat-box');
            box.innerHTML += '<div class="msg staff"><b>คุณ:</b> ' + t + '</div>';
            
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
                player.onended = function() { 
                    isThinking = false; 
                    document.getElementById('status').innerText = "✅ พร้อมคุยต่อ";
                    document.getElementById('eval-btn').style.display = 'block';
                };
            } else { isThinking = false; }
        }
    </script>
</body>
</html>
"""

# --- [ส่วนที่ 4: เชื่อมต่อ API] ---
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
    # เรียกใช้ฟังก์ชัน TTS ด้วยกุญแจใหม่
    audio_data = get_audio_base64(reply_text, cust['voice'])
    return jsonify({"reply": reply_text, "audio": audio_data})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
