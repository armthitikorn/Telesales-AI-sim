import os
import requests
import re
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai

app = Flask(__name__)

# --- [ส่วนที่ 1: ตั้งค่า AI - บังคับใช้ Gemini 2.5 Flash ตามคำสั่ง] ---
# อ้างอิงจากข้อกำหนด: "เมื่อเขียนโค้ด Simulator ให้ใช้ Gemini 2.5 Flash เสมอ"
GENAI_API_KEY = os.environ.get("GENAI_API_KEY")
TTS_API_KEY = os.environ.get("TTS_API_KEY")
genai.configure(api_key=GENAI_API_KEY)
model = genai.GenerativeModel(model_name="gemini-2.5-flash")

# --- [ส่วนที่ 2: ลอจิก Cold Call และ ความจำ] ---
COLD_CALL_RULES = """
คุณคือลูกค้าที่มีความจำดีเยี่ยมและเข้มงวด:
1. [การจดจำ]: คุณต้องอ่านประวัติการสนทนาทั้งหมดอย่างละเอียด หากพนักงานแจ้งชื่อ, เลขใบอนุญาต หรือขออัดเสียงไปแล้ว "ห้ามถามซ้ำ" และ "ห้ามทำเป็นลืม"
2. [คำแทนตัว]: ผู้หญิงใช้ 'ฉัน/เรา', ผู้ชายใช้ 'ผม' (ห้ามเรียกชื่อตัวเอง และห้ามมีหัวข้อชื่อนำหน้าข้อความ)
3. [ลำดับสาย]: เริ่มจากระแวง -> ปฏิเสธ 4-5 รอบ -> ยอมฟังเมื่อพูดถูกต้องตามกฎ คปภ. (ต้องแจ้งชื่อ-นามสกุล, ชื่อบริษัท, เลขใบอนุญาต และขออนุญาตบันทึกเสียง)
"""

CUSTOMERS = {
    "1": {
        "name": "น้องฟ้า", 
        "desc": "พนักงานออฟฟิศขี้รำคาญ", 
        "prompt": "คุณคือน้องฟ้า พนักงานออฟฟิศที่กำลังยุ่งมาก ไม่ชอบประกันทางโทรศัพท์ จะวางสายลูกเดียว ยกเว้นพนักงานจะพูดจาสุภาพและถูกต้องตามกฎจริงๆ", 
        "voice": {"name": "th-TH-Neural2-A", "pitch": 0.0, "rate": 1.0}
    },
    "2": {
        "name": "คุณวิรัช", 
        "desc": "เจ้าของกิจการ (Double Sure Health)", 
        "prompt": "คุณคือคุณวิรัช สนใจเรื่องความคุ้มครองที่คุ้มค่า แต่เป็นคนขี้สงสัยและต้องการความชัดเจนเรื่องเบี้ยประกัน", 
        "voice": {"name": "th-TH-Neural2-C", "pitch": 0.0, "rate": 1.0}
    },
    "3": {
        "name": "คุณป้ามาลี", 
        "desc": "ผู้สูงอายุใจดีแต่ขี้กลัว", 
        "prompt": "คุณคือคุณป้ามาลี กลัวโดนหลอกมากที่สุด ต้องใช้เวลาอธิบายช้าๆ และสุภาพมากๆ ถึงจะยอมเปิดใจ", 
        "voice": {"name": "th-TH-Standard-A", "pitch": -1.5, "rate": 0.9}
    },
    "5": {
        "name": "คุณอัครเดช", 
        "desc": "นักธุรกิจระดับสูง (ด่านสุดท้าย)", 
        "prompt": "คุณคือคุณอัครเดช เป็นคนใจร้อน เวลาเป็นเงินเป็นทอง ถ้าพนักงานพูดจาวนไปวนมาหรือไม่เป็นมืออาชีพ คุณจะตัดสายทันที", 
        "voice": {"name": "th-TH-Neural2-C", "pitch": -2.0, "rate": 1.0}
    }
}

def get_audio_base64(text, voice_config):
    if not TTS_API_KEY: return None
    # ล้างข้อความที่ไม่เกี่ยวข้องออกก่อนส่งไป Gen เสียง
    clean_text = re.sub(r'^.*?:', '', text)
    clean_text = re.sub(r'\(.*?\)', '', clean_text).strip()
    if not clean_text: return None
    
    url = "https://texttospeech.googleapis.com/v1/text:synthesize?key=" + TTS_API_KEY
    payload = {
        "input": {"text": clean_text},
        "voice": {"languageCode": "th-TH", "name": voice_config["name"]},
        "audioConfig": {"audioEncoding": "MP3", "pitch": voice_config["pitch"], "speakingRate": voice_config["rate"]}
    }
    try:
        res = requests.post(url, json=payload, timeout=5)
        return res.json().get("audioContent")
    except: return None

# --- [ส่วนที่ 3: UI และ JavaScript] ---
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
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f1f5f9; margin:0; }
        #lobby { padding: 20px; text-align: center; max-width: 600px; margin: auto; }
        input { padding: 15px; width: 85%; border-radius: 8px; border: 1px solid #ddd; font-size: 18px; margin-bottom: 20px; }
        .card { background: white; padding: 15px; margin: 10px 0; border-radius: 12px; border-left: 8px solid var(--blue); text-align: left; cursor: pointer; transition: 0.3s; }
        .card:hover { transform: scale(1.02); }
        #main-app { display: none; flex-direction: column; height: 100vh; background: white; }
        .header { background: var(--blue); color: white; padding: 15px; text-align: center; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        #chat-box { flex: 1; overflow-y: auto; padding: 15px; display: flex; flex-direction: column; gap: 10px; background: #f8fafc; }
        .msg { padding: 12px 18px; border-radius: 15px; max-width: 80%; line-height: 1.5; font-size: 16px; position: relative; }
        .staff { align-self: flex-end; background: var(--blue); color: white; border-bottom-right-radius: 2px; }
        .customer { align-self: flex-start; background: #e2e8f0; color: #1e293b; border-bottom-left-radius: 2px; }
        .controls { padding: 20px; text-align: center; background: white; border-top: 1px solid #ddd; }
        .btn-mic { width: 80px; height: 80px; border-radius: 50%; border: none; background: var(--red); color: white; font-size: 35px; cursor: pointer; box-shadow: 0 4px 10px rgba(190, 18, 60, 0.3); }
        .btn-mic:disabled { background: var(--gray) !important; opacity: 0.6; cursor: not-allowed; }
        #cert-area { display:none; background: white; padding: 40px; border: 15px double var(--gold); text-align: center; margin: 20px; }
        .eval-btn-style { width:100%; padding:15px; border-radius:30px; border:2px solid var(--blue); color:var(--blue); background:none; font-weight:bold; cursor:pointer; margin-top:10px; }
    </style>
</head>
<body>
    <div id="lobby">
        <h1 style="color: var(--blue)">🏆 Sales Mastery Academy</h1>
        <p>ยินดีต้อนรับคุณอาร์ม เข้าสู่ระบบฝึกฝนการขาย</p>
        <input type="text" id="staff-name" placeholder="ระบุชื่อพนักงานเพื่อเริ่มการทดสอบ">
        <div id="customer-list"></div>
    </div>

    <div id="main-app">
        <div class="header"><h2 id="active-name" style="margin:0;">ลูกค้า</h2></div>
        <div id="chat-box"></div>
        <div class="controls">
            <button id="mic-btn" class="btn-mic" onclick="toggleListen()">🎤</button>
            <p id="status" style="margin-top:10px; font-weight: bold; color: #64748b;">แตะไมค์เพื่อพูด</p>
            <button id="eval-btn" class="eval-btn-style" style="display:none;" onclick="showEvaluation()">🏁 จบการสนทนาและประเมินผล</button>
        </div>
    </div>

    <div id="cert-area">
        <h1 style="color: var(--blue)">CERTIFICATE OF EXCELLENCE</h1>
        <p style="font-size: 22px;">ขอมอบใบประกาศนียบัตรฉบับนี้ให้แก่</p>
        <h2 style="font-size: 30px; color: var(--gold);" id="pdf-staff"></h2>
        <p style="font-size: 18px;">ในฐานะผู้พิชิตการทดสอบด่านสูงสุด (คุณอัครเดช) และปิดการขายได้สำเร็จตามมาตรฐาน</p>
        <div style="margin-top: 50px;">
            <hr style="width: 50%; border: 1px solid #ddd;">
            <p>ผู้อำนวยการ Sales Mastery Academy</p>
        </div>
    </div>

    <script>
        var history_log = [];
        var activeLvl = "";
        var isThinking = false;
        var customers = {{ CUSTOMERS | tojson | safe }};
        var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        var recognition = new SpeechRecognition();
        recognition.lang = 'th-TH';
        recognition.interimResults = false;
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
            var name = document.getElementById('staff-name').value;
            if(!name) { alert("กรุณาระบุชื่อพนักงานก่อนครับ"); return; }
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
            try {
                recognition.start();
                document.getElementById('mic-btn').style.transform = "scale(1.1)";
                document.getElementById('status').innerText = "👂 กำลังฟัง...";
            } catch(e) {}
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
            document.getElementById('mic-btn').style.transform = "scale(1)";
            document.getElementById('status').innerText = "✅ พร้อมคุยต่อ (แตะไมค์อีกครั้ง)";
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
            alert(data.evaluation);
            
            if (data.is_closed && activeLvl === "5") {
                document.getElementById('pdf-staff').innerText = document.getElementById('staff-name').value;
                var el = document.getElementById('cert-area');
                el.style.display = 'block';
                html2pdf().from(el).set({margin: 1, filename: 'Certificate.pdf'}).save().then(function(){ 
                    el.style.display = 'none'; 
                    alert("🎉 ยินดีด้วยครับ! ระบบดาวน์โหลดใบประกาศนียบัตรให้คุณแล้ว");
                });
            } else if (activeLvl === "5" && !data.is_closed) {
                alert("💡 คำแนะนำ: คุณยังปิดการขายคุณอัครเดชไม่ได้ พยายามเน้นที่ผลประโยชน์ที่กระชับและตรงไปตรงมานะครับ");
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
    lvl, history = data.get('lvl'), data.get('history', [])
    cust = CUSTOMERS[lvl]
    
    # รวมกฎและประวัติการสนทนา (History มีข้อความล่าสุดจาก JS แล้ว)
    context = "\n".join(history)
    full_prompt = f"System Instruction: {cust['prompt']}\n{COLD_CALL_RULES}\n\nChat History:\n{context}\n{cust['name']}:"
    
    try:
        response = model.generate_content(full_prompt)
        reply_text = response.text
        audio_data = get_audio_base64(reply_text, cust['voice'])
        return jsonify({"reply": reply_text, "audio": audio_data})
    except Exception as e:
        return jsonify({"reply": "ขออภัย ระบบขัดข้องชั่วคราว", "audio": None})

@app.route('/api/evaluate', methods=['POST'])
def evaluate():
    data = request.json
    history = data.get('history', '')
    
    # บังคับโครงสร้างการตอบกลับเพื่อให้ตรวจสอบได้แม่นยำ
    prompt = f"""ในฐานะโค้ชการขายวิเคราะห์บทสนทนานี้:
    {history}
    
    ให้ประเมินตามเกณฑ์ดังนี้:
    1. พนักงานแจ้งชื่อ-นามสกุล และบริษัทชัดเจนหรือไม่
    2. พนักงานแจ้งเลขใบอนุญาตและขออนุญาตอัดเสียงหรือไม่
    3. พนักงานรับมือกับการปฏิเสธได้ดีเพียงใด
    4. พนักงานปิดการขายได้สำเร็จ (ลูกค้าตอบตกลงทำ) หรือไม่
    
    สรุปผลการประเมินให้พนักงานทราบ
    ในบรรทัดสุดท้ายให้พิมพ์คำว่า: [FINAL_RESULT: SUCCESS] หากปิดการขายได้สำเร็จ หรือ [FINAL_RESULT: FAILED] หากยังไม่สำเร็จ
    """
    
    try:
        evaluation = model.generate_content(prompt).text
        is_closed = "[FINAL_RESULT: SUCCESS]" in evaluation
        # ตัดคำว่า [FINAL_RESULT: ...] ออกจากข้อความที่จะแสดงให้ User เห็น
        display_eval = evaluation.replace("[FINAL_RESULT: SUCCESS]", "").replace("[FINAL_RESULT: FAILED]", "").strip()
        return jsonify({"evaluation": display_eval, "is_closed": is_closed})
    except:
        return jsonify({"evaluation": "ไม่สามารถประเมินผลได้ในขณะนี้", "is_closed": False})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
