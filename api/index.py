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

# --- [ส่วนที่ 2: รายชื่อลูกค้า] ---
CUSTOMERS = {
    "1": {"name": "น้องฟ้า (Level 1)", "desc": "ขี้ระแวง - กลัวมิจฉาชีพ", "prompt": "คุณคือ 'ฟ้า' (ผู้หญิง) อายุ 25 ปี พูดลงท้ายว่า 'ค่ะ' เสมอ ตอบสั้นและระแวง", "voice": {"name": "th-TH-Standard-A", "pitch": 2.0, "rate": 1.0}},
    "2": {"name": "คุณวิรัช (Level 2)", "desc": "สุขุม - เน้นความมั่นคง", "prompt": "คุณคือ 'วิรัช' (ผู้ชาย) อายุ 45 ปี พูดลงท้ายว่า 'ครับ' เสมอ ใจเย็นและต้องการเหตุผล", "voice": {"name": "th-TH-Standard-A", "pitch": -4.0, "rate": 0.95}},
    "3": {"name": "คุณป้ามาลี (Level 3)", "desc": "จอมละเอียด - ถามเยอะ", "prompt": "คุณคือ 'ป้ามาลี' (ผู้หญิง) พูดลงท้ายว่า 'ค่ะ/จ๊ะ' ถามจุกจิกเรื่องเงิน", "voice": {"name": "th-TH-Standard-A", "pitch": -1.5, "rate": 0.9}},
    "4": {"name": "แม่แอน (Level 4)", "desc": "คุณแม่ลูกอ่อน - ห่วงลูก", "prompt": "คุณคือ 'แอน' (ผู้หญิง) พูดลงท้ายว่า 'ค่ะ' กังวลค่าใช้จ่ายเพื่อลูก", "voice": {"name": "th-TH-Standard-A", "pitch": 0.5, "rate": 1.0}},
    "5": {"name": "คุณอัครเดช (Level 5)", "desc": "นักธุรกิจใหญ่ - เวลาน้อย", "prompt": "คุณคือ 'อัครเดช' (ผู้ชาย) รวยมาก พูดลงท้ายว่า 'ครับ' เน้นทุนประกันสูงและเร็ว", "voice": {"name": "th-TH-Standard-A", "pitch": -5.0, "rate": 1.0}}
}

def get_audio_base64(text, voice_config):
    if not TTS_API_KEY: return None
    clean_text = re.sub(r'\(.*?\)', '', text).strip()
    url = "https://texttospeech.googleapis.com/v1/text:synthesize?key=" + TTS_API_KEY
    payload = {
        "input": {"text": clean_text},
        "voice": {"languageCode": "th-TH", "name": voice_config["name"]},
        "audioConfig": {"audioEncoding": "MP3", "pitch": voice_config["pitch"], "speakingRate": voice_config["rate"]}
    }
    try:
        res = requests.post(url, json=payload)
        return res.json().get("audioContent")
    except: return None

# --- [ส่วนที่ 3: หน้าเว็บ UI] ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Sales Mastery Academy</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <style>
        :root { --blue: #1e3a8a; --red: #be123c; --gold: #b45309; --gray: #94a3b8; }
        body { font-family: sans-serif; background: #f1f5f9; margin:0; }
        #lobby { padding: 20px; text-align: center; max-width: 600px; margin: auto; }
        .input-group { background: white; padding: 20px; border-radius: 15px; margin-bottom: 20px; }
        input[type="text"] { padding: 15px; width: 85%; border-radius: 8px; border: 1px solid #ddd; font-size: 18px; }
        .cust-card { background: white; padding: 15px; margin: 10px 0; border-radius: 12px; border-left: 8px solid var(--blue); cursor: pointer; text-align: left; }
        #main-app { display: none; flex-direction: column; height: 100vh; background: white; }
        .header { background: var(--blue); color: white; padding: 15px; text-align: center; }
        #chat-box { flex: 1; overflow-y: auto; padding: 15px; display: flex; flex-direction: column; gap: 10px; background: #f8fafc; }
        .msg { padding: 10px 15px; border-radius: 15px; max-width: 85%; }
        .staff { align-self: flex-end; background: var(--blue); color: white; }
        .customer { align-self: flex-start; background: #e2e8f0; }
        .controls { padding: 20px; text-align: center; background: white; border-top: 1px solid #ddd; }
        .btn-mic { width: 90px; height: 90px; border-radius: 50%; border: none; background: var(--red); color: white; font-size: 40px; cursor: pointer; }
        .btn-mic:disabled { background: var(--gray) !important; cursor: not-allowed; opacity: 0.6; }
        #cert-area { display:none; }
        .certificate { width: 800px; height: 550px; padding: 40px; border: 15px double var(--gold); background: white; text-align: center; }
    </style>
</head>
<body>
    <div id="lobby">
        <h1 style="color: var(--blue)">🏆 Sales Mastery Academy</h1>
        <div class="input-group">
            <p>พิมพ์ชื่อพนักงานเพื่อเริ่มฝึก</p>
            <input type="text" id="staff-name" placeholder="ชื่อ-นามสกุล">
        </div>
        <div id="customer-list"></div>
    </div>

    <div id="main-app">
        <div class="header">
            <button onclick="location.reload()" style="float:left; color:white; background:none; border:none; padding:10px;">🏠</button>
            <h2 id="active-cust-name" style="margin:0;">ลูกค้า</h2>
        </div>
        <div id="chat-box"></div>
        <div class="controls">
            <button id="mic-btn" class="btn-mic" onclick="toggleListen()">🎤</button>
            <p id="status" style="margin-top:10px; font-size: 0.9rem;">แตะไมค์เพื่อพูด</p>
            <button id="eval-btn" style="display:none; width:100%; margin-top:15px; padding:12px; border-radius:25px; border:1px solid var(--blue); background:none; color:var(--blue);" onclick="showEvaluation()">🏁 ประเมินผลและรับใบประกาศ</button>
        </div>
    </div>

    <div id="cert-area">
        <div id="certificate" class="certificate">
            <h1 style="color: var(--blue); font-size: 40px;">CERTIFICATE</h1>
            <p style="font-size: 20px;">ขอมอบให้แด่ คุณ <span id="pdf-name"></span></p>
            <p>ผู้ผ่านการทดสอบระดับ: <b id="pdf-lvl"></b></p>
            <p>ณ วันที่ <span id="cert-date"></span></p>
            <p>โดย Sales Mastery Academy</p>
        </div>
    </div>

    <script>
        var history_log = [];
        var activeLvl = "";
        var isProcessing = false;
        var customers = {{ CUSTOMERS | tojson | safe }};
        var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        var recognition = new SpeechRecognition();
        recognition.lang = 'th-TH';
        var player = new Audio();

        var listDiv = document.getElementById('customer-list');
        for (var k in customers) {
            (function(lvl){
                var d = document.createElement('div');
                d.className = 'cust-card';
                d.onclick = function(){ startApp(lvl); };
                d.innerHTML = '<b>Level ' + lvl + ': ' + customers[lvl].name + '</b><br><small>' + customers[lvl].desc + '</small>';
                listDiv.appendChild(d);
            })(k);
        }

        function startApp(lvl) {
            if(!document.getElementById('staff-name').value) { alert("ใส่ชื่อก่อนครับ"); return; }
            activeLvl = lvl;
            document.getElementById('lobby').style.display = 'none';
            document.getElementById('main-app').style.display = 'flex';
            document.getElementById('active-cust-name').innerText = customers[lvl].name;
            var s = new Audio("data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=");
            s.play().catch(function(){});
        }

        recognition.onresult = function(e) {
            var t = e.results[0][0].transcript;
            if (t.length > 1 && !isProcessing) { sendToAI(t); }
        };

        function toggleListen() {
            if (isProcessing) return;
            player.pause();
            recognition.start();
            document.getElementById('mic-btn').style.opacity = "0.5";
            document.getElementById('status').innerText = "👂 กำลังฟัง...";
        }

        async function sendToAI(t) {
            isProcessing = true;
            document.getElementById('mic-btn').disabled = true;
            var box = document.getElementById('chat-box');
            box.innerHTML += '<div class="msg staff"><b>คุณ:</b> ' + t + '</div>';
            history_log.push("พนักงาน: " + t);
            box.scrollTop = box.scrollHeight;

            var res = await fetch('/api/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: t, lvl: activeLvl, history: history_log})
            });
            var data = await res.json();
            box.innerHTML += '<div class="msg customer"><b>' + customers[activeLvl].name + ':</b> ' + data.reply + '</div>';
            history_log.push(customers[activeLvl].name + ": " + data.reply);
            box.scrollTop = box.scrollHeight;

            if (data.audio) {
                player.src = "data:audio/mp3;base64," + data.audio;
                await player.play();
                document.getElementById('status').innerText = "🔈 ลูกค้ากำลังพูด...";
                player.onended = function(){ resetUI(); };
            } else { resetUI(); }
        }

        function resetUI() {
            isProcessing = false;
            document.getElementById('mic-btn').disabled = false;
            document.getElementById('mic-btn').style.opacity = "1";
            document.getElementById('status').innerText = "✅ พร้อมคุยต่อ";
            document.getElementById('eval-btn').style.display = 'block';
        }

        async function showEvaluation() {
            var res = await fetch('/api/evaluate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({history: history_log.join("\\n")})
            });
            var d = await res.json();
            alert("ผลประเมิน:\\n" + d.evaluation);
            
            document.getElementById('pdf-name').innerText = document.getElementById('staff-name').value;
            document.getElementById('pdf-lvl').innerText = customers[activeLvl].name;
            document.getElementById('cert-date').innerText = new Date().toLocaleDateString('th-TH');
            
            var cBtn = document.createElement('button');
            cBtn.innerHTML = "📜 ดาวน์โหลดใบประกาศ PDF";
            cBtn.style = "width:100%; padding:15px; background:var(--gold); color:white; border:none; border-radius:10px; margin-top:10px;";
            cBtn.onclick = function() {
                var el = document.getElementById('cert-area');
                el.style.display = 'block';
                html2pdf().from(el).save().then(function(){ el.style.display = 'none'; });
            };
            document.getElementById('main-app').appendChild(cBtn);
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
    context = "\\n".join(history[-5:])
    full_prompt = "System: " + cust['prompt'] + "\\nHistory: " + context + "\\nUser: " + user_msg
    response = model.generate_content(full_prompt)
    audio_data = get_audio_base64(response.text, cust['voice'])
    return jsonify({"reply": response.text, "audio": audio_data})

@app.route('/api/evaluate', methods=['POST'])
def evaluate():
    history = request.json.get('history', '')
    prompt = "ประเมินบทสนทนานี้และให้คะแนน 1-10: " + history
    evaluation = model.generate_content(prompt).text
    return jsonify({"evaluation": evaluation})

if __name__ == "__main__":
    app.run(debug=True)
