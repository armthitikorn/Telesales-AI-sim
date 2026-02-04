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

# --- [ส่วนที่ 2: ข้อมูลลูกค้าและลอจิก Cold Call] ---
COLD_CALL_RULES = """
คุณคือลูกค้าที่พนักงานโทรหา (Cold Call) ห้ามใจอ่อนง่ายๆ:
1. [เริ่มสาย]: ตอบแค่ 'สวัสดีค่ะ/ครับ' หรือ 'ใครคะ/ครับ?' ห้ามรู้ว่าเขามาขายอะไร
2. [เมื่อรู้ว่ามาขาย]: ถาม 'เอาเบอร์มาจากไหน?' หรือ 'ได้เบอร์มาจากที่ไหน?'
3. [การปฏิเสธ]: ต้องปฏิเสธอย่างน้อย 4 รอบ เช่น 'มีเยอะแล้ว', 'ยุ่งอยู่', 'ส่งเอกสารมาพอ', 'ไม่สนใจ'
4. [เงื่อนไข]: ห้ามยอมฟังจนกว่าพนักงานจะแจ้ง ชื่อ-นามสกุล, บ.พรูเด็นเชียล, เลขใบอนุญาต และขออัดเสียง ครบถ้วน
5. [การคุย]: ตอบโต้ครั้งละ 1-2 ประโยค ไม่สั้นกุดและไม่ยาวเกินไป
"""

CUSTOMERS = {
    "1": {"name": "น้องฟ้า (Level 1)", "desc": "Product: SuperSmartSave 20/9", "prompt": COLD_CALL_RULES + " เมื่อพนักงานเปิดใจสำเร็จ ให้ถามเรื่อง SuperSmartSave 20/9 ลงท้าย 'ค่ะ'", "voice": {"name": "th-TH-Standard-A", "pitch": 2.0, "rate": 1.0}},
    "2": {"name": "คุณวิรัช (Level 2)", "desc": "Product: Double Sure Health", "prompt": COLD_CALL_RULES + " เมื่อพนักงานเปิดใจสำเร็จ ให้ถามเรื่องสุขภาพเหมาจ่าย Double Sure ลงท้าย 'ครับ'", "voice": {"name": "th-TH-Standard-A", "pitch": -4.0, "rate": 0.95}},
    "3": {"name": "คุณป้ามาลี (Level 3)", "desc": "Product: Wealth 888", "prompt": COLD_CALL_RULES + " เมื่อพนักงานเปิดใจสำเร็จ ให้ถามเรื่อง Wealth 888 เก็บเงินให้หลาน ลงท้าย 'ค่ะ/จ๊ะ'", "voice": {"name": "th-TH-Standard-A", "pitch": -1.5, "rate": 0.9}},
    "4": {"name": "แม่แอน (Level 4)", "desc": "ยาก: ปฏิเสธหนัก (สุ่ม Product)", "prompt": COLD_CALL_RULES + " ปฏิเสธหนักมาก พนักงานต้องแก้ข้อโต้แย้งอย่างมืออาชีพถึงจะยอมฟัง ลงท้าย 'ค่ะ'", "voice": {"name": "th-TH-Standard-A", "pitch": 0.5, "rate": 1.0}},
    "5": {"name": "คุณอัครเดช (Level 5)", "desc": "ยากมาก: นักธุรกิจ (รับใบเซอร์)", "prompt": COLD_CALL_RULES + " เวลาน้อยมาก ถ้าพนักงานพูดจาไม่ชัดเจนหรือผิดกฎ คปภ. ให้วางสายทันที ลงท้าย 'ครับ'", "voice": {"name": "th-TH-Standard-A", "pitch": -5.0, "rate": 1.0}}
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

# --- [ส่วนที่ 3: UI และ JavaScript สำหรับ iPhone และไมค์สีเทา] ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Sales Mastery Simulator</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <style>
        :root { --blue: #1e3a8a; --red: #be123c; --gray: #94a3b8; --gold: #b45309; }
        body { font-family: sans-serif; background: #f1f5f9; margin:0; }
        #lobby { padding: 20px; text-align: center; max-width: 600px; margin: auto; }
        input { padding: 15px; width: 85%; border-radius: 8px; border: 2px solid #ddd; font-size: 18px; margin-bottom: 20px; }
        .card { background: white; padding: 15px; margin: 10px 0; border-radius: 12px; border-left: 8px solid var(--blue); text-align: left; cursor: pointer; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        #main-app { display: none; flex-direction: column; height: 100vh; background: white; }
        .header { background: var(--blue); color: white; padding: 15px; text-align: center; border-bottom: 4px solid var(--red); }
        #chat-box { flex: 1; overflow-y: auto; padding: 15px; display: flex; flex-direction: column; gap: 10px; background: #f8fafc; }
        .msg { padding: 10px 15px; border-radius: 15px; max-width: 85%; line-height: 1.4; }
        .staff { align-self: flex-end; background: var(--blue); color: white; }
        .customer { align-self: flex-start; background: #e2e8f0; color: #1e293b; }
        .controls { padding: 20px; text-align: center; background: white; border-top: 1px solid #ddd; }
        .btn-mic { width: 90px; height: 90px; border-radius: 50%; border: none; background: var(--red); color: white; font-size: 40px; cursor: pointer; }
        .btn-mic:disabled { background: var(--gray) !important; cursor: not-allowed; opacity: 0.6; }
        #cert-area { display:none; }
        .certificate { width: 800px; height: 550px; padding: 40px; border: 15px double var(--gold); background: white; text-align: center; }
    </style>
</head>
<body>
    <div id="lobby">
        <h1 style="color: var(--blue)">🎖️ Sales Mastery Simulator</h1>
        <input type="text" id="staff-name" placeholder="ระบุชื่อพนักงาน">
        <div id="customer-list"></div>
    </div>

    <div id="main-app">
        <div class="header">
            <button onclick="location.reload()" style="float:left; color:white; background:none; border:none; font-size: 20px;">🏠</button>
            <h2 id="active-name" style="margin:0;">ลูกค้า</h2>
        </div>
        <div id="chat-box"></div>
        <div class="controls">
            <button id="mic-btn" class="btn-mic" onclick="toggleListen()">🎤</button>
            <p id="status" style="margin-top:10px; font-size: 0.9rem;">แตะไมค์เพื่อพูด</p>
            <button id="eval-btn" style="display:none; width:100%; margin-top:20px; padding:15px; border-radius:30px; border:2px solid var(--blue); background:none; color:var(--blue); font-weight:bold;" onclick="showEvaluation()">🏁 ประเมินผล</button>
        </div>
    </div>

    <div id="cert-area">
        <div id="certificate" class="certificate">
            <h1 style="color: var(--blue); font-size: 40px;">CERTIFICATE</h1>
            <p style="font-size: 20px;">ขอมอบให้แก่ คุณ <span id="pdf-staff"></span></p>
            <p style="font-size: 20px;">ผู้ผ่านการทดสอบระดับสูงสุด (Level 5)</p>
            <p style="margin-top: 50px;">ออกให้ ณ วันที่ <span id="cert-date"></span><br>โดย Sales Mastery Academy</p>
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

        // แสดงรายชื่อลูกค้า
        var list = document.getElementById('customer-list');
        for (var lvl in customers) {
            (function(k){
                var d = document.createElement('div');
                d.className = 'card';
                d.onclick = function(){ startChat(k); };
                d.innerHTML = '<b>' + customers[k].name + '</b><br><small>' + customers[k].desc + '</small>';
                list.appendChild(d);
            })(lvl);
        }

        function startChat(lvl) {
            if(!document.getElementById('staff-name').value) { alert("กรุณาใส่ชื่อพนักงาน"); return; }
            activeLvl = lvl;
            document.getElementById('lobby').style.display = 'none';
            document.getElementById('main-app').style.display = 'flex';
            document.getElementById('active-name').innerText = customers[lvl].name;
            unlockAudio();
        }

        function unlockAudio() {
            var s = new Audio("data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=");
            s.play().catch(function(){});
        }

        recognition.onresult = function(e) {
            var t = e.results[0][0].transcript;
            if (t.length > 1 && !isProcessing) { sendToAI(t); }
        };

        function toggleListen() {
            if (isProcessing) return;
            unlockAudio();
            player.pause();
            recognition.start();
            document.getElementById('mic-btn').style.opacity = "0.5";
        }

        async function sendToAI(text) {
            isProcessing = true;
            document.getElementById('mic-btn').disabled = true;
            document.getElementById('status').innerText = "⌛ ลูกค้ากำลังคิด...";
            
            var box = document.getElementById('chat-box');
            box.innerHTML += '<div class="msg staff"><b>คุณ:</b> ' + text + '</div>';
            history_log.push("พนักงาน: " + text);
            box.scrollTop = box.scrollHeight;

            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: text, lvl: activeLvl, history: history_log})
                });
                const data = await res.json();
                box.innerHTML += '<div class="msg customer"><b>' + customers[activeLvl].name + ':</b> ' + data.reply + '</div>';
                history_log.push(customers[activeLvl].name + ": " + data.reply);
                box.scrollTop = box.scrollHeight;

                if (data.audio) {
                    player.src = "data:audio/mp3;base64," + data.audio;
                    await player.play();
                    document.getElementById('status').innerText = "🔈 ลูกค้ากำลังตอบ...";
                    player.onended = function() { resetUI(); };
                } else { resetUI(); }
            } catch (e) { resetUI(); }
        }

        function resetUI() {
            isProcessing = false;
            document.getElementById('mic-btn').disabled = false;
            document.getElementById('mic-btn').style.opacity = "1";
            document.getElementById('status').innerText = "✅ พร้อมคุยต่อ";
            document.getElementById('eval-btn').style.display = 'block';
        }

        async function showEvaluation() {
            document.getElementById('status').innerText = "⌛ กำลังประเมินผล...";
            const res = await fetch('/api/evaluate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({history: history_log.join("\\n")})
            });
            const data = await res.json();
            alert("📊 ผลการประเมิน:\\n" + data.evaluation);
            
            if (activeLvl === "5") {
                document.getElementById('pdf-staff').innerText = document.getElementById('staff-name').value;
                document.getElementById('cert-date').innerText = new Date().toLocaleDateString('th-TH');
                var el = document.getElementById('certificate');
                el.style.display = 'block';
                html2pdf().from(el).save().then(function(){ el.style.display = 'none'; });
            }
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
    context = "\\n".join(history[-6:])
    full_prompt = "System: " + cust['prompt'] + "\\nHistory:\\n" + context + "\\nUser: " + user_msg
    response = model.generate_content(full_prompt)
    audio_data = get_audio_base64(response.text, cust['voice'])
    return jsonify({"reply": response.text, "audio": audio_data})

@app.route('/api/evaluate', methods=['POST'])
def evaluate():
    history = request.json.get('history', '')
    prompt = "ประเมินการเปิดใจ, การปฏิบัติตามกฎ คปภ. และความถูกต้องของสินค้าจากบทสนทนานี้: " + history
    evaluation = model.generate_content(prompt).text
    return jsonify({"evaluation": evaluation})

if __name__ == "__main__":
    app.run(debug=True)
