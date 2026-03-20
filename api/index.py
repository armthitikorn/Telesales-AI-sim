import os
import requests
import re
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai

app = Flask(__name__)

# --- [ส่วนที่ 1: ตั้งค่า API และ AI] ---
# ใช้คีย์จาก Environment Variables ที่อาร์มตั้งใน Vercel
GENAI_API_KEY = os.environ.get("GENAI_API_KEY")
TTS_API_KEY = os.environ.get("TTS_API_KEY")

genai.configure(api_key=GENAI_API_KEY)
model = genai.GenerativeModel(model_name="gemini-2.5-flash")

# --- [ส่วนที่ 2: กฎของลูกค้าและรายชื่อลูกค้า] ---
COLD_CALL_RULES = """
[คำสั่งเด็ดขาด]: คุณคือ "ลูกค้า" เท่านั้น ห้ามสวมบทบาทเป็นพนักงานเด็ดขาด
1. [การจดจำ]: ห้ามถามชื่อพนักงานหรือเลขใบอนุญาตซ้ำหากเขาแจ้งไปแล้ว
2. [คำแทนตัว]: ผู้หญิงใช้ 'ฉัน/เรา', ผู้ชายใช้ 'ผม' (ห้ามเรียกชื่อตัวเอง)
3. [บุคลิก]: เริ่มจากระแวงและปฏิเสธ 4-5 รอบ จนกว่าพนักงานจะทำตามกฎ คปภ. ถูกต้อง
"""

CUSTOMERS = {
    "1": {
        "name": "น้องฟ้า", 
        "desc": "ออม 20/9", 
        "prompt": COLD_CALL_RULES + "คุณคือ 'ฟ้า' อายุ 25 ปี ลงท้าย 'ค่ะ'", 
        "voice": {"name": "th-TH-Neural2-A", "pitch": 0.5, "rate": 1.05} # เสียงผู้หญิง (ใสๆ วัยรุ่น)
    },
    "2": {
        "name": "คุณวิรัช", 
        "desc": "สุขภาพ", 
        "prompt": COLD_CALL_RULES + "คุณคือ 'วิรัช' อายุ 45 ปี ลงท้าย 'ครับ' เน้นถามเรื่องความคุ้มครองสุขภาพ", 
        "voice": {"name": "th-TH-Neural2-B", "pitch": -1.0, "rate": 1.0} # เสียงผู้ชาย (สุขุม มีอายุ)
    },
    "3": {
        "name": "คุณป้ามาลี", 
        "desc": "มรดก", 
        "prompt": COLD_CALL_RULES + "คุณคือ 'ป้ามาลี' อายุ 50 ปี ลงท้าย 'ค่ะ/จ๊ะ'", 
        "voice": {"name": "th-TH-Neural2-C", "pitch": -2.0, "rate": 0.9} # เสียงผู้หญิง (ผู้ใหญ่ ใจดี)
    },
    "4": {
        "name": "แม่แอน", 
        "desc": "ปฏิเสธหนัก", 
        "prompt": COLD_CALL_RULES + "คุณคือ 'แอน' ปฏิเสธเรื่องประกันตลอด", 
        "voice": {"name": "th-TH-Neural2-A", "pitch": -0.5, "rate": 1.1} # เสียงผู้หญิง (กระฉับกระเฉง/รำคาญ)
    },
    "5": {
        "name": "คุณอัครเดช", 
        "desc": "นักธุรกิจ", 
        "prompt": COLD_CALL_RULES + "คุณคือ 'อัครเดช' เวลาน้อยและดุ", 
        "voice": {"name": "th-TH-Neural2-B", "pitch": -2.5, "rate": 1.05} # เสียงผู้ชาย (เข้ม ดุ ดัน)
    }
}

def get_audio_base64(text, voice_config):
    if not TTS_API_KEY: return None
    # ล้างข้อความส่วนเกินเหมือนเดิม
    clean_text = re.sub(r'^.*?:', '', text)
    clean_text = re.sub(r'\(.*?\)', '', clean_text).strip()
    if not clean_text: return None
    
    url = f"https://texttospeech.googleapis.com/v1beta1/text:synthesize?key={TTS_API_KEY}"
    
    # แก้ไข Payload ตรงนี้ครับ
    payload = {
        "input": {"text": clean_text},
        "voice": {
            "languageCode": "th-TH", 
            "name": voice_config["name"],
            "ssmlGender": voice_config["gender"] # เพิ่มบรรทัดนี้เข้าไปครับ
        },
        "audioConfig": {
            "audioEncoding": "MP3", 
            "pitch": voice_config["pitch"], 
            "speakingRate": voice_config["rate"]
        }
    }
    
    try:
        res = requests.post(url, json=payload, timeout=10)
        result_json = res.json()
        
        # เพิ่มการดักจับ Error เพื่อดูว่าทำไมเสียงถึงไม่มา
        if "audioContent" in result_json:
            return result_json["audioContent"]
        else:
            print(f"TTS Error: {result_json}") # จะแสดง Error ใน Console ถ้าเสียงไม่ยอมพูด
            return None
    except Exception as e: 
        print(f"Request Error: {e}")
        return None

# --- [ส่วนที่ 3: หน้าจอ HTML และ JavaScript] ---
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
        .btn-mic:disabled { background: var(--gray) !important; opacity: 0.6; }
        #cert-area { display:none; background: white; padding: 40px; border: 15px double var(--gold); text-align: center; }
    </style>
</head>
<body>
    <div id="lobby">
        <h1 style="color: var(--blue)">🏆 Sales Mastery Academy</h1>
        <input type="text" id="staff-name" placeholder="ระบุชื่อพนักงาน">
        <div id="customer-list"></div>
    </div>

    <div id="main-app">
        <div class="header"><h2 id="active-name" style="margin:0;">ลูกค้า</h2></div>
        <div id="chat-box"></div>
        <div class="controls">
            <button id="mic-btn" class="btn-mic" onclick="toggleListen()">🎤</button>
            <p id="status" style="margin-top:10px;">แตะไมค์เพื่อพูด</p>
            <button id="eval-btn" style="display:none; width:100%; padding:15px; border-radius:30px; border:2px solid var(--blue); color:var(--blue); background:none; font-weight:bold;" onclick="showEvaluation()">🏁 ประเมินผล</button>
        </div>
    </div>

    <div id="cert-area">
        <h1 style="color: var(--blue)">CERTIFICATE OF EXCELLENCE</h1>
        <p style="font-size: 20px;">ขอมอบให้ คุณ <span id="pdf-staff"></span></p>
        <p>ผู้พิชิตการทดสอบด่านสูงสุดและปิดการขายได้สำเร็จ</p>
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
                d.innerHTML = '<b>' + customers[lvl].name + '</b><br><small>' + customers[lvl].desc + '</small>';
                list.appendChild(d);
            })(k);
        }

        function startApp(lvl) {
            if(!document.getElementById('staff-name').value) { alert("ระบุชื่อก่อนครับ"); return; }
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
            if (t.length > 0 && !isThinking) { sendToAI(t); }
        };

        function toggleListen() {
            if (isThinking) return;
            unlockAudio();
            player.pause();
            recognition.start();
            document.getElementById('mic-btn').style.opacity = "0.5";
        }

        async function sendToAI(t) {
            isThinking = true;
            document.getElementById('mic-btn').disabled = true;
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
                var cleanReply = data.reply.replace(/^.*?:/g, '').trim();
                box.innerHTML += '<div class="msg customer"><b>' + customers[activeLvl].name + ':</b> ' + cleanReply + '</div>';
                history_log.push(customers[activeLvl].name + ": " + cleanReply);
                box.scrollTop = box.scrollHeight;

                if (data.audio) {
                    player.src = "data:audio/mp3;base64," + data.audio;
                    await player.play();
                    player.onended = function() { resetUI(); };
                } else { resetUI(); }
            } catch (e) { resetUI(); }
        }

        function resetUI() {
            isThinking = false;
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
                body: JSON.stringify({history: history_log.join("\\n"), lvl: activeLvl})
            });
            const data = await res.json();
            alert("📊 ผลการประเมิน:\\n" + data.evaluation);
            
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

# --- [ส่วนที่ 4: เชื่อมต่อ API (ลบตัวซ้ำออกให้แล้ว)] ---
@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE, CUSTOMERS=CUSTOMERS)

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        lvl, user_msg, history = data.get('lvl'), data.get('message'), data.get('history', [])
        cust = CUSTOMERS[lvl]
        
        # ล็อกบทบาทลูกค้าให้ Gemini เข้าใจแจ่มแจ้ง
        context = "\n".join(history[-10:])
        full_prompt = f"""บทบาทของคุณ: {cust['prompt']}
ประวัติการสนทนา:
{context}
พนักงานขายประกันพูดว่า: "{user_msg}"
ตอบกลับในฐานะลูกค้าเท่านั้น (ห้ามตอบเป็นพนักงาน):"""

        response = model.generate_content(full_prompt)
        reply_text = response.text
        
        audio_data = get_audio_base64(reply_text, cust['voice'])
        return jsonify({"reply": reply_text, "audio": audio_data})
    except Exception as e:
        return jsonify({"reply": f"เกิดข้อผิดพลาด: {str(e)}", "audio": None}), 500

@app.route('/api/evaluate', methods=['POST'])
def evaluate():
    try:
        data = request.json
        history = data.get('history', '')
        lvl = data.get('lvl', '')
        
        prompt = f"ในฐานะโค้ชการขาย ประเมินบทสนทนานี้: {history} ... ให้บอกว่า [ปิดการขาย]: (สำเร็จ/ไม่สำเร็จ)"
        evaluation = model.generate_content(prompt).text
        is_closed = "สำเร็จ" in evaluation and "[ปิดการขาย]" in evaluation
        
        return jsonify({"evaluation": evaluation, "is_closed": is_closed})
    except:
        return jsonify({"evaluation": "ไม่สามารถประเมินได้", "is_closed": False}), 500

if __name__ == "__main__":
    app.run(debug=True)
