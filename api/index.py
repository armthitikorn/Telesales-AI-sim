import os
import requests
import re
import json
import csv
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai

app = Flask(__name__)

# --- [ส่วนที่ 1: ตั้งค่า AI - บังคับใช้ Gemini 2.5 Flash ตามกฎ Simulator] ---
GENAI_API_KEY = os.environ.get("GENAI_API_KEY")
TTS_API_KEY = os.environ.get("TTS_API_KEY")
LOG_FILE = "sales_performance.csv"

genai.configure(api_key=GENAI_API_KEY)
model = genai.GenerativeModel(model_name="gemini-2.5-flash")[span_0](start_span)[span_0](end_span)

# ฟังก์ชันบันทึก Log ลง CSV สำหรับ Analytics
def save_to_csv(staff_name, customer_name, scores, total, passed):
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, mode='a', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        if not file_exists:
            header = ["Timestamp", "Staff Name", "Customer Name", "Total Score", "Status"] + [f"S_{i}" for i in range(4, 21)]
            writer.writerow(header)
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M"), staff_name, customer_name, total, "PASS" if passed else "FAIL"] + scores)

# --- [ส่วนที่ 2: ลอจิกการโต้ตอบ & Persona แบบสมจริง] ---
COLD_CALL_RULES = """
[คำสั่งเด็ดขาด]: คุณคือ "ลูกค้าตัวจริง" ตอบสั้น กระชับ (1-2 ประโยค) ห้ามสอนงานหรือไกด์สคริปต์พนักงาน
1. [ความจำ]: อ่านประวัติการสนทนาทั้งหมด หากพนักงานแจ้งชื่อหรือเลขใบอนุญาตไปแล้ว ห้ามถามซ้ำ
2. [การปฏิเสธ]: เริ่มจากระแวงและปฏิเสธ 4-5 รอบ จนกว่าพนักงานจะพูดถูกต้องตามกฎ คปภ. หรือมีจุดขายที่ตรงกับชีวิตคุณ
3. [คำแทนตัว]: ผู้หญิงใช้ 'ฉัน/เรา', ผู้ชายใช้ 'ผม' ห้ามเรียกชื่อตัวเอง[span_1](start_span)[span_1](end_span)
"""

CUSTOMERS = {
    "1": {"name": "น้องฟ้า", "desc": "วัยรุ่นเริ่มทำงาน (ห่วงเงินออม)", "prompt": COLD_CALL_RULES + "คุณคือ 'ฟ้า' อายุ 23 ปี ห่วงเรื่องเงินออม ลงท้าย 'ค่ะ'", "voice": {"name": "th-TH-Neural2-A", "pitch": 0.0, "rate": 1.0}},
    "2": {"name": "เฮียวิรัช", "desc": "เจ้าของอู่ (ห่วงค่ารักษา/ภาษี)", "prompt": COLD_CALL_RULES + "คุณคือ 'วิรัช' อายุ 45 ปี ดุและเขี้ยว ลงท้าย 'ครับ'", "voice": {"name": "th-TH-Neural2-C", "pitch": 0.0, "rate": 1.0}},
    "3": {"name": "ป้ามาลี", "desc": "แม่ค้าตลาด (ห่วงมรดก)", "prompt": COLD_CALL_RULES + "คุณคือ 'ป้ามาลี' อายุ 60 ปี ภาษาชาวบ้าน ลงท้าย 'จ๊ะ'", "voice": {"name": "th-TH-Standard-A", "pitch": -1.5, "rate": 0.9}},
    "5": {"name": "คุณอัครเดช", "desc": "นักธุรกิจ (ห่วงการส่งต่อทรัพย์สิน)", "prompt": COLD_CALL_RULES + "คุณคือ 'อัครเดช' อายุ 55 ปี เวลาน้อย ลงท้าย 'ครับ'", "voice": {"name": "th-TH-Neural2-C", "pitch": -2.0, "rate": 1.0}}
}

def get_audio_base64(text, voice_config):
    if not TTS_API_KEY: return None
    clean_text = re.sub(r'\(.*?\)', '', re.sub(r'^.*?:', '', text)).replace('*', '').strip()[span_2](start_span)[span_2](end_span)
    if not clean_text: return None
    url = "https://texttospeech.googleapis.com/v1/text:synthesize?key=" + TTS_API_KEY[span_3](start_span)[span_3](end_span)
    payload = {
        "input": {"text": clean_text},
        "voice": {"languageCode": "th-TH", "name": voice_config["name"]},
        "audioConfig": {"audioEncoding": "MP3", "pitch": voice_config["pitch"], "speakingRate": voice_config["rate"]}
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.json().get("audioContent")
    except: return None

# --- [ส่วนที่ 3: UI & JavaScript แบบ iOS Fixed] ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Sales Mastery Simulator</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root { --blue: #1e3a8a; --red: #be123c; --gray: #94a3b8; --green: #15803d; }
        body { font-family: sans-serif; background: #f1f5f9; margin:0; -webkit-tap-highlight-color: transparent; }
        .modal-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); display: flex; align-items: center; justify-content: center; z-index: 2000; }
        .modal-card { background: white; padding: 25px; border-radius: 15px; max-width: 500px; width: 90%; text-align: center; }
        #lobby { padding: 20px; text-align: center; max-width: 600px; margin: auto; }
        .card { background: white; padding: 15px; margin: 10px 0; border-radius: 12px; border-left: 8px solid var(--blue); text-align: left; cursor: pointer; }
        #main-app { display: none; flex-direction: column; height: 100vh; background: white; }
        .header { background: var(--blue); color: white; padding: 15px; text-align: center; }
        #chat-box { flex: 1; overflow-y: auto; padding: 15px; display: flex; flex-direction: column; gap: 10px; background: #f8fafc; }
        .msg { padding: 10px 15px; border-radius: 15px; max-width: 85%; line-height: 1.4; }
        .staff { align-self: flex-end; background: var(--blue); color: white; }
        .customer { align-self: flex-start; background: #e2e8f0; color: #1e293b; }
        .controls { padding: 20px; text-align: center; background: white; border-top: 1px solid #ddd; }
        .btn-mic { width: 80px; height: 80px; border-radius: 50%; border: none; background: var(--red); color: white; font-size: 35px; cursor: pointer; }
        #analytics-section { display:none; padding: 20px; background: white; border-radius: 15px; margin: 20px auto; max-width: 800px; }
    </style>
</head>
<body>

    <!-- 1. PDPA Consent & iOS Audio Unlock -->
    <div id="consent-modal" class="modal-overlay">
        <div class="modal-card">
            <h2 style="color: var(--blue)">ยินยอมให้เก็บข้อมูล</h2>
            <p style="font-size:14px; color:#64748b; text-align:left;">ระบบจะบันทึกคะแนนเพื่อพัฒนาทักษะ (PDPA) และขออนุญาตเปิดใช้งานลำโพงสำหรับเสียง AI</p>
            <button onclick="acceptConsent()" style="width:100%; padding:15px; background:var(--green); color:white; border:none; border-radius:10px; font-weight:bold;">ยอมรับและเริ่มใช้งาน</button>
        </div>
    </div>

    <div id="lobby" style="display:none;">
        <h1 style="color: var(--blue)">🏆 Sales Mastery Academy</h1>
        <input type="text" id="staff-name" placeholder="ระบุชื่อพนักงาน" style="width:85%; padding:15px; border-radius:8px; border:1px solid #ddd; font-size:18px; margin-bottom:10px;">
        <div id="customer-list"></div>
        <button onclick="toggleAnalytics()" style="margin-top:20px; background:none; color:var(--blue); border:none; text-decoration:underline;">ดูสถิติย้อนหลัง (Analytics)</button>
    </div>

    <div id="analytics-section">
        <canvas id="performanceChart"></canvas>
        <button onclick="toggleAnalytics()" style="width:100%; margin-top:10px; padding:10px;">ปิด</button>
    </div>

    <div id="main-app">
        <div class="header"><h2 id="active-name" style="margin:0;">ลูกค้า</h2></div>
        <div id="chat-box"></div>
        <div class="controls">
            <button id="mic-btn" class="btn-mic" onclick="toggleListen()">🎤</button>
            <p id="status" style="margin-top:10px; color:#64748b;">แตะไมค์เพื่อพูด</p>
            <button id="eval-btn" style="display:none; width:100%; padding:15px; border-radius:30px; border:2px solid var(--blue); color:var(--blue); background:none; font-weight:bold; margin-top:10px;" onclick="showEvaluation()">🏁 ประเมินผล QC Matrix</button>
        </div>
    </div>

    <div id="eval-modal" style="display:none;" class="modal-overlay">
        <div style="background:white; padding:25px; border-radius:15px; width:90%; max-width:550px; max-height:85vh; overflow-y:auto;">
            <div id="eval-result"></div>
            <button onclick="location.reload()" style="width:100%; padding:15px; background:var(--blue); color:white; border:none; border-radius:8px; margin-top:15px;">เสร็จสิ้น (กลับหน้าหลัก)</button>
        </div>
    </div>

    <script>
        var history_log = [];
        var activeLvl = "";
        var isThinking = false;
        var customers = {{ CUSTOMERS | tojson | safe }};
        var player = new Audio(); // Global Audio Object[span_4](start_span)[span_4](end_span)
        
        var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        var recognition = SpeechRecognition ? new SpeechRecognition() : null;
        if(recognition) recognition.lang = 'th-TH';

        // ปลดล็อคเสียง iOS ด้วยไฟล์เสียงใบ้[span_5](start_span)[span_5](end_span)
        function unlockAudio() {
            var s = new Audio("data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=");
            s.play().catch(function(){});
        }

        function acceptConsent() {
            unlockAudio();
            document.getElementById('consent-modal').style.display = 'none';
            document.getElementById('lobby').style.display = 'block';
        }

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
            unlockAudio();
            activeLvl = lvl;
            document.getElementById('lobby').style.display = 'none';
            document.getElementById('main-app').style.display = 'flex';
            document.getElementById('active-name').innerText = customers[lvl].name;
        }

        if(recognition) {
            recognition.onresult = function(e) {
                var t = e.results[0][0].transcript;
                if (t.length > 0 && !isThinking) { sendToAI(t); }
            };
        }

        function toggleListen() {
            if (isThinking) return;
            unlockAudio();
            player.pause(); // หยุดเสียงเก่าก่อนเริ่มฟัง[span_6](start_span)[span_6](end_span)
            recognition.start();
            document.getElementById('mic-btn').style.opacity = "0.5";
            document.getElementById('status').innerText = "🔊 กำลังฟัง...";
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
                    player.src = "data:audio/mp3;base64," + data.audio;[span_7](start_span)[span_7](end_span)
                    await player.play();[span_8](start_span)[span_8](end_span)
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
                body: JSON.stringify({
                    history: history_log.join("\\n"), 
                    staff_name: document.getElementById('staff-name').value,
                    customer_name: customers[activeLvl].name
                })
            });
            const data = await res.json();
            document.getElementById('eval-result').innerHTML = `
                <h3 style="color:${data.passed?'green':'red'}">คะแนน: ${data.total}/85</h3>
                <p><b>จุดแข็ง:</b> ${data.strengths}</p>
                <p><b>จุดอ่อน:</b> ${data.weaknesses}</p>
                <hr><small>รายละเอียดถูกบันทึกลงระบบ Analytics เรียบร้อยแล้ว</small>
            `;
            document.getElementById('eval-modal').style.display = 'flex';
        }

        async function toggleAnalytics() {
            let sec = document.getElementById('analytics-section');
            if(sec.style.display === 'block') { sec.style.display = 'none'; } 
            else {
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
                    datasets: [{ label: 'คะแนนรวมล่าสุด', data: data.values, borderColor: '#1e3a8a', fill: false }]
                }
            });
        }
    </script>
</body>
</html>
"""

# --- [ส่วนที่ 4: Backend API] ---
@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE, CUSTOMERS=CUSTOMERS)

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    lvl, user_msg, history = data.get('lvl'), data.get('message'), data.get('history', [])
    cust = CUSTOMERS[lvl]
    context = "\\n".join(history)[span_9](start_span)[span_9](end_span)
    full_prompt = "System: " + cust['prompt'] + "\\nHistory:\\n" + context + "\\nUser: " + user_msg[span_10](start_span)[span_10](end_span)
    response = model.generate_content(full_prompt)
    reply_text = response.text
    audio_data = get_audio_base64(reply_text, cust['voice'])
    return jsonify({"reply": reply_text, "audio": audio_data})

@app.route('/api/evaluate', methods=['POST'])
def evaluate():
    data = request.json
    history = data.get('history', '')
    staff_name = data.get('staff_name', 'Unknown')
    customer_name = data.get('customer_name', 'Unknown')
    
    prompt = f"""ประเมินบทสนทนาการขายตาม QC Matrix 17 ข้อ (ข้อ 4-20) ให้คะแนนข้อละ 1-5 ดาว
    ประวัติ: {history}
    ตอบกลับเป็น JSON เท่านั้น:
    {{"scores": [คะแนน17ข้อ], "strengths": "...", "weaknesses": "..."}}"""
    
    res_text = model.generate_content(prompt).text
    if "```json" in res_text: res_text = res_text.split("```json")[1].split("```")[0]
    eval_data = json.loads(res_text)
    
    scores = eval_data.get("scores", [0]*17)
    total = sum(scores)
    passed = total >= 50
    
    save_to_csv(staff_name, customer_name, [str(s) for s in scores], total, passed)
    
    eval_data["total"] = total
    eval_data["passed"] = passed
    return jsonify(eval_data)

@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    labels, values = [], []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, mode='r', encoding='utf-8-sig') as f:
            rows = list(csv.DictReader(f))
            for row in rows[-10:]:
                labels.append(row['Timestamp'])
                values.append(int(row['Total Score']))
    return jsonify({"labels": labels, "values": values})

if __name__ == "__main__":
    app.run(debug=True)
