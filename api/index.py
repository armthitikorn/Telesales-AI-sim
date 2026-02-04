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

# --- [ส่วนที่ 2: ข้อมูลลูกค้าและโปรดักส์] ---
CUSTOMERS = {
    "1": {
        "name": "น้องฟ้า (Level 1)",
        "desc": "ถามเรื่อง: SuperSmartSave 20/9",
        "prompt": """คุณคือ 'ฟ้า' อายุ 25 ปี สนใจออมเงินแต่ขี้ระแวง 
        - โปรดักส์ที่พนักงานต้องเสนอ: SuperSmartSave 20/9 (ออม 9 ปี คุ้มครอง 20 ปี)
        - หน้าที่ของคุณ: ถามเรื่องระยะเวลาฝาก, เงินคืนแต่ละปี, และความคุ้มครองกรณีเสียชีวิต 
        - กฎ: ตอบโต้เป็นธรรมชาติ ไม่สั้นเกินไป ไม่ยาวเกินไป ลงท้ายด้วย 'ค่ะ' เสมอ""",
        "voice": {"name": "th-TH-Standard-A", "pitch": 2.0, "rate": 1.0}
    },
    "2": {
        "name": "คุณวิรัช (Level 2)",
        "desc": "ถามเรื่อง: PRUMhao Mhao Double Sure",
        "prompt": """คุณคือ 'วิรัช' อายุ 45 ปี สนใจประกันสุขภาพ 
        - โปรดักส์ที่พนักงานต้องเสนอ: PRUMhao Mhao Double Sure (สุขภาพเหมาจ่าย)
        - หน้าที่ของคุณ: ถามเรื่องวงเงินเหมาจ่าย, ค่าห้อง, และครอบคลุมการผ่าตัดไหม
        - กฎ: พูดจาสุภาพ ลงท้ายด้วย 'ครับ' ตอบโต้แบบผู้ใหญ่ที่มีเหตุผล""",
        "voice": {"name": "th-TH-Standard-A", "pitch": -4.0, "rate": 0.95}
    },
    "3": {
        "name": "คุณป้ามาลี (Level 3)",
        "desc": "ถามเรื่อง: PRUSmart Wealth 888",
        "prompt": """คุณคือ 'ป้ามาลี' อายุ 60 ปี อยากเก็บเงินให้หลาน 
        - โปรดักส์ที่พนักงานต้องเสนอ: PRUSmart Wealth 888 (ออม 8 ปี คุ้มครองถึงอายุ 88)
        - หน้าที่ของคุณ: ถามจุกจิกเรื่องผลตอบแทนรวม, อายุที่คุ้มครองถึง, และทำไมต้องออมตั้ง 8 ปี
        - กฎ: พูดช้าลงเล็กน้อย ถามเยอะๆ ขี้สงสัย ลงท้ายด้วย 'ค่ะ/จ๊ะ'""",
        "voice": {"name": "th-TH-Standard-A", "pitch": -1.5, "rate": 0.9}
    },
    "4": {
        "name": "แม่แอน (Level 4)",
        "desc": "ถามได้ทุกโปรดักส์ (ระดับยาก)",
        "prompt": "คุณคือ 'แอน' คุณแม่ลูกอ่อน ปฏิเสธเก่งและมีข้อโต้แย้งเยอะ พนักงานต้องเสนอโปรดักส์ให้ตรงกับความต้องการของครอบครัวคุณและต้องถูกต้องตามเงื่อนไข คปภ.",
        "voice": {"name": "th-TH-Standard-A", "pitch": 0.5, "rate": 1.0}
    },
    "5": {
        "name": "คุณอัครเดช (Level 5)",
        "desc": "ถามได้ทุกโปรดักส์ (ระดับยากมาก)",
        "prompt": "คุณคือ 'อัครเดช' นักธุรกิจใหญ่ เวลาน้อยและเน้นตัวเลขความคุ้มค่าสูงสุด หากพนักงานให้ข้อมูลผิดแม้แต่นิดเดียวคุณจะวางสายทันที",
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

# --- [ส่วนที่ 3: UI ที่รองรับ iPhone และใบประกาศ Level 5] ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Sales Simulator Professional</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <style>
        :root { --blue: #1e3a8a; --red: #be123c; --gold: #b45309; }
        body { font-family: 'Sarabun', sans-serif; background: #f1f5f9; margin:0; -webkit-tap-highlight-color: transparent; }
        #lobby { padding: 20px; text-align: center; max-width: 600px; margin: auto; }
        .input-group { background: white; padding: 20px; border-radius: 15px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        input[type="text"] { padding: 15px; width: 85%; border-radius: 8px; border: 1px solid #ccc; font-size: 16px; margin-bottom: 10px; }
        .cust-card { background: white; padding: 15px; margin: 10px 0; border-radius: 12px; border-left: 8px solid var(--blue); cursor: pointer; text-align: left; transition: 0.2s; }
        .cust-card:active { transform: scale(0.98); background: #eee; }
        #main-app { display: none; flex-direction: column; height: 100vh; background: white; }
        .header { background: var(--blue); color: white; padding: 15px; text-align: center; position: sticky; top:0; z-index: 10; }
        #chat-box { flex: 1; overflow-y: auto; padding: 15px; display: flex; flex-direction: column; gap: 10px; background: #f8fafc; }
        .msg { padding: 12px 18px; border-radius: 15px; max-width: 85%; line-height: 1.5; font-size: 16px; }
        .staff { align-self: flex-end; background: var(--blue); color: white; }
        .customer { align-self: flex-start; background: #e2e8f0; color: #1e293b; }
        .controls { padding: 25px; text-align: center; background: white; border-top: 1px solid #ddd; padding-bottom: 40px; }
        .btn-mic { width: 90px; height: 90px; border-radius: 50%; border: none; background: var(--red); color: white; font-size: 40px; cursor: pointer; box-shadow: 0 4px 10px rgba(0,0,0,0.2); }
        .btn-mic:disabled { background: #94a3b8; opacity: 0.6; }
        
        #result-modal { display: none; position: fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.95); z-index: 1000; padding: 20px; overflow-y: auto; }
        .modal-body { background: white; padding: 25px; border-radius: 15px; max-width: 600px; margin: auto; }
        .cert-btn { background: var(--gold); color: white; border: none; padding: 15px; border-radius: 10px; width: 100%; font-weight: bold; margin-top: 15px; }

        /* Certificate */
        #cert-area { display:none; }
        .certificate { width: 800px; height: 550px; padding: 40px; border: 15px double var(--gold); background: white; text-align: center; position: relative; }
    </style>
</head>
<body>
    <div id="lobby">
        <h1 style="color: var(--blue)">🏆 Sales Mastery Academy</h1>
        <div class="input-group">
            <p>พิมพ์ชื่อพนักงานเพื่อเริ่มการฝึก</p>
            <input type="text" id="staff-name" placeholder="ชื่อ-นามสกุล ของท่าน">
        </div>
        <div id="customer-list"></div>
    </div>

    <div id="main-app">
        <div class="header">
            <button onclick="location.reload()" style="float:left; color:white; background:none; border:none; padding:10px; font-size: 20px;">🏠</button>
            <h2 id="active-cust-name" style="margin:0;">ลูกค้า</h2>
        </div>
        <div id="chat-box"></div>
        <div class="controls">
            <button id="mic-btn" class="btn-mic" onclick="toggleListen()">🎤</button>
            <div id="status" style="margin-top:10px; font-size: 14px; color: #666;">แตะไมค์เพื่อพูด</div>
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
            <h1 style="color: var(--blue); font-size: 40px;">CERTIFICATE OF EXCELLENCE</h1>
            <p style="font-size: 20px;">ขอมอบใบประกาศฉบับนี้ให้เพื่อรับรองว่า</p>
            <h2 id="pdf-staff-name" style="font-size: 35px; color: var(--red); text-decoration: underline;"></h2>
            <p style="font-size: 20px;">ได้ผ่านการทดสอบจำลองการขายระดับสูงสุด (Level 5)</p>
            <p style="font-size: 18px; margin-top: 50px;">ให้ไว้ ณ วันที่ <span id="cert-date"></span><br>โดย Sales Mastery Academy</p>
        </div>
    </div>

    <script>
        var history_log = [];
        var activeLvl = "";
        var isProcessing = false;
        var customers = {{ CUSTOMERS | tojson | safe }};
        var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        var recognition = null;
        if (SpeechRecognition) {
            recognition = new SpeechRecognition();
            recognition.lang = 'th-TH';
        }

        var audioPlayer = new Audio();

        // แสดงรายชื่อลูกค้า
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
            if(!document.getElementById('staff-name').value) { alert("กรุณาใส่ชื่อพนักงานก่อนครับ"); return; }
            activeLvl = lvl;
            document.getElementById('lobby').style.display = 'none';
            document.getElementById('main-app').style.display = 'flex';
            document.getElementById('active-cust-name').innerText = customers[lvl].name;
            
            // iPhone Audio Unlock: ต้องมีการเล่นเสียงสั้นๆ จากการสัมผัสครั้งแรก
            unlockAudio();
        }

        function unlockAudio() {
            var silent = new Audio("data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=");
            silent.play().catch(function(){});
        }

        if (recognition) {
            recognition.onresult = function(e) {
                var text = e.results[0][0].transcript;
                if (text.length > 1 && !isProcessing) { sendToAI(text); }
            };
            recognition.onend = function() { document.getElementById('mic-btn').style.opacity = "1"; };
        }

        function toggleListen() {
            if (isProcessing) return;
            unlockAudio(); // Unlock audio every time mic is clicked for iPhone stability
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
            document.getElementById('eval-content').innerText = "⏳ กำลังประเมินผลการขายและความถูกต้องของ คปภ...";
            const res = await fetch('/api/evaluate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({history: history_log.join("\\n")})
            });
            const data = await res.json();
            document.getElementById('eval-content').innerHTML = "<h2>📊 ผลการประเมิน</h2>" + data.evaluation.replace(/\\n/g, '<br>');
            
            // เฉพาะด่าน 5 ถึงจะโชว์ปุ่มใบประกาศ
            if (activeLvl === "5") {
                document.getElementById('cert-section').innerHTML = '<button class="cert-btn" onclick="generatePDF()">📜 รับใบประกาศนียบัตร Level 5</button>';
            } else {
                document.getElementById('cert-section').innerHTML = '';
            }
        }

        function generatePDF() {
            document.getElementById('pdf-staff-name').innerText = document.getElementById('staff-name').value;
            document.getElementById('cert-date').innerText = new Date().toLocaleDateString('th-TH');
            var element = document.getElementById('certificate');
            var opt = {
                margin: 0,
                filename: 'Sales_Mastery_L5.pdf',
                html2canvas: { scale: 2 },
                jsPDF: { unit: 'in', format: 'letter', orientation: 'landscape' }
            };
            document.getElementById('cert-area').style.display = 'block';
            html2pdf().set(opt).from(element).save().then(function() {
                document.getElementById('cert-area').style.display = 'none';
            });
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
    
    # ดึงบริบทจากไฟล์แนบที่ user เคยให้ไว้ (ใช้ความสามารถของ Gemini ในการจำข้อมูลโปรดักส์)
    context = "\\n".join(history[-6:])
    full_prompt = f"""คุณคือลูกค้าในสถานการณ์จำลองการขายประกันทางโทรศัพท์ 
    ข้อมูลบทบาทของคุณ: {cust['prompt']}
    ประวัติการคุย: {context}
    
    หน้าที่ของคุณ:
    1. ตอบโต้คำพูดของพนักงานขาย (User: {user_msg})
    2. ถามคำถามเกี่ยวกับโปรดักส์ที่ได้รับมอบหมาย เพื่อทดสอบความรู้พนักงาน
    3. ห้ามเสนอขายเอง และห้ามตอบตกลงง่ายเกินไป
    """
    
    response = model.generate_content(full_prompt)
    reply_text = response.text
    audio_data = get_audio_base64(reply_text, cust['voice'])
    return jsonify({"reply": reply_text, "audio": audio_data})

@app.route('/api/evaluate', methods=['POST'])
def evaluate():
    history = request.json.get('history', '')
    prompt = f"""คุณคือผู้เชี่ยวชาญด้านการฝึกอบรมการขายประกันและกฎ คปภ. 
    โปรดประเมินบทสนทนานี้:
    {history}
    
    เกณฑ์การประเมิน (สรุปเป็นข้อๆ):
    1. ความถูกต้องตามประกาศ คปภ. (การแนะนำตัว, เลขใบอนุญาต, ขออนุญาตบันทึกเสียง)
    2. ความถูกต้องของข้อมูลผลิตภัณฑ์ (SuperSmartSave 20/9, Double Sure, Wealth 888) ตามข้อมูลที่พนักงานนำเสนอ
    3. ทักษะการโน้มน้าวใจและการตอบข้อโต้แย้ง
    4. ให้คะแนนรวม 1-10
    """
    evaluation = model.generate_content(prompt).text
    return jsonify({"evaluation": evaluation})

if __name__ == "__main__":
    app.run(debug=True)
