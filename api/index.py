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

# --- [ส่วนที่ 2: ข้อมูลลูกค้า] ---
CUSTOMERS = {
    "1": {"name": "น้องฟ้า (Level 1)", "desc": "ขี้ระแวง - กลัวมิจฉาชีพ", "prompt": "คุณคือ 'ฟ้า' (ผู้หญิง) อายุ 25 ปี พูดลงท้ายว่า 'ค่ะ' เสมอ ตอบสั้นและระแวง", "voice": {"name": "th-TH-Standard-A", "pitch": 2.0, "rate": 1.0}},
    "2": {"name": "คุณวิรัช (Level 2)", "desc": "สุขุม - เน้นความมั่นคง", "prompt": "คุณคือ 'วิรัช' (ผู้ชาย) อายุ 45 ปี พูดลงท้ายว่า 'ครับ' เสมอ ตอบโต้ด้วยเหตุผล", "voice": {"name": "th-TH-Standard-A", "pitch": -4.0, "rate": 0.95}},
    "3": {"name": "คุณป้ามาลี (Level 3)", "desc": "จอมละเอียด - ถามเยอะ", "prompt": "คุณคือ 'ป้ามาลี' (ผู้หญิง) พูดลงท้ายว่า 'ค่ะ/จ๊ะ' ถามจุกจิก", "voice": {"name": "th-TH-Standard-A", "pitch": -1.5, "rate": 0.9}},
    "4": {"name": "แม่แอน (Level 4)", "desc": "คุณแม่ลูกอ่อน - ห่วงลูก", "prompt": "คุณคือ 'แอน' (ผู้หญิง) พูดลงท้ายว่า 'ค่ะ' ห่วงเรื่องลูก", "voice": {"name": "th-TH-Standard-A", "pitch": 0.5, "rate": 1.0}},
    "5": {"name": "คุณอัครเดช (Level 5)", "desc": "นักธุรกิจใหญ่ - เวลาน้อย", "prompt": "คุณคือ 'อัครเดช' (ผู้ชาย) พูดลงท้ายว่า 'ครับ' เน้นทุนประกันสูง", "voice": {"name": "th-TH-Standard-A", "pitch": -5.0, "rate": 1.0}}
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

# --- [ส่วนที่ 3: หน้าเว็บ UI แบบเน้นปุ่มชัดๆ] ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Sales Mastery</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <style>
        :root { --blue: #1e3a8a; --red: #be123c; --gold: #b45309; }
        body { font-family: sans-serif; background: #f1f5f9; margin:0; padding:0; }
        #lobby, #main-app { padding: 20px; max-width: 600px; margin: auto; text-align: center; }
        .input-box { background: white; padding: 20px; border-radius: 15px; margin-bottom: 20px; }
        input { padding: 15px; width: 80%; border-radius: 8px; border: 1px solid #ccc; font-size: 18px; }
        .card { background: white; padding: 20px; margin: 10px 0; border-radius: 12px; border-left: 10px solid var(--blue); text-align: left; cursor: pointer; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        #chat-box { height: 300px; overflow-y: auto; background: #f8fafc; padding: 15px; border-radius: 10px; margin-bottom: 20px; display: flex; flex-direction: column; gap: 10px; }
        .msg { padding: 10px; border-radius: 10px; max-width: 80%; text-align: left; }
        .staff { align-self: flex-end; background: var(--blue); color: white; }
        .customer { align-self: flex-start; background: #e2e8f0; }
        .btn-mic { width: 100px; height: 100px; border-radius: 50%; border: none; background: var(--red); color: white; font-size: 40px; cursor: pointer; }
        #cert-area { display:none; background: white; border: 10px double var(--gold); padding: 30px; text-align: center; }
    </style>
</head>
<body>
    <div id="lobby">
        <h1 style="color: var(--blue)">🏆 Sales Mastery Academy</h1>
        <div class="input-box">
            <p>ระบุชื่อเพื่อรับใบประกาศ</p>
            <input type="text" id="staff-name" placeholder="ชื่อ-นามสกุล">
        </div>
        <div id="customer-list"></div>
    </div>

    <div id="main-app" style="display:none;">
        <h2 id="active-name" style="color: var(--blue)">ลูกค้า</h2>
        <div id="chat-box"></div>
        <button id="mic-btn" class="btn-mic" onclick="toggleListen()">🎤</button>
        <p id="status" style="margin-top:10px;">แตะไมค์เพื่อพูด</p>
        <button id="eval-btn" style="display:none; width:100%; margin-top:20px; padding:15px; background:none; border:2px solid var(--blue); border-radius:30px; color:var(--blue); font-weight:bold;" onclick="showEvaluation()">🏁 ประเมินผลและรับใบประกาศ</button>
    </div>

    <div id="cert-area">
        <h1 style="color: var(--blue)">CERTIFICATE</h1>
        <p>ขอมอบให้แก่</p>
        <h2 id="pdf-name" style="color: var(--red); text-decoration: underline;"></h2>
        <p>ผู้ผ่านการฝึกฝนระดับ</p>
        <h3 id="pdf-lvl" style="color: var(--blue)"></h3>
        <p>โดย Sales Mastery Academy</p>
    </div>

    <script>
        var history_log = [];
        var activeLvl = "";
        var isThinking = false;
        var customers = {{ CUSTOMERS | tojson | safe }};
        
        // ตรวจสอบระบบไมค์
        var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        var recognition = null;
        if (SpeechRecognition) {
            recognition = new SpeechRecognition();
            recognition.lang = 'th-TH';
        }

        var player = new Audio();

        // สร้างรายการลูกค้า
        var list = document.getElementById('customer-list');
        for (var key in customers) {
            (function(k){
                var div = document.createElement('div');
                div.className = 'card';
                div.onclick = function() { startApp(k); };
                div.innerHTML = '<b>Level ' + k + ': ' + customers[k].name + '</b><br><small>' + customers[k].desc + '</small>';
                list.appendChild(div);
            })(key);
        }

        function startApp(k) {
            var n = document.getElementById('staff-name').value;
            if (!n) { alert("กรุณาใส่ชื่อพนักงานครับ"); return; }
            activeLvl = k;
            document.getElementById('lobby').style.display = 'none';
            document.getElementById('main-app').style.display = 'block';
            document.getElementById('active-name').innerText = customers[k].name;
            
            // เปิดระบบเสียง (สำหรับ iPhone)
            var s = new Audio("data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=");
            s.play().catch(function(){});
        }

        if (recognition) {
            recognition.onresult = function(e) {
                var text = e.results[0][0].transcript;
                if (text.length > 0 && !isThinking) { callAI(text); }
            };
            recognition.onend = function() {
                document.getElementById('mic-btn').style.opacity = "1";
            };
        }

        function toggleListen() {
            if (isThinking) return;
            if (!recognition) { alert("เครื่องนี้ไม่รองรับระบบเสียง"); return; }
            player.pause();
            recognition.start();
            document.getElementById('mic-btn').style.opacity = "0.5";
            document.getElementById('status').innerText = "👂 กำลังฟัง...";
        }

        async function callAI(t) {
            isThinking = true;
            document.getElementById('mic-btn').disabled = true;
            var box = document.getElementById('chat-box');
            box.innerHTML += '<div class="msg staff"><b>คุณ:</b> ' + t + '</div>';
            history_log.push("พนักงาน: " + t);
            box.scrollTop = box.scrollHeight;

            try {
                var res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: t, lvl: activeLvl, history: history_log})
                });
                var d = await res.json();
                box.innerHTML += '<div class="msg customer"><b>' + customers[activeLvl].name + ':</b> ' + d.reply + '</div>';
                history_log.push(customers[activeLvl].name + ": " + d.reply);
                box.scrollTop = box.scrollHeight;

                if (d.audio) {
                    player.src = "data:audio/mp3;base64," + d.audio;
                    await player.play();
                    document.getElementById('status').innerText = "🔈 ลูกค้ากำลังตอบ...";
                    player.onended = function() { done(); };
                } else { done(); }
            } catch (e) { done(); }
        }

        function done() {
            isThinking = false;
            document.getElementById('mic-btn').disabled = false;
            document.getElementById('mic-btn').style.opacity = "1";
            document.getElementById('status').innerText = "✅ พร้อมคุยต่อ แตะไมค์เลยครับ";
            document.getElementById('eval-btn').style.display = 'block';
        }

        async function showEvaluation() {
            var box = document.getElementById('chat-box');
            box.innerHTML += '<p style="text-align:center;">⌛ กำลังประเมินผล...</p>';
            var res = await fetch('/api/evaluate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({history: history_log.join("\\n")})
            });
            var d = await res.json();
            alert("ผลประเมิน:\\n" + d.evaluation);
            
            // เตรียมใบประกาศ
            document.getElementById('pdf-name').innerText = document.getElementById('staff-name').value;
            document.getElementById('pdf-lvl').innerText = customers[activeLvl].name;
            
            var certBtn = document.createElement('button');
            certBtn.innerHTML = "📜 ดาวน์โหลดใบประกาศ PDF";
            certBtn.style = "width:100%; padding:15px; background:var(--gold); color:white; border:none; border-radius:10px; margin-top:10px;";
            certBtn.onclick = function() {
                var el = document.getElementById('cert-area');
                el.style.display = 'block';
                html2pdf().from(el).save().then(function(){ el.style.display = 'none'; });
            };
            document.getElementById('main-app').appendChild(certBtn);
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
    prompt = "ประเมินการสนทนานี้และให้คะแนน 1-10: " + history
    evaluation = model.generate_content(prompt).text
    return jsonify({"evaluation": evaluation})

if __name__ == "__main__":
    app.run(debug=True)
