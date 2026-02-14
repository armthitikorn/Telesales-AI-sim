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
# ใช้สมอง Gemini 2.5 Flash ตามที่บันทึกไว้
model = genai.GenerativeModel(model_name="gemini-2.5-flash")

# --- [ส่วนที่ 2: ลอจิก Cold Call และ ความจำ] ---
COLD_CALL_RULES = """
คุณคือลูกค้าที่มีความจำดีเยี่ยมและเข้มงวด:
1. [การจดจำ]: คุณต้องอ่านประวัติการสนทนาทั้งหมดอย่างละเอียด หากพนักงานแจ้งชื่อ, เลขใบอนุญาต หรือขออัดเสียงไปแล้ว "ห้ามถามซ้ำ" และ "ห้ามทำเป็นลืม"
2. [คำแทนตัว]: ผู้หญิงใช้ 'ฉัน/เรา', ผู้ชายใช้ 'ผม' (ห้ามเรียกชื่อตัวเอง และห้ามมีหัวข้อชื่อนำหน้าข้อความ)
3. [ลำดับสาย]: เริ่มจากระแวง -> ปฏิเสธ 4-5 รอบ -> ยอมฟังเมื่อพูดถูกต้องตามกฎ คปภ.
"""

# ปรับปรุงเสียงเป็น Chirp 3 HD Voices (Charon) ตามที่เลือกไว้ใน Vertex AI Studio
CUSTOMERS = {
    "1": {"name": "น้องฟ้า", "desc": "SuperSmartSave 20/9", "prompt": COLD_CALL_RULES + "คุณคือ 'ฟ้า' อายุ 25 ปี ลงท้าย 'ค่ะ' ถามเรื่องออม 9 ปี คุ้มครอง 20 ปี", "voice": {"name": "th-TH-Chirp3-HD-Charon", "pitch": 0.0, "rate": 1.05}},
    "2": {"name": "คุณวิรัช", "desc": "Double Sure Health", "prompt": COLD_CALL_RULES + "คุณคือ 'วิรัช' อายุ 45 ปี ลงท้าย 'ครับ' ถามเรื่องสุขภาพเหมาจ่าย", "voice": {"name": "th-TH-Chirp3-HD-Charon", "pitch": -2.0, "rate": 1.0}},
    "3": {"name": "คุณป้ามาลี", "desc": "Wealth 888", "prompt": COLD_CALL_RULES + "คุณคือ 'ป้ามาลี' ลงท้าย 'ค่ะ/จ๊ะ' ถามเรื่องมรดกให้หลาน", "voice": {"name": "th-TH-Chirp3-HD-Charon", "pitch": 0.0, "rate": 0.9}},
    "4": {"name": "แม่แอน", "desc": "ยาก: ปฏิเสธหนักมาก", "prompt": COLD_CALL_RULES + "คุณคือ 'แอน' ปฏิเสธหนักและห่วงเรื่องค่าใช้จ่ายลูก ลงท้าย 'ค่ะ'", "voice": {"name": "th-TH-Chirp3-HD-Charon", "pitch": 0.0, "rate": 1.0}},
    "5": {"name": "คุณอัครเดช", "desc": "ยากมาก: นักธุรกิจ (ต้องปิดการขายถึงได้ใบเซอร์)", "prompt": COLD_CALL_RULES + "คุณคือ 'อัครเดช' เวลาน้อยและเน้นความคุ้มค่าสูงสุด ลงท้าย 'ครับ'", "voice": {"name": "th-TH-Chirp3-HD-Charon", "pitch": -3.0, "rate": 1.05}}
}

def get_audio_base64(text, voice_config):
    if not TTS_API_KEY: return None
    # ลบสัญลักษณ์พิเศษที่ Gemini ชอบใส่มา เพื่อไม่ให้เสียงอ่านเพี้ยน
    clean_text = re.sub(r'[*#_]', '', text)
    clean_text = re.sub(r'\(.*?\)', '', clean_text).strip()
    if not clean_text: return None
    
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
            "speakingRate": voice_config["rate"],
            "sampleRateHertz": 44100  # ปรับเป็น 44100 Hz ตามที่คุณตั้งค่าในภาพ
        }
    }
    
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.json().get("audioContent")
    except Exception as e:
        print(f"Error in TTS: {e}")
        return None

# --- [ส่วนที่ 3: UI และ JavaScript] ---
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
        body { font-family: 'Sarabun', sans-serif; background: #f1f5f9; margin:0; }
        #lobby { padding: 20px; text-align: center; max-width: 600px; margin: auto; }
        input { padding: 15px; width: 85%; border-radius: 8px; border: 1px solid #ddd; font-size: 18px; margin-bottom: 20px; }
        .card { background: white; padding: 15px; margin: 10px 0; border-radius: 12px; border-left: 8px solid var(--blue); text-align: left; cursor: pointer; transition: 0.3s; }
        .card:hover { transform: scale(1.02); }
        #main-app { display: none; flex-direction: column; height: 100vh; background: white; }
        .header { background: var(--blue); color: white; padding: 15px; text-align: center; }
        #chat-box { flex: 1; overflow-y: auto; padding: 15px; display: flex; flex-direction: column; gap: 10px; background: #f8fafc; }
        .msg { padding: 10px 15px; border-radius: 15px; max-width: 85%; line-height: 1.4; position: relative; }
        .staff { align-self: flex-end; background: var(--blue); color: white; border-bottom-right-radius: 2px; }
        .customer { align-self: flex-start; background: #e2e8f0; color: #1e293b; border-bottom-left-radius: 2px; }
        .controls { padding: 20px; text-align: center; background: white; border-top: 1px solid #ddd; }
        .btn-mic { width: 80px; height: 80px; border-radius: 50%; border: none; background: var(--red); color: white; font-size: 35px; cursor: pointer; box-shadow: 0 4px 15px rgba(190, 18, 60, 0.4); }
        .btn-mic:disabled { background: var(--gray) !important; opacity: 0.6; box-shadow: none; }
        #cert-area { display:none; background: white; padding: 40px; border: 15px double var(--gold); text-align: center; }
        .thinking { font-style: italic; color: var(--gray); font-size: 0.9em; }
    </style>
</head>
<body>
    <div id="lobby">
        <h1 style="color: var(--blue)">🏆 Sales Mastery Simulator HD</h1>
        <p>ยกระดับการฝึกด้วยโมเดลเสียง Chirp 3</p>
        <input type="text" id="staff-name" placeholder="ระบุชื่อพนักงาน">
        <div id="customer-list"></div>
    </div>

    <div id="main-app">
        <div class="header"><h2 id="active-name" style="margin:0;">ลูกค้า</h2></div>
        <div id="chat-box"></div>
        <div class="controls">
            <button id="mic-btn" class="btn-mic" onclick="toggleListen()">🎤</button>
            <p id="status" style="margin-top:10px; font-weight: bold; color: var(--blue);">แตะไมค์เพื่อพูด</p>
            <button id="eval-btn" style="display:none; width:100%; padding:15px; border-radius:30px; border:2px solid var(--blue); color:var(--blue); background:none; font-weight:bold; margin-top: 10px;" onclick="showEvaluation()">🏁 จบการสนทนาและประเมินผล</button>
        </div>
    </div>

    <div id="cert-area">
        <h1 style="color: var(--blue)">CERTIFICATE OF EXCELLENCE</h1>
        <p style="font-size: 20px;">ขอมอบให้ คุณ <span id="pdf-staff"></span></p>
        <p>ผู้พิชิตการทดสอบด่านสูงสุดและปิดการขายได้สำเร็จ (Chirp 3 HD Level)</p>
        <p style="margin-top: 50px;">โดย Sales Mastery Academy</p>
    </div>

    <script>
        var history_log = [];
        var activeLvl = "";
        var isThinking = false;
        var customers = {{ CUSTOMERS | tojson | safe }};
        var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        var recognition = new SpeechRecognition();
        recognition.lang = 'th-TH';
        var player = new Audio();

        var list = document.getElementById('customer-list');
        for (var k in customers) {
            (function(lvl){
                var d = document.createElement('div');
                d.className = 'card';
                d.onclick = function(){ startApp(lvl); };
                d.innerHTML = '<b>👤 ' + customers[lvl].name + '</b><br><small>🎯 ' + customers[lvl].desc + '</small>';
                list.appendChild(d);
            })(k);
        }

        function startApp(lvl) {
            if(!document.getElementById('staff-name').value) { alert("กรุณาระบุชื่อพนักงานก่อนเริ่มต้นครับ"); return; }
            activeLvl = lvl;
            document.getElementById('lobby').style.display = 'none';
            document.getElementById('main-app').style.display = 'flex';
            document.getElementById('active-name').innerText = "กำลังคุยกับ: " + customers[lvl].name;
            unlockAudio();
        }

        function unlockAudio() {
            var s = new Audio("data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=");
            s.play().catch(function(){});
        }

        recognition.onresult = function(e) {
            var t = e.results[0][0].transcript;
            if (t.length > 0 && !isThinking) { sendToAI(t); }
        };

        recognition.onerror = function() { resetUI(); };

        function toggleListen() {
            if (isThinking) return;
            unlockAudio();
            player.pause();
            try { recognition.start(); } catch(e) {}
            document.getElementById('mic-btn').style.background = "#22c55e"; // สีเขียวขณะฟัง
            document.getElementById('status').innerText = "🔴 กำลังฟัง...";
        }

        async function sendToAI(t) {
            isThinking = true;
            document.getElementById('mic-btn').disabled = true;
            document.getElementById('mic-btn').style.background = var(--gray);
            document.getElementById('status').innerText = "⌛ ลูกค้ากำลังคิด...";
            
            var box = document.getElementById('chat-box');
            box.innerHTML += '<div class="msg staff"><b>คุณ:</b> ' + t + '</div>';
            history_log.push("พนักงาน: " + t);
            box.scrollTop = box.scrollHeight;

            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: t, lvl: activeLvl, history: history_log})
                });
                const data = await res.json();
                
                // ลบคำนำหน้าชื่อที่ AI อาจจะแถมมา
                var cleanReply = data.reply.replace(/^.*?:/g, '').trim();
                
                box.innerHTML += '<div class="msg customer"><b>' + customers[activeLvl].name + ':</b> ' + cleanReply + '</div>';
                history_log.push(customers[activeLvl].name + ": " + cleanReply);
                box.scrollTop = box.scrollHeight;

                if (data.audio) {
                    player.src = "data:audio/mp3;base64," + data.audio;
                    await player.play();
                    player.onended = function() { resetUI(); };
                } else { resetUI(); }
            } catch (e) { 
                console.error(e);
                resetUI(); 
            }
        }

        function resetUI() {
            isThinking = false;
            document.getElementById('mic-btn').disabled = false;
            document.getElementById('mic-btn').style.background = "var(--red)";
            document.getElementById('status').innerText = "✅ พร้อมคุยต่อ (แตะไมค์)";
            document.getElementById('eval-btn').style.display = 'block';
        }

        async function showEvaluation() {
            document.getElementById('status').innerText = "📊 กำลังวิเคราะห์ผลการสนทนา...";
            const res = await fetch('/api/evaluate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({history: history_log.join("\\n"), lvl: activeLvl})
            });
            const data = await res.json();
            alert("📊 รายงานผลการซ้อม:\\n" + data.evaluation);
            
            if (data.is_closed && activeLvl === "5") {
                document.getElementById('pdf-staff').innerText = document.getElementById('staff-name').value;
                var el = document.getElementById('cert-area');
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
    
    # ดึงประวัติมาสร้างเป็น Context
    context = "\\n".join(history)
    
    # ใช้ Gemini 2.5 Flash ในการประมวลผลคำตอบ
    full_prompt = f"System: {cust['prompt']}\\nHistory:\\n{context}\\nUser: {user_msg}"
    response = model.generate_content(full_prompt)
    reply_text = response.text
    
    # สร้างเสียงด้วยโมเดล Chirp 3 HD
    audio_data = get_audio_base64(reply_text, cust['voice'])
    
    return jsonify({"reply": reply_text, "audio": audio_data})

@app.route('/api/evaluate', methods=['POST'])
def evaluate():
    data = request.json
    history = data.get('history', '')
    
    prompt = f"""ในฐานะโค้ชการขายระดับมืออาชีพ ประเมินบทสนทนานี้:
    {history}
    
    ประเมินตามหัวข้อดังนี้:
    1. การกล่าวเปิดและแจ้งเลขใบอนุญาต/ขออัดเสียง (Compliance)
    2. การรับมือข้อโต้แย้ง (Objection Handling)
    3. ความสามารถในการปิดการขาย (Closing)
    
    สรุปปิดท้ายว่า: [ปิดการขาย]: (สำเร็จ/ไม่สำเร็จ)
    """
    evaluation = model.generate_content(prompt).text
    is_closed = "สำเร็จ" in evaluation and "[ปิดการขาย]" in evaluation
    
    return jsonify({"evaluation": evaluation, "is_closed": is_closed})

if __name__ == "__main__":
    # รันแบบรองรับพอร์ตที่ Vercel หรือ Hosting ต้องการ
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
