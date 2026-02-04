import os
import requests
import re
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai

app = Flask(__name__)

# --- [ส่วนที่ 1: ตั้งค่า API Keys] ---
GENAI_API_KEY = os.environ.get("GENAI_API_KEY")
TTS_API_KEY = os.environ.get("TTS_API_KEY")
genai.configure(api_key=GENAI_API_KEY)

# --- [ส่วนที่ 2: ข้อมูลลูกค้าพร้อมด่านข้อโต้แย้งต้นสาย] ---
# ทุกคนจะใช้กฎเดียวกันคือ: ต้องปฏิเสธ 4 ครั้งก่อนถึงจะยอมให้ขาย
COLD_CALL_LOGIC = """
กฎเหล็กในการสนทนา (สำคัญมาก):
1. [ระยะเริ่มต้น]: คุณยังไม่รู้ว่าพนักงานขายอะไร คุณต้องทำตัวยุ่งและไม่อยากคุย
2. [การปฏิเสธ]: คุณต้องปฏิเสธอย่างน้อย 4 รอบ ด้วยประโยคเหล่านี้ (สุ่มใช้):
   - 'เอาข้อมูล/เบอร์มาจากไหนคะ/ครับ?'
   - 'ประกันหรอ ไม่สนใจค่ะ/ครับ มีเยอะแล้ว'
   - 'ยุ่งอยู่ครับ/ค่ะ ส่งเอกสารมาดูทางเมล์หรือไปรษณีย์ก่อนได้ไหม'
   - 'พูดนานไหม ถ้าเกิน 2 นาทีไม่คุยนะ'
3. [เงื่อนไขการยอมฟัง]: คุณจะยอมให้เขาพูดต่อก็ต่อเมื่อเขาแจ้งชื่อ-นามสกุล, เลขใบอนุญาต และขออนุญาตบันทึกเสียงอย่างถูกต้องตามกฎ คปภ. และพูดจาโน้มน้าวใจได้น่าสนใจ
4. [ความยาว]: ตอบโต้ครั้งละ 1-2 ประโยค ไม่สั้นกุด และไม่ร่ายยาวจนน่ารำคาญ
"""

CUSTOMERS = {
    "1": {
        "name": "น้องฟ้า (Level 1)",
        "desc": "Product: SuperSmartSave 20/9",
        "prompt": f"คุณคือ 'ฟ้า' อายุ 25 ปี {COLD_CALL_LOGIC} หากยอมให้ขาย ให้ถามเรื่องโปรดักส์ SuperSmartSave 20/9 เน้นออมสั้นคุ้มครองยาว ลงท้าย 'ค่ะ'",
        "voice": {"name": "th-TH-Standard-A", "pitch": 2.0, "rate": 1.0}
    },
    "2": {
        "name": "คุณวิรัช (Level 2)",
        "desc": "Product: Double Sure Health",
        "prompt": f"คุณคือ 'วิรัช' อายุ 45 ปี {COLD_CALL_LOGIC} หากยอมให้ขาย ให้ถามเรื่องโปรดักส์ PRUMhao Mhao Double Sure เน้นค่ารักษาเหมาจ่าย ลงท้าย 'ครับ'",
        "voice": {"name": "th-TH-Standard-A", "pitch": -4.0, "rate": 1.0}
    },
    "3": {
        "name": "คุณป้ามาลี (Level 3)",
        "desc": "Product: Wealth 888",
        "prompt": f"คุณคือ 'ป้ามาลี' {COLD_CALL_LOGIC} หากยอมให้ขาย ให้ถามเรื่องโปรดักส์ PRUSmart Wealth 888 เน้นเก็บเงินให้หลาน ลงท้าย 'ค่ะ/จ๊ะ'",
        "voice": {"name": "th-TH-Standard-A", "pitch": -1.5, "rate": 0.9}
    },
    "4": {
        "name": "แม่แอน (Level 4)",
        "desc": "ยาก: ปฏิเสธหนักและถามจุกจิก",
        "prompt": f"คุณคือ 'แอน' คุณแม่ลูกอ่อน {COLD_CALL_LOGIC} คุณจะปฏิเสธหนักกว่าคนอื่น และถามจี้เรื่องความคุ้มครองลูกสาว ยอมฟังยากมาก",
        "voice": {"name": "th-TH-Standard-A", "pitch": 0.5, "rate": 1.0}
    },
    "5": {
        "name": "คุณอัครเดช (Level 5)",
        "desc": "ยากมาก: นักธุรกิจเวลาน้อย (มีใบประกาศ)",
        "prompt": f"คุณคือ 'อัครเดช' นักธุรกิจ {COLD_CALL_LOGIC} คุณจะให้เวลาแค่ 1 นาทีในการเปิดใจ ถ้าพูดไม่รู้เรื่องหรือไม่ถูกต้องตามกฎ คปภ. คุณจะวางสายทันที",
        "voice": {"name": "th-TH-Standard-A", "pitch": -5.0, "rate": 1.0}
    }
}

model = genai.GenerativeModel(model_name="gemini-2.5-flash")

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

# --- [ส่วนที่ 3: UI ที่รองรับ iPhone และระบบล็อกไมค์] ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Sales Simulator Elite</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <style>
        :root { --blue: #1e3a8a; --red: #be123c; --gold: #b45309; --gray: #94a3b8; }
        body { font-family: 'Sarabun', sans-serif; background: #f1f5f9; margin:0; }
        #lobby { padding: 20px; text-align: center; max-width: 600px; margin: auto; }
        .input-group { background: white; padding: 20px; border-radius: 15px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        input { padding: 15px; width: 85%; border-radius: 8px; border: 1px solid #ddd; font-size: 18px; text-align: center; }
        .cust-card { background: white; padding: 15px; margin: 10px 0; border-radius: 12px; border-left: 8px solid var(--blue); cursor: pointer; text-align: left; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        #main-app { display: none; flex-direction: column; height: 100vh; background: white; }
        .header { background: var(--blue); color: white; padding: 15px; text-align: center; }
        #chat-box { flex: 1; overflow-y: auto; padding: 15px; display: flex; flex-direction: column; gap: 10px; background: #f8fafc; }
        .msg { padding: 10px 15px; border-radius: 15px; max-width: 85%; line-height: 1.4; }
        .staff { align-self: flex-end; background: var(--blue); color: white; }
        .customer { align-self: flex-start; background: #e2e8f0; }
        .controls { padding: 30px; text-align: center; background: white; border-top: 1px solid #ddd; }
        .btn-mic { width: 90px; height: 90px; border-radius: 50%; border: none; background: var(--red); color: white; font-size: 40px; cursor: pointer; }
        .btn-mic:disabled { background: var(--gray) !important; opacity: 0.6; }
        #result-modal { display: none; position: fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.9); z-index: 1000; padding: 20px; overflow-y: auto; }
        .modal-body { background: white; padding: 25px; border-radius: 15px; max-width: 600px; margin: auto; }
        #cert-area { display:none; }
        .certificate { width: 800px; height: 550px; padding: 40px; border: 15px double var(--gold); background: white; text-align: center; color: #333; margin: auto; }
    </style>
</head>
<body>
    <div id="lobby">
        <h1 style="color: var(--blue)">🏆 Sales Mastery Simulator</h1>
        <div class="input-group">
            <p>พิมพ์ชื่อพนักงานเพื่อเริ่มฝึก</p>
            <input type="text" id="staff-name" placeholder="ชื่อ - นามสกุล">
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
            <div id="status" style="margin-top:10px; font-size: 0.9rem;">แตะไมค์เพื่อเริ่มคุย</div>
            <button id="eval-btn" style="display:none; width:100%; margin-top:20px; padding:15px; border-radius:30px; border:2px solid var(--blue); background:none; color:var(--blue); font-weight:bold;" onclick="showEvaluation()">🏁 จบการสนทนาและประเมินผล</button>
        </div>
    </div>

    <div id="result-modal">
        <div class="modal-body">
            <div id="eval-content"></div>
            <div id="cert-section"></div>
            <button onclick="location.reload()" style="width:100%; padding:10px; background:var(--blue); color:white; border:none; border-radius:8px; margin-top:10px;">กลับหน้าหลัก</button>
        </div>
    </div>

    <div id="cert-area">
        <div id="certificate" class="certificate">
            <h1 style="color: var(--blue); font-size: 40px;">CERTIFICATE OF ACHIEVEMENT</h1>
            <p style="font-size: 20px;">ขอมอบใบประกาศฉบับนี้ให้แก่ คุณ <span id="pdf-staff-name"></span></p>
            <p style="font-size: 20px;">ผู้ผ่านการทดสอบจำลองการขายระดับสูงสุด (Level 5)</p>
            <p style="font-size: 18px; margin-top: 50px;">ให้ไว้ ณ วันที่ <span id="cert-date"></span><br>โดย Sales Mastery Academy</p>
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

        var audioPlayer = new Audio();

        var listDiv = document.getElementById('customer-list');
        for (var lvl in customers) {
            (function(k){
                var d = document.createElement('div');
                d.className = 'cust-card';
                d.onclick = function(){ startApp(k); };
                d.innerHTML = '<b>' + customers[k].name + '</b><br><small>' + customers[k].desc + '</small>';
                listDiv.appendChild(d);
            })(lvl);
        }

        function startApp(lvl) {
            if(!document.getElementById('staff-name').value) { alert("ใส่ชื่อก่อนครับ"); return; }
            activeLvl = lvl;
            document.getElementById('lobby').style.display = 'none';
            document.getElementById('main-app').style.display = 'flex';
            document.getElementById('active-cust-name').innerText = customers[lvl].name;
            unlockAudio();
        }

        function unlockAudio() {
            var silent = new Audio("data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=");
            silent.play().catch(function(){});
        }

        recognition.onresult = function(e) {
            var text = e.results[0][0].transcript;
            if (text.length > 1 && !isProcessing) { sendToAI(text); }
        };

        function toggleListen() {
            if (isProcessing) return;
            unlockAudio();
            audioPlayer.pause();
            recognition.start();
            document.getElementById('mic-btn').style.opacity = "0.5";
            document.getElementById('status').innerText = "👂 กำลังฟัง...";
        }

        async function sendToAI(text) {
            isProcessing = true;
            document.getElementById('mic-btn').disabled = true;
            var chatBox = document.getElementById('chat-box');
            chatBox.innerHTML += '<div class="msg staff"><b>คุณ:</b> ' + text + '</div>';
            history_log.push("พนักงาน: " + text);
            chatBox.scrollTop = chatBox.scrollHeight;

            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: text, lvl: activeLvl, history: history_log})
                });
                const data = await res.json();
                chatBox.innerHTML += '<div class="msg customer"><b>' + customers[activeLvl].name + ':</b> ' + data.reply + '</div>';
                history_log.push(customers[activeLvl].name + ": " + data.reply);
                chatBox.scrollTop = chatBox.scrollHeight;

                if (data.audio) {
                    audioPlayer.src = "data:audio/mp3;base64," + data.audio;
                    await audioPlayer.play();
                    document.getElementById('status').innerText = "🔈 ลูกค้ากำลังตอบ...";
                    audioPlayer.onended = function() { resetUI(); };
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
            document.getElementById('result-modal').style.display = 'block';
            document.getElementById('eval-content').innerText = "⏳ กำลังประเมินผล...";
            const res = await fetch('/api/evaluate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({history: history_log.join("\\n")})
            });
            const data = await res.json();
            document.getElementById('eval-content').innerHTML = "<h2>📊 ผลการประเมิน</h2>" + data.evaluation.replace(/\\n/g, '<br>');
            if (activeLvl === "5") {
                document.getElementById('cert-section').innerHTML = '<button style="width:100%; padding:15px; background:var(--gold); color:white; border:none; border-radius:10px; font-weight:bold; margin-top:10px;" onclick="generatePDF()">📜 รับใบประกาศ Level 5</button>';
            }
        }

        function generatePDF() {
            document.getElementById('pdf-staff-name').innerText = document.getElementById('staff-name').value;
            document.getElementById('cert-date').innerText = new Date().toLocaleDateString('th-TH');
            var el = document.getElementById('certificate');
            var opt = { margin: 0, filename: 'Sales_Mastery_Cert.pdf', html2canvas: { scale: 2 }, jsPDF: { unit: 'in', format: 'letter', orientation: 'landscape' } };
            document.getElementById('cert-area').style.display = 'block';
            html2pdf().set(opt).from(el).save().then(function(){ document.getElementById('cert-area').style.display = 'none'; });
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
    context = "\\n".join(history[-6:])
    full_prompt = f"""บทบาทของคุณ: {cust['prompt']}
    ประวัติการสนทนา: {context}
    คำพูดพนักงานล่าสุด: {user_msg}
    
    คำสั่งเฉพาะ:
    - ในช่วง 4-5 ประโยคแรก คุณต้องปฏิเสธและยื้อเวลาตามกฎ Cold Call
    - ห้ามตอบตกลงฟังจนกว่าเขาจะแนะนำตัวครบ (ชื่อ, บ.พรูเด็นเชียล, เลขใบอนุญาต, บันทึกเสียง)
    - หลังจากเขาสร้างสัมพันธ์ได้ดีแล้ว จึงเริ่มถามคำถามเกี่ยวกับผลิตภัณฑ์ตามด่านของคุณ
    """
    response = model.generate_content(full_prompt)
    audio_data = get_audio_base64(response.text, cust['voice'])
    return jsonify({"reply": response.text, "audio": audio_data})

@app.route('/api/evaluate', methods=['POST'])
def evaluate():
    history = request.json.get('history', '')
    prompt = f"""ในฐานะโค้ชสอนการขาย ประเมินการสนทนานี้:
    {history}
    
    หัวข้อที่ต้องสรุป:
    1. การแก้ข้อโต้แย้งต้นสาย (Handle Objections) ทำได้ดีแค่ไหน
    2. ความถูกต้องตามประกาศ คปภ. (แนะนำตัว, แจ้งเลขใบอนุญาต, ขออัดเสียง)
    3. ความถูกต้องของข้อมูลสินค้า (ตามโปรดักส์ประจำด่าน)
    4. การปิดการขาย
    ให้คะแนนรวม 1-10 พร้อมคำแนะนำ
    """
    evaluation = model.generate_content(prompt).text
    return jsonify({"evaluation": evaluation})

if __name__ == "__main__":
    app.run(debug=True)
