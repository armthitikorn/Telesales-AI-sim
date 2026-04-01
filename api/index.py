import os
import requests
import re
import json
import csv
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai

app = Flask(__name__)

# --- [ส่วนที่ 1: ตั้งค่า API & Logging] ---
GENAI_API_KEY = os.environ.get("GENAI_API_KEY")
TTS_API_KEY = os.environ.get("TTS_API_KEY")
LOG_FILE = "sales_performance.csv"

genai.configure(api_key=GENAI_API_KEY)
model = genai.GenerativeModel(model_name="gemini-3.1-flash-lite-preview")

def save_to_csv(staff_name, customer_name, scores, total, passed):
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, mode='a', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        if not file_exists:
            header = ["Timestamp", "Staff Name", "Customer Name", "Total Score", "Status"] + [f"S_{i}" for i in range(4, 21)]
            writer.writerow(header)
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M"), staff_name, customer_name, total, "PASS" if passed else "FAIL"] + scores)

# --- [ส่วนที่ 2: ลอจิกการโต้ตอบ & Persona] ---
COLD_CALL_RULES = """
[คำสั่งเด็ดขาด]: คุณคือ "ลูกค้า" ห้ามสอนงาน ห้ามไกด์สคริปต์ ตอบสั้นและเป็นธรรมชาติ (1-2 ประโยค)
- หากพนักงานแนะนำตัวไม่ครบ/ไม่ชัดเจน ให้ถามแค่ "ใครนะ?", "เอาเบอร์มาจากไหน?"
- ตัดสินใจโต้ตอบตามบทบาทชีวิตของคุณ เปิดรับประกันทุกประเภทหากพนักงานหาจุดสนใจ (Hook) เจอ
"""

CUSTOMERS = {
    "1": {"name": "น้องฟ้า", "desc": "วัยรุ่นเริ่มทำงาน (ห่วงเงินออม)", "prompt": COLD_CALL_RULES + "คุณคือ 'ฟ้า' อายุ 23 ปี ห่วงเรื่องเงินเดือนที่ไม่พอใช้ ลงท้าย 'ค่ะ'", "voice": {"name": "th-TH-Chirp3-HD-Aoede", "gender": "FEMALE"}},
    "2": {"name": "เฮียวิรัช", "desc": "เจ้าของอู่ (ห่วงค่ารักษา/ภาษี)", "prompt": COLD_CALL_RULES + "คุณคือ 'วิรัช' อายุ 45 ปี ดุและเขี้ยวเรื่องความคุ้มค่า ลงท้าย 'ครับ'", "voice": {"name": "th-TH-Chirp3-HD-Achird", "gender": "MALE"}},
    "3": {"name": "ป้ามาลี", "desc": "แม่ค้าตลาด (ห่วงมรดก/การเคลม)", "prompt": COLD_CALL_RULES + "คุณคือ 'ป้ามาลี' อายุ 60 ปี ไม่เชื่อใจประกัน ถามคำถามชาวบ้านๆ ลงท้าย 'จ๊ะ'", "voice": {"name": "th-TH-Chirp3-HD-Kore", "gender": "FEMALE"}},
    "4": {"name": "คุณแอน", "desc": "แม่ลูกอ่อน (ห่วงสวัสดิการลูก)", "prompt": COLD_CALL_RULES + "คุณคือ 'แอน' อายุ 32 ปี สนใจทุกอย่างที่ทำให้ลูกปลอดภัย ลงท้าย 'ค่ะ'", "voice": {"name": "th-TH-Chirp3-HD-Leda", "gender": "FEMALE"}},
    "5": {"name": "คุณอัครเดช", "desc": "นักลงทุน (ห่วงภาษี/ส่งต่อทรัพย์สิน)", "prompt": COLD_CALL_RULES + "คุณคือ 'อัครเดช' อายุ 55 ปี เวลาน้อยและชอบความเป็นมืออาชีพ ลงท้าย 'ครับ'", "voice": {"name": "th-TH-Chirp3-HD-Charon", "gender": "MALE"}}
}

def get_audio_base64(text, voice_config):
    if not TTS_API_KEY: return None
    clean_text = re.sub(r'\(.*?\)', '', re.sub(r'^.*?:', '', text)).replace('*', '').strip()
    url = f"https://texttospeech.googleapis.com/v1beta1/text:synthesize?key={TTS_API_KEY}"
    payload = {"input": {"text": clean_text}, "voice": {"languageCode": "th-TH", "name": voice_config["name"]}, "audioConfig": {"audioEncoding": "MP3"}}
    try:
        res = requests.post(url, json=payload, timeout=5)
        return res.json().get("audioContent")
    except: return None

# --- [ส่วนที่ 3: HTML & UI] ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Sales Mastery Analytics</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root { --blue: #1e3a8a; --red: #be123c; --gray: #94a3b8; --green: #15803d; --gold: #b45309; }
        body { font-family: sans-serif; background: #f1f5f9; margin:0; }
        
        /* Modal Style */
        .modal-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); display: flex; align-items: center; justify-content: center; z-index: 2000; }
        .modal-card { background: white; padding: 25px; border-radius: 15px; max-width: 500px; width: 90%; text-align: center; }
        
        #lobby { padding: 20px; text-align: center; max-width: 600px; margin: auto; }
        .card { background: white; padding: 15px; margin: 10px 0; border-radius: 12px; border-left: 8px solid var(--blue); text-align: left; cursor: pointer; }
        #main-app { display: none; flex-direction: column; height: 100vh; background: white; }
        .header { background: var(--blue); color: white; padding: 15px; text-align: center; position: relative; }
        #chat-box { flex: 1; overflow-y: auto; padding: 15px; display: flex; flex-direction: column; gap: 10px; background: #f8fafc; }
        .msg { padding: 10px 15px; border-radius: 15px; max-width: 85%; line-height: 1.4; }
        .staff { align-self: flex-end; background: var(--blue); color: white; }
        .customer { align-self: flex-start; background: #e2e8f0; color: #1e293b; }
        .controls { padding: 15px; background: white; border-top: 1px solid #ddd; text-align: center; }
        .btn-mic { width: 70px; height: 70px; border-radius: 50%; border: none; background: var(--red); color: white; font-size: 30px; cursor: pointer; }
        
        #analytics-section { display:none; padding: 20px; background: white; border-radius: 15px; margin: 20px auto; max-width: 800px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .btn-view-stats { position: absolute; right: 15px; top: 15px; background: rgba(255,255,255,0.2); border: 1px solid white; color: white; padding: 5px 10px; border-radius: 5px; cursor: pointer; font-size: 12px; }
        
        /* PDPA UI */
        .pdpa-text { font-size: 13px; color: #64748b; text-align: left; line-height: 1.5; margin: 15px 0; max-height: 200px; overflow-y: auto; background: #f8fafc; padding: 10px; border-radius: 8px; }
    </style>
</head>
<body>

    <!-- 1. Consent Modal (PDPA) -->
    <div id="consent-modal" class="modal-overlay">
        <div class="modal-card">
            <h2 style="color: var(--blue)">ยินยอมให้เก็บข้อมูล (Consent)</h2>
            <div class="pdpa-text">
                <b>ข้อตกลงการใช้ระบบ Simulator:</b><br>
                1. ระบบจะเก็บข้อมูลชื่อพนักงาน และบันทึกคะแนนการประเมินเพื่อใช้ในการวิเคราะห์พัฒนาทักษะ<br>
                2. ข้อมูลการสนทนาจะถูกประมวลผลโดย AI เพื่อสรุปผลรายบุคคล<br>
                3. ข้อมูลทั้งหมดจะถูกจัดเก็บภายในองค์กรเพื่อการฝึกอบรมเท่านั้น<br>
                4. ท่านสามารถแจ้งผู้ดูแลระบบหากต้องการลบข้อมูลคะแนนย้อนหลัง<br><br>
                <i>*การกด "ยอมรับและเริ่มใช้งาน" ถือว่าท่านรับทราบและยินยอมให้ระบบบันทึกผลการทดสอบ</i>
            </div>
            <button onclick="acceptConsent()" style="width:100%; padding:15px; background:var(--green); color:white; border:none; border-radius:10px; font-weight:bold; cursor:pointer;">ยอมรับและเริ่มใช้งาน</button>
        </div>
    </div>

    <div id="lobby" style="display:none;">
        <h1 style="color: var(--blue)">🏆 Sales Mastery Academy</h1>
        <input type="text" id="staff-name" placeholder="ระบุชื่อพนักงาน" style="margin-bottom: 20px; padding: 10px; width: 80%; border-radius: 5px; border: 1px solid #ddd;">
        <div id="customer-list"></div>
        <button onclick="toggleAnalytics()" style="margin-top: 20px; background:none; border:1px solid var(--blue); color:var(--blue); padding:10px; border-radius:5px; cursor:pointer;">📊 ดูสถิติการพัฒนา (Analytics)</button>
    </div>

    <!-- Analytics Section -->
    <div id="analytics-section">
        <h2 style="text-align:center; color:var(--blue)">สถิติพัฒนาการพนักงาน</h2>
        <canvas id="performanceChart"></canvas>
        <button onclick="toggleAnalytics()" style="width:100%; margin-top:20px; padding:10px; border-radius:8px; border:none; background:var(--gray); color:white;">ปิดหน้าต่างสถิติ</button>
    </div>

    <div id="main-app">
        <div class="header">
            <h2 id="active-name" style="margin:0;">ลูกค้า</h2>
            <button class="btn-view-stats" onclick="location.reload()">🏠 กลับหน้าหลัก</button>
        </div>
        <div id="chat-box"></div>
        <div class="controls">
            <button id="mic-btn" class="btn-mic" onclick="toggleListen()">🎤</button>
            <p id="status" style="margin: 10px 0; font-size: 14px; color: #64748b;">แตะไมค์เพื่อพูด</p>
            <div style="display:flex; gap:5px; justify-content:center;">
                <input type="text" id="text-input" placeholder="พิมพ์ข้อความ..." style="width:70%; padding: 10px; border-radius: 8px; border: 1px solid #ddd;" onkeypress="if(event.key==='Enter') sendMsg()">
                <button onclick="sendMsg()" style="padding:10px; background:var(--blue); color:white; border:none; border-radius:8px;">ส่ง</button>
            </div>
            <button id="eval-btn" style="display:none; width:100%; padding:12px; border-radius:30px; border:2px solid var(--blue); color:var(--blue); background:none; font-weight:bold; margin-top: 15px;" onclick="showEvaluation()">🏁 ประเมินผล QC Matrix</button>
        </div>
    </div>

    <!-- Evaluation Modal -->
    <div id="eval-modal" style="display:none;" class="modal-overlay">
        <div class="eval-content" style="background:white; padding:20px; border-radius:15px; max-width:600px; width:90%; max-height:90vh; overflow-y:auto;">
             <div id="eval-printable-area">
                <h2 style="text-align:center; color:var(--blue);">📊 รายงานผลการทดสอบ</h2>
                <div id="score-banner" style="text-align:center; padding:15px; border-radius:10px; color:white; font-size:20px; font-weight:bold; margin-bottom:15px;"></div>
                <div id="fb-content"></div>
                <div id="eval-details" style="font-size:12px;"></div>
             </div>
             <button onclick="location.reload()" style="width:100%; padding:15px; background:var(--blue); color:white; border:none; border-radius:8px; margin-top:15px;">เสร็จสิ้น (กลับหน้าหลัก)</button>
        </div>
    </div>

    <!-- เผื่อไว้เป็น fallback ในกรณีที่ Web Audio API มีปัญหา -->
    <audio id="audio-player" playsinline style="display:none;"></audio>

    <script>
        var history_log = [];
        var activeLvl = "";
        var isThinking = false;
        var customers = {{ CUSTOMERS | tojson | safe }};
        
        // --- ส่วนเสริมสำหรับจัดการเสียงบน iOS (Web Audio API) ---
        var audioCtx;

        function initAudio() {
            if (!audioCtx) {
                const AudioContext = window.AudioContext || window.webkitAudioContext;
                audioCtx = new AudioContext();
            }
            if (audioCtx.state === 'suspended') {
                audioCtx.resume();
            }
        }

        async function playAudioWebAPI(base64String) {
            try {
                initAudio(); // กระตุ้น Context ให้พร้อมใช้งาน
                
                // แปลง Base64 เป็น ArrayBuffer
                const binaryString = window.atob(base64String);
                const len = binaryString.length;
                const bytes = new Uint8Array(len);
                for (let i = 0; i < len; i++) {
                    bytes[i] = binaryString.charCodeAt(i);
                }
                
                // ถอดรหัสและเล่นเสียง
                const audioBuffer = await audioCtx.decodeAudioData(bytes.buffer);
                const source = audioCtx.createBufferSource();
                source.buffer = audioBuffer;
                source.connect(audioCtx.destination);
                source.start(0);
                
            } catch (error) {
                console.error("Web Audio API failed, fallback to <audio> tag", error);
                // Fallback วิธีเดิมเผื่อฉุกเฉิน
                var audioPlayer = document.getElementById('audio-player');
                if (audioPlayer) {
                    audioPlayer.src = "data:audio/mp3;base64," + base64String;
                    audioPlayer.play().catch(e => console.error("Audio tag fallback failed", e));
                }
            }
        }
        // ------------------------------------------------

        function acceptConsent() {
            initAudio(); // ปลดล็อคเสียงให้ iOS อนุญาตตั้งแต่กดปุ่มยอมรับ
            document.getElementById('consent-modal').style.display = 'none';
            document.getElementById('lobby').style.display = 'block';
        }

        var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        var recognition = SpeechRecognition ? new SpeechRecognition() : null;
        if(recognition) {
            recognition.lang = 'th-TH';
            recognition.onresult = (e) => { if(!isThinking) sendToAI(e.results[0][0].transcript); };
        }

        function toggleListen() {
            initAudio(); // ปลดล็อคเสียงเผื่อไว้ทุกครั้งที่มีการโต้ตอบ
            try { recognition.start(); document.getElementById('status').innerText = "🔊 กำลังฟัง..."; } catch(e){}
        }

        function startApp(lvl) {
            if(!document.getElementById('staff-name').value) { alert("ระบุชื่อก่อนครับ"); return; }
            activeLvl = lvl;
            document.getElementById('lobby').style.display = 'none';
            document.getElementById('main-app').style.display = 'flex';
            document.getElementById('active-name').innerText = customers[lvl].name;
        }

        async function sendMsg() {
            initAudio(); // ปลดล็อคเสียงตอนกดส่งข้อความ
            let input = document.getElementById('text-input');
            if(input.value && !isThinking) sendToAI(input.value);
            input.value = "";
        }

        async function sendToAI(t) {
            isThinking = true;
            document.getElementById('mic-btn').disabled = true;
            document.getElementById('status').innerText = "⌛ ลูกค้ากำลังคิด...";
            
            appendMsg('staff', 'คุณ', t);
            history_log.push("พนักงาน: " + t);

            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: t, lvl: activeLvl, history: history_log})
            });
            const data = await res.json();
            
            appendMsg('customer', customers[activeLvl].name, data.reply);
            history_log.push(customers[activeLvl].name + ": " + data.reply);
            
            if(data.audio) {
                playAudioWebAPI(data.audio); // เรียกใช้ฟังก์ชันเล่นเสียงแบบใหม่
            }
            
            isThinking = false;
            document.getElementById('mic-btn').disabled = false;
            document.getElementById('status').innerText = "✅ พร้อมคุยต่อ";
            document.getElementById('eval-btn').style.display = 'block';
        }

        function appendMsg(role, name, text) {
            let box = document.getElementById('chat-box');
            let d = document.createElement('div');
            d.className = "msg " + role;
            d.innerHTML = `<b>${name}:</b> ${text}`;
            box.appendChild(d);
            box.scrollTop = box.scrollHeight;
        }

        async function showEvaluation() {
            document.getElementById('status').innerText = "⌛ กำลังประเมิน...";
            const res = await fetch('/api/evaluate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    history: history_log.join("\\n"),
                    staff_name: document.getElementById('staff-name').value,
                    customer_name: customers[activeLvl].name
                })
            });
            const data = await res.json();
            
            const banner = document.getElementById('score-banner');
            banner.innerText = `คะแนน: ${data.total}/85 (${data.passed ? "ผ่าน" : "ไม่ผ่าน"})`;
            banner.style.background = data.passed ? "var(--green)" : "var(--red)";
            
            document.getElementById('fb-content').innerHTML = `
                <div style="background:#f1f5f9; padding:10px; border-radius:8px; margin-bottom:10px;">
                    <b>จุดแข็ง:</b> ${data.strengths}<br>
                    <b>จุดอ่อน:</b> ${data.weaknesses}
                </div>`;
            
            document.getElementById('eval-modal').style.display = 'flex';
        }

        async function toggleAnalytics() {
            let sec = document.getElementById('analytics-section');
            if(sec.style.display === 'block') {
                sec.style.display = 'none';
            } else {
                sec.style.display = 'block';
                const res = await fetch('/api/analytics');
                const data = await res.json();
                renderChart(data);
            }
        }

        let myChart = null;
        function renderChart(data) {
            const ctx = document.getElementById('performanceChart').getContext('2d');
            if(myChart) myChart.destroy();
            myChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.labels,
                    datasets: [{
                        label: 'คะแนนรวมพนักงานล่าสุด',
                        data: data.values,
                        borderColor: '#1e3a8a',
                        backgroundColor: 'rgba(30, 58, 138, 0.1)',
                        fill: true,
                        tension: 0.3
                    }]
                },
                options: { scales: { y: { min: 0, max: 85 } } }
            });
        }

        var list = document.getElementById('customer-list');
        for (var k in customers) {
            (function(lvl){
                var d = document.createElement('div');
                d.className = 'card';
                d.onclick = function(){ startApp(lvl); };
                d.innerHTML = `<b>${customers[lvl].name}</b><br><small>${customers[lvl].desc}</small>`;
                list.appendChild(d);
            })(k);
        }
    </script>
</body>
</html>
"""

# --- [ส่วนที่ 4: เชื่อมต่อ API และ Backend] ---
@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE, CUSTOMERS=CUSTOMERS)

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        lvl, user_msg, history = data.get('lvl'), data.get('message'), data.get('history', [])
        cust = CUSTOMERS[lvl]
        context = "\n".join(history[-5:])
        full_prompt = f"{cust['prompt']}\nประวัติคุย: {context}\nพนักงาน: {user_msg}\nลูกค้าตอบกลับสั้นๆ:"
        response = model.generate_content(full_prompt)
        reply_text = response.text.strip()
        audio_data = get_audio_base64(reply_text, cust['voice'])
        return jsonify({"reply": reply_text, "audio": audio_data})
    except Exception as e:
        return jsonify({"reply": "ขอโทษทีครับ ระบบขัดข้อง", "audio": None}), 500

@app.route('/api/evaluate', methods=['POST'])
def evaluate():
    try:
        data = request.json
        history = data.get('history', '')
        staff_name = data.get('staff_name', 'Unknown')
        customer_name = data.get('customer_name', 'Unknown')
        
        eval_prompt = f"""วิเคราะห์ประวัติการขายประกันนี้ตาม QC Matrix 17 ข้อ (ข้อ 4-20) 
        ประวัติ: {history}
        ตอบกลับเป็น JSON เท่านั้น:
        {{
            "scores": [คะแนนข้อ4-20 รวม 17 ตัวเลข],
            "strengths": "...",
            "weaknesses": "...",
            "improvements": "..."
        }}"""
        
        response = model.generate_content(eval_prompt)
        res_text = response.text.strip()
        if "```json" in res_text: 
            res_text = res_text.split("```json")[1].split("```")[0]
        elif "```" in res_text: 
            res_text = res_text.split("```")[1].split("```")[0]
            
        eval_data = json.loads(res_text)
        scores = eval_data.get("scores", [0]*17)
        total = sum(scores)
        passed = total >= 50
        
        # บันทึกลง CSV ทันที
        async function showEvaluation() {
            document.getElementById('status').innerText = "⌛ กำลังประเมิน...";
            try {
                const res = await fetch('/api/evaluate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        history: history_log.join("\\n"),
                        staff_name: document.getElementById('staff-name').value,
                        customer_name: customers[activeLvl].name
                    })
                });
                const data = await res.json();
                
                const banner = document.getElementById('score-banner');
                banner.innerText = `คะแนน: ${data.total}/85 (${data.passed ? "ผ่านเกณฑ์ ✅" : "ไม่ผ่านเกณฑ์ ❌"})`;
                banner.style.background = data.passed ? "var(--green)" : "var(--red)";
                
                // แสดงจุดแข็ง จุดอ่อน และข้อเสนอแนะ
                document.getElementById('fb-content').innerHTML = `
                    <div style="background:#f1f5f9; padding:15px; border-radius:8px; margin-bottom:15px; line-height:1.6;">
                        <b style="color:var(--green);">จุดแข็ง:</b> ${data.strengths || "-"}<br>
                        <b style="color:var(--red);">จุดอ่อน:</b> ${data.weaknesses || "-"}<br>
                        <b style="color:var(--blue);">ข้อเสนอแนะ:</b> ${data.improvements || "ไม่มีข้อเสนอแนะเพิ่มเติม"}
                    </div>`;
                
                // สร้างพื้นที่แสดงคะแนนรายข้อ 4-20
                let detailsHtml = "<b style='color:var(--blue);'>รายละเอียดคะแนน QC Matrix (ข้อ 4 - 20):</b><div style='display:grid; grid-template-columns: 1fr 1fr; gap:8px; margin-top:10px;'>";
                if(data.scores && data.scores.length > 0) {
                    data.scores.forEach((score, index) => {
                        let itemNum = index + 4; // เริ่มที่ข้อ 4
                        detailsHtml += `<div style="background:#f8fafc; padding:8px; border-radius:5px; border:1px solid #e2e8f0; font-size:13px;">ข้อ ${itemNum}: <b>${score}</b>/5</div>`;
                    });
                } else {
                    detailsHtml += `<div>ไม่สามารถดึงข้อมูลคะแนนรายข้อได้</div>`;
                }
                detailsHtml += "</div>";
                
                document.getElementById('eval-details').innerHTML = detailsHtml;
                document.getElementById('eval-modal').style.display = 'flex';
            } catch (e) {
                console.error("Evaluation Error:", e);
                alert("เกิดข้อผิดพลาดในการประเมินผล รบกวนลองใหม่อีกครั้งครับ");
            }
        }

        async function toggleAnalytics() {
            let sec = document.getElementById('analytics-section');
            if(sec.style.display === 'block') {
                sec.style.display = 'none';
            } else {
                sec.style.display = 'block';
                const res = await fetch('/api/analytics');
                const data = await res.json();
                renderChart(data);
            }
        }

        let myChart = null;
        function renderChart(data) {
            const ctx = document.getElementById('performanceChart').getContext('2d');
            if(myChart) myChart.destroy();
            myChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.labels,
                    datasets: [{
                        label: 'คะแนนรวมพนักงานล่าสุด',
                        data: data.values,
                        borderColor: '#1e3a8a',
                        backgroundColor: 'rgba(30, 58, 138, 0.1)',
                        fill: true,
                        tension: 0.3
                    }]
                },
                options: { scales: { y: { min: 0, max: 85 } } }
            });
        }

        var list = document.getElementById('customer-list');
        for (var k in customers) {
            (function(lvl){
                var d = document.createElement('div');
                d.className = 'card';
                d.onclick = function(){ startApp(lvl); };
                d.innerHTML = `<b>${customers[lvl].name}</b><br><small>${customers[lvl].desc}</small>`;
                list.appendChild(d);
            })(k);
        }
    </script>
</body>
</html>
"""

# --- [ส่วนที่ 4: เชื่อมต่อ API และ Backend] ---
@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE, CUSTOMERS=CUSTOMERS)

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        lvl, user_msg, history = data.get('lvl'), data.get('message'), data.get('history', [])
        cust = CUSTOMERS[lvl]
        
        # แก้ไข: ดึงประวัติมาทั้งหมดเพื่อให้ AI ไม่ลืมบริบท
        context = "\n".join(history)
        
        full_prompt = f"{cust['prompt']}\nประวัติคุย: {context}\nพนักงาน: {user_msg}\nลูกค้าตอบกลับสั้นๆ:"
        response = model.generate_content(full_prompt)
        reply_text = response.text.strip()
        audio_data = get_audio_base64(reply_text, cust['voice'])
        return jsonify({"reply": reply_text, "audio": audio_data})
    except Exception as e:
        return jsonify({"reply": "ขอโทษทีครับ ระบบขัดข้อง", "audio": None}), 500

@app.route('/api/evaluate', methods=['POST'])
def evaluate():
    try:
        data = request.json
        history = data.get('history', '')
        staff_name = data.get('staff_name', 'Unknown')
        customer_name = data.get('customer_name', 'Unknown')
        
        eval_prompt = f"""วิเคราะห์ประวัติการขายประกันนี้ตาม QC Matrix 17 ข้อ (ข้อ 4-20) 
        ประวัติ: {history}
        ตอบกลับเป็น JSON เท่านั้น:
        {{
            "scores": [คะแนนข้อ4-20 รวม 17 ตัวเลข],
            "strengths": "...",
            "weaknesses": "...",
            "improvements": "..."
        }}"""
        
        response = model.generate_content(eval_prompt)
        res_text = response.text.strip()
        if "```json" in res_text: 
            res_text = res_text.split("```json")[1].split("```")[0]
        elif "```" in res_text: 
            res_text = res_text.split("```")[1].split("```")[0]
            
        eval_data = json.loads(res_text)
        
        # ป้องกัน Error กรณี AI คืนค่ามาเป็น String
        raw_scores = eval_data.get("scores", [0]*17)
        scores = [int(s) for s in raw_scores]
        
        total = sum(scores)
        passed = total >= 50
        
        # บันทึกลง CSV ทันที
        save_to_csv(staff_name, customer_name, [str(s) for s in scores], total, passed)
        
        eval_data["scores"] = scores # อัปเดต Array กลับไปให้ฝั่ง JS ใช้งาน
        eval_data["total"] = total
        eval_data["passed"] = passed
        return jsonify(eval_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    labels = []
    values = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, mode='r', encoding='utf-8-sig') as f:
            rows = list(csv.DictReader(f))
            # ดึง 10 รายการล่าสุดมาแสดงผล
            for row in rows[-10:]:
                labels.append(f"{row['Staff Name']} ({row['Timestamp']})")
                values.append(int(row['Total Score']))
    return jsonify({"labels": labels, "values": values})

if __name__ == "__main__":
    app.run(debug=True)
