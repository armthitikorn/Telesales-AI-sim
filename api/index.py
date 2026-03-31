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
[คำสั่งเด็ดขาด]: คุณคือ "ลูกค้า" ตอบสั้นและเป็นธรรมชาติ (1-2 ประโยค) ห้ามไกด์สคริปต์
- หากพนักงานแนะนำตัวไม่ครบ ให้ถามแค่ "ใครนะ?", "โทรมาจากไหน?" 
- โต้ตอบตามบทบาทชีวิตของคุณ เปิดรับประกันทุกประเภทหากพนักงานหาจุดสนใจ (Hook) เจอ
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

# --- [ส่วนที่ 3: HTML & UI (Fix iOS Audio)] ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Sales Mastery iOS Ready</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root { --blue: #1e3a8a; --red: #be123c; --gray: #94a3b8; --green: #15803d; --gold: #b45309; }
        body { font-family: sans-serif; background: #f1f5f9; margin:0; -webkit-tap-highlight-color: transparent; }
        
        .modal-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); display: flex; align-items: center; justify-content: center; z-index: 2000; }
        .modal-card { background: white; padding: 25px; border-radius: 15px; max-width: 500px; width: 90%; text-align: center; }
        
        #lobby { padding: 20px; text-align: center; max-width: 600px; margin: auto; }
        .card { background: white; padding: 15px; margin: 10px 0; border-radius: 12px; border-left: 8px solid var(--blue); text-align: left; }
        #main-app { display: none; flex-direction: column; height: 100vh; background: white; }
        .header { background: var(--blue); color: white; padding: 15px; text-align: center; }
        #chat-box { flex: 1; overflow-y: auto; padding: 15px; display: flex; flex-direction: column; gap: 10px; background: #f8fafc; }
        .msg { padding: 10px 15px; border-radius: 15px; max-width: 85%; line-height: 1.4; position: relative; }
        .staff { align-self: flex-end; background: var(--blue); color: white; }
        .customer { align-self: flex-start; background: #e2e8f0; color: #1e293b; }
        .controls { padding: 15px; background: white; border-top: 1px solid #ddd; text-align: center; }
        .btn-mic { width: 70px; height: 70px; border-radius: 50%; border: none; background: var(--red); color: white; font-size: 30px; cursor: pointer; }
        
        .btn-play-audio { display: block; margin-top: 8px; padding: 5px 12px; background: #cbd5e1; border: none; border-radius: 10px; font-size: 12px; cursor: pointer; }
        
        #analytics-section { display:none; padding: 20px; background: white; border-radius: 15px; margin: 20px auto; max-width: 800px; }
    </style>
</head>
<body>

    <div id="consent-modal" class="modal-overlay">
        <div class="modal-card">
            <h2 style="color: var(--blue)">ข้อตกลงการใช้งาน</h2>
            <p style="font-size:14px; color:#64748b; text-align:left;">ระบบจะบันทึกเสียงและคะแนนเพื่อพัฒนาทักษะ (PDPA Compliance)</p>
            <button onclick="acceptConsent()" style="width:100%; padding:15px; background:var(--green); color:white; border:none; border-radius:10px; font-weight:bold;">ยอมรับและเริ่มใช้งาน</button>
        </div>
    </div>

    <div id="lobby" style="display:none;">
        <h1 style="color: var(--blue)">🏆 Sales Mastery Simulator</h1>
        <input type="text" id="staff-name" placeholder="ระบุชื่อพนักงาน" style="width:80%; padding:12px; border-radius:8px; border:1px solid #ddd;">
        <div id="customer-list" style="margin-top:20px;"></div>
        <button onclick="toggleAnalytics()" style="margin-top:20px; background:none; color:var(--blue); border:none; text-decoration:underline;">ดูสถิติย้อนหลัง</button>
    </div>

    <div id="analytics-section">
        <canvas id="performanceChart"></canvas>
        <button onclick="toggleAnalytics()" style="width:100%; margin-top:10px;">ปิด</button>
    </div>

    <div id="main-app">
        <div class="header"><h2 id="active-name" style="margin:0;">ลูกค้า</h2></div>
        <div id="chat-box"></div>
        <div class="controls">
            <button id="mic-btn" class="btn-mic" onclick="toggleListen()">🎤</button>
            <p id="status" style="margin: 8px 0; font-size: 13px; color: #64748b;">แตะไมค์เพื่อพูด</p>
            <div style="display:flex; gap:5px;">
                <input type="text" id="text-input" placeholder="พิมพ์โต้ตอบ..." style="flex:1; padding:10px; border-radius:8px; border:1px solid #ddd;">
                <button onclick="sendMsg()" style="padding:10px 20px; background:var(--blue); color:white; border:none; border-radius:8px;">ส่ง</button>
            </div>
            <button id="eval-btn" style="display:none; width:100%; padding:12px; border-radius:20px; border:1px solid var(--blue); color:var(--blue); background:none; margin-top:10px; font-weight:bold;" onclick="showEvaluation()">🏁 ประเมินผล</button>
        </div>
    </div>

    <div id="eval-modal" style="display:none;" class="modal-overlay">
        <div style="background:white; padding:20px; border-radius:15px; width:90%; max-width:500px; max-height:80vh; overflow-y:auto;">
            <div id="eval-content"></div>
            <button onclick="location.reload()" style="width:100%; padding:15px; background:var(--blue); color:white; border:none; border-radius:8px; margin-top:10px;">กลับหน้าหลัก</button>
        </div>
    </div>

    <!-- แอบใส่ไฟล์เสียงใบ้เพื่อปลดล็อค iOS -->
    <audio id="audio-player" playsinline style="display:none;"></audio>

    <script>
        var history_log = [];
        var activeLvl = "";
        var isThinking = false;
        var customers = {{ CUSTOMERS | tojson | safe }};
        var audioPlayer = document.getElementById('audio-player');
        
        // ฟังก์ชันสำคัญ: ปลดล็อคเสียงสำหรับ iOS
        function unlockAudio() {
            audioPlayer.src = "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=";
            audioPlayer.play().then(() => {
                audioPlayer.pause();
                console.log("Audio Unlocked for iOS");
            }).catch(e => console.log("Unlock failed", e));
        }

        function acceptConsent() {
            unlockAudio(); // ปลดล็อคทันทีที่กดตกลง
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
            unlockAudio(); // ปลดล็อคซ้ำทุกครั้งที่กดไมค์
            try { recognition.start(); document.getElementById('status').innerText = "🔊 กำลังฟัง..."; } catch(e){}
        }

        function startApp(lvl) {
            if(!document.getElementById('staff-name').value) { alert("ระบุชื่อก่อน"); return; }
            activeLvl = lvl;
            document.getElementById('lobby').style.display = 'none';
            document.getElementById('main-app').style.display = 'flex';
            document.getElementById('active-name').innerText = customers[lvl].name;
        }

        function sendMsg() {
            unlockAudio(); // ปลดล็อคซ้ำทุกครั้งที่กดส่ง
            let input = document.getElementById('text-input');
            if(input.value && !isThinking) sendToAI(input.value);
            input.value = "";
        }

        // แปลง Base64 เป็น Blob URL (iOS เสถียรกว่า)
        function base64ToBlobUrl(base64) {
            const byteCharacters = atob(base64);
            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            const blob = new Blob([byteArray], {type: 'audio/mp3'});
            return URL.createObjectURL(blob);
        }

        async function sendToAI(t) {
            isThinking = true;
            document.getElementById('status').innerText = "⌛ ลูกค้ากำลังคิด...";
            appendMsg('staff', 'คุณ', t);
            history_log.push("พนักงาน: " + t);

            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: t, lvl: activeLvl, history: history_log})
                });
                const data = await res.json();
                
                let botDiv = appendMsg('customer', customers[activeLvl].name, data.reply);
                history_log.push(customers[activeLvl].name + ": " + data.reply);
                
                if(data.audio) {
                    const blobUrl = base64ToBlobUrl(data.audio);
                    audioPlayer.src = blobUrl;
                    
                    // พยายามเล่นอัตโนมัติ
                    audioPlayer.play().catch(err => {
                        console.log("Autoplay blocked, showing manual button");
                        // ถ้า iOS บล็อก ให้สร้างปุ่มกดฟังเอง
                        let playBtn = document.createElement('button');
                        playBtn.className = "btn-play-audio";
                        playBtn.innerHTML = "🔊 กดเพื่อฟังเสียง";
                        playBtn.onclick = () => { audioPlayer.play(); playBtn.remove(); };
                        botDiv.appendChild(playBtn);
                    });
                }
            } catch(e) {}
            
            isThinking = false;
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
            return d;
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
            document.getElementById('eval-content').innerHTML = `<h3>คะแนน: ${data.total}/85</h3><p><b>จุดแข็ง:</b> ${data.strengths}</p><p><b>จุดอ่อน:</b> ${data.weaknesses}</p>`;
            document.getElementById('eval-modal').style.display = 'flex';
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

# --- [ส่วนที่ 4: Backend API (เหมือนเดิม)] ---
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
        full_prompt = f"{cust['prompt']}\nประวัติ: {context}\nพนักงาน: {user_msg}\nลูกค้าตอบสั้นๆ:"
        response = model.generate_content(full_prompt)
        reply_text = response.text.strip()
        audio_data = get_audio_base64(reply_text, cust['voice'])
        return jsonify({"reply": reply_text, "audio": audio_data})
    except:
        return jsonify({"reply": "สัญญาณไม่ดีเลยครับ...", "audio": None})

@app.route('/api/evaluate', methods=['POST'])
def evaluate():
    try:
        data = request.json
        eval_prompt = f"ประเมินบทสนทนานี้ตามกฎ คปภ. (JSON Only): {data.get('history')}"
        response = model.generate_content(eval_prompt)
        res_text = response.text.strip()
        if "```json" in res_text: res_text = res_text.split("```json")[1].split("```")[0]
        eval_data = json.loads(res_text)
        scores = eval_data.get("scores", [0]*17)
        total = sum(scores)
        save_to_csv(data.get('staff_name'), data.get('customer_name'), [str(s) for s in scores], total, total>=50)
        eval_data["total"] = total
        eval_data["passed"] = total>=50
        return jsonify(eval_data)
    except:
        return jsonify({"total": 0, "strengths": "Error", "weaknesses": "Error"})

if __name__ == "__main__":
    app.run(debug=True)
