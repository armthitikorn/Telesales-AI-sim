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

# --- [ส่วนที่ 2: ข้อมูลลูกค้า (เน้นประหยัดคำและบทบาทผู้ซื้อ)] ---
CUSTOMERS = {
    "1": {
        "name": "น้องฟ้า (Level 1 - Skeptical)",
        "desc": "วัยทำงาน 25 ปี - ขี้ระแวงและพูดน้อย",
        "prompt": """คุณคือ 'ฟ้า' ลูกค้า (ผู้ซื้อ) อายุ 25 ปี 
        กฎ: ตอบสั้นไม่เกิน 1 ประโยค ห้ามเสนอขายเอง ห้ามพูดก่อนพนักงานทัก และรอรับฟังคำอธิบายอย่างใจเย็น""",
        "voice": {"name": "th-TH-Standard-A", "pitch": 2.5, "rate": 1.05} 
    },
    "2": {"name": "คุณวิรัช (Level 2)", "desc": "วัยสร้างตัว 45 ปี", "prompt": "คุณคือวิรัช ตอบสั้นและสุภาพ", "voice": {"name": "th-TH-Standard-B", "pitch": -1.0, "rate": 1.0}},
    "3": {"name": "คุณป้ามาลี (Level 3)", "desc": "จอมละเอียด", "prompt": "คุณคือป้ามาลี ถามจุกจิก", "voice": {"name": "th-TH-Standard-A", "pitch": -2.0, "rate": 0.9}},
    "4": {"name": "แม่แอน (Level 4)", "desc": "ทำประกันให้ลูก", "prompt": "คุณคือแอน ห่วงลูกมาก", "voice": {"name": "th-TH-Standard-A", "pitch": 1.0, "rate": 1.0}},
    "5": {"name": "คุณอัครเดช (Level 5)", "desc": "นักธุรกิจใหญ่", "prompt": "คุณคืออัครเดช เวลามีน้อย", "voice": {"name": "th-TH-Standard-B", "pitch": -3.0, "rate": 0.95}}
}

model = genai.GenerativeModel(model_name="gemini-2.5-flash")

def get_audio_base64(text, voice_config):
    if not TTS_API_KEY: return None
    clean_text = re.sub(r'\(.*?\)', '', text)
    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={TTS_API_KEY}"
    payload = {
        "input": {"text": clean_text},
        "voice": {"languageCode": "th-TH", "name": voice_config["name"]},
        "audioConfig": {"audioEncoding": "MP3", "pitch": voice_config["pitch"], "speakingRate": voice_config["rate"]}
    }
    try:
        response = requests.post(url, json=payload)
        return response.json().get("audioContent") if response.status_code == 200 else None
    except: return None

# --- [ส่วนที่ 3: UI ระบบกดเปิด-ปิดไมค์เอง] ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Sales Mastery</title>
    <style>
        :root { --blue: #1e3a8a; --red: #be123c; --orange: #f59e0b; --gray: #94a3b8; }
        body { font-family: 'Sarabun', sans-serif; background: #f1f5f9; margin:0; }
        #lobby { padding: 20px; text-align: center; }
        .cust-card { background: white; padding: 15px; margin: 10px 0; border-radius: 12px; border-left: 8px solid var(--blue); cursor: pointer; text-align: left; }
        #main-app { display: none; flex-direction: column; height: 100vh; background: white; }
        .header { background: var(--blue); color: white; padding: 15px; text-align: center; }
        #chat-box { flex: 1; overflow-y: auto; padding: 15px; display: flex; flex-direction: column; gap: 10px; background: #f8fafc; }
        .msg { padding: 10px 15px; border-radius: 15px; max-width: 80%; }
        .staff { align-self: flex-end; background: var(--blue); color: white; }
        .customer { align-self: flex-start; background: #e2e8f0; }
        .controls { padding: 30px; text-align: center; background: white; border-top: 1px solid #ddd; }
        .btn-mic { width: 90px; height: 90px; border-radius: 50%; border: none; background: var(--blue); color: white; font-size: 35px; cursor: pointer; transition: 0.3s; }
        .btn-mic.recording { background: var(--orange); animation: pulse 1s infinite; }
        .btn-mic:disabled { background: var(--gray); opacity: 0.5; }
        @keyframes pulse { 0% { transform: scale(1); } 50% { transform: scale(1.1); } 100% { transform: scale(1); } }
        #status-text { margin-top: 10px; font-weight: bold; color: var(--blue); }
    </style>
</head>
<body>
    <div id="lobby">
        <h1 style="color: var(--blue)">🏆 Sales Mastery Academy</h1>
        <div id="customer-list"></div>
    </div>

    <div id="main-app">
        <div class="header">
            <button onclick="location.reload()" style="float:left; color:white; background:none; border:none;">⬅️ ออก</button>
            <h2 id="active-cust-name" style="margin:0;">ลูกค้า</h2>
        </div>
        <div id="chat-box"></div>
        <div class="controls">
            <button id="mic-btn" class="btn-mic" onclick="handleMicClick()">🎤</button>
            <div id="status-text">กดปุ่มเพื่อเริ่มพูด</div>
            <button id="eval-btn" style="display:none; width:100%; margin-top:20px; padding:10px; border-radius:20px; border:1px solid var(--blue); background:none; color:var(--blue);" onclick="showEvaluation()">🏁 จบและประเมินผล</button>
        </div>
    </div>

    <script>
        let history = [];
        let activeLevel = "";
        let isRecording = false; // สถานะการบันทึกเสียง
        let isProcessing = false; // สถานะ AI กำลังทำงาน
        let finalTranscript = ""; // เก็บคำพูดที่รวบรวมได้
        
        const customers = {{ CUSTOMERS | tojson | safe }};
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        let recognition = new SpeechRecognition();
        recognition.lang = 'th-TH';
        recognition.continuous = true; // บังคับให้ฟังยาวๆ ไม่ต้องหยุดเอง
        recognition.interimResults = true;

        let audioPlayer = new Audio();

        Object.keys(customers).forEach(lvl => {
            document.getElementById('customer-list').innerHTML += `<div class="cust-card" onclick="startChat('${lvl}')"><b>Level ${lvl}: ${customers[lvl].name}</b><br><small>${customers[lvl].desc}</small></div>`;
        });

        function startChat(lvl) {
            activeLevel = lvl;
            document.getElementById('lobby').style.display = 'none';
            document.getElementById('main-app').style.display = 'flex';
            document.getElementById('active-cust-name').innerText = customers[lvl].name;
            unlockAudio();
        }

        recognition.onresult = (e) => {
            let interimTranscript = "";
            for (let i = e.resultIndex; i < e.results.length; ++i) {
                if (e.results[i].isFinal) {
                    finalTranscript += e.results[i][0].transcript;
                } else {
                    interimTranscript += e.results[i][0].transcript;
                }
            }
            document.getElementById('status-text').innerText = "กำลังฟัง: " + (finalTranscript + interimTranscript);
        };

        function handleMicClick() {
            if (isProcessing) return;

            if (!isRecording) {
                // เริ่มบันทึกเสียง
                startRecording();
            } else {
                // หยุดและส่งข้อมูล
                stopRecordingAndSend();
            }
        }

        function startRecording() {
            finalTranscript = "";
            isRecording = true;
            audioPlayer.pause();
            
            try {
                recognition.start();
                const btn = document.getElementById('mic-btn');
                btn.classList.add('recording');
                btn.innerHTML = "⏹️";
                document.getElementById('status-text').innerText = "🎧 กำลังฟัง... กดอีกครั้งเพื่อส่ง";
            } catch (e) { console.error(e); }
        }

        function stopRecordingAndSend() {
            isRecording = false;
            try { recognition.stop(); } catch(e) {}
            
            const btn = document.getElementById('mic-btn');
            btn.classList.remove('recording');
            btn.innerHTML = "⌛";
            
            if (finalTranscript.trim().length > 1) {
                sendToAI(finalTranscript);
            } else {
                resetUI();
                document.getElementById('status-text').innerText = "⚠️ ไม่ได้ยินเสียงพูด กรุณาลองใหม่";
            }
        }

        async function sendToAI(text) {
            isProcessing = true;
            document.getElementById('mic-btn').disabled = true;
            document.getElementById('status-text').innerText = "⌛ น้องฟ้ากำลังประมวลผล...";

            const chatBox = document.getElementById('chat-box');
            chatBox.innerHTML += `<div class="msg staff"><b>คุณ:</b> ${text}</div>`;
            history.push("พนักงาน: " + text);
            chatBox.scrollTop = chatBox.scrollHeight;

            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: text, lvl: activeLevel, history: history})
                });
                const data = await res.json();
                
                chatBox.innerHTML += `<div class="msg customer"><b>${customers[activeLevel].name}:</b> ${data.reply}</div>`;
                history.push(customers[activeLevel].name + ": " + data.reply);
                chatBox.scrollTop = chatBox.scrollHeight;

                if (data.audio) {
                    audioPlayer.src = "data:audio/mp3;base64," + data.audio;
                    document.getElementById('status-text').innerText = "🔈 น้องฟ้ากำลังพูด...";
                    await audioPlayer.play();
                    audioPlayer.onended = () => { resetUI(); };
                } else {
                    resetUI();
                }
            } catch (e) { resetUI(); }
        }

        function resetUI() {
            isProcessing = false;
            isRecording = false;
            const btn = document.getElementById('mic-btn');
            btn.disabled = false;
            btn.innerHTML = "🎤";
            btn.classList.remove('recording');
            document.getElementById('status-text').innerText = "✅ พร้อมคุยต่อ กดไมค์เพื่อเริ่มพูด";
            document.getElementById('eval-btn').style.display = 'block';
        }

        function unlockAudio() {
            const silent = new Audio("data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=");
            silent.play().catch(e => {});
        }

        async function showEvaluation() {
            // โค้ดส่วนประเมินผลคงเดิม...
        }
    </script>
</body>
</html>
"""

# --- [ส่วนที่ 4: Server Routes คงเดิม] ---
@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE, CUSTOMERS=CUSTOMERS)

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    lvl, user_msg = data.get('lvl'), data.get('message')
    history = data.get('history', [])
    cust = CUSTOMERS[lvl]
    context = "\\n".join(history[-5:])
    full_prompt = f"System: {cust['prompt']}\\n\\nHistory:\\n{context}\\nUser: {user_msg}"
    response = model.generate_content(full_prompt)
    reply_text = response.text
    audio_data = get_audio_base64(reply_text, cust['voice'])
    return jsonify({"reply": reply_text, "audio": audio_data})

if __name__ == "__main__":
    app.run(debug=True)
