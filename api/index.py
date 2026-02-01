import os
import requests
import re
import random
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai

app = Flask(__name__)

# --- [ส่วนที่ 1: ตั้งค่า API Keys] ---
GENAI_API_KEY = os.environ.get("GENAI_API_KEY")
TTS_API_KEY = os.environ.get("TTS_API_KEY")
genai.configure(api_key=GENAI_API_KEY)

# --- [ส่วนที่ 2: คลังลูกค้า 5 ประเภท] ---
CUSTOMERS = [
    {
        "id": "veena",
        "name": "คุณวีณา",
        "desc": "แม่บ้านวัย 40 (ยากมาก - ชอบอ้างสามี/ติดประชุม)",
        "prompt": "คุณคือ 'คุณวีณา' อายุ 40 สุภาพแต่ใจแข็งมาก จะปฏิเสธสายในตอนต้นว่า 'ติดประชุม' หรือ 'ยุ่งอยู่' ตลอด พนักงานต้องโน้มน้าวเก่งจริงๆ ถึงจะยอมฟัง และสุดท้ายต้องขอปรึกษาสามีก่อนเสมอ ยกเว้นพนักงานจะพูดเรื่องความคุ้มครองลูกได้ดีมากถึงจะยอมตกลง"
    },
    {
        "id": "somchai",
        "name": "คุณสมชาย",
        "desc": "คุณลุงเกษียณใจดี (ปานกลาง - ขี้เหงา ชอบชวนคุยออกนอกเรื่อง)",
        "prompt": "คุณคือ 'คุณสมชาย' อายุ 65 เกษียณแล้ว ใจดี ขี้เหงา ชอบชวนคุยเรื่องลูกหลานและอดีต พนักงานต้องดึงคุณกลับมาเรื่องประกันให้ได้ ถ้าดูแลความรู้สึกคุณดี คุณจะยอมทำประกันเพื่อเป็นมรดกให้หลาน และยอมให้ข้อมูลลงทะเบียนง่ายๆ"
    },
    {
        "id": "kanya",
        "name": "คุณกัญญา",
        "desc": "สาวออฟฟิศจอมเนี้ยบ (ยาก - เน้นตัวเลขและผลประโยชน์)",
        "prompt": "คุณคือ 'คุณกัญญา' นักการเงินสาววัย 30 พูดจาฉะฉาน เน้นถามเรื่อง IRR และความคุ้มครองที่คุ้มค่าที่สุด ถ้าพนักงานคำนวณเลขไม่เคลียร์คุณจะวางสายทันที แต่ถ้าเขาเสนอแผนที่ประหยัดภาษีได้ดี คุณจะตกลง"
    },
    {
        "id": "prasert",
        "name": "คุณประเสริฐ",
        "desc": "เจ้าของอู่รถ (ยาก - เคยมีประสบการณ์แย่กับประกัน)",
        "prompt": "คุณคือ 'คุณประเสริฐ' อายุ 50 พูดจาโผงผาง ไม่เชื่อใจประกันเพราะเคยเคลมยาก พนักงานต้องใช้ความจริงใจและอธิบายเรื่องบริการหลังการขายให้ชัดเจนถึงจะยอมเปิดใจ"
    },
    {
        "id": "suda",
        "name": "น้องสุดา",
        "desc": "เด็กจบใหม่ (ง่าย - สนใจเทรนด์ใหม่ๆ)",
        "prompt": "คุณคือ 'สุดา' อายุ 23 เพิ่งทำงาน อยากมีประกันเล่มแรกเพราะเห็นเพื่อนทำกัน พนักงานต้องแนะนำแบบที่เบี้ยไม่แพงและคุ้มครองอุบัติเหตุ คุณจะตกลงง่ายถ้าพนักงานพูดจาเป็นกันเอง"
    }
]

model = genai.GenerativeModel(model_name="gemini-2.5-flash")

def get_audio_base64(text):
    if not TTS_API_KEY: return None
    clean_text = re.sub(r'\(.*?\)', '', text)
    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={TTS_API_KEY}"
    payload = {
        "input": {"text": clean_text},
        "voice": {"languageCode": "th-TH", "name": "th-TH-Standard-A"},
        "audioConfig": {"audioEncoding": "MP3"}
    }
    try:
        response = requests.post(url, json=payload)
        return response.json().get("audioContent") if response.status_code == 200 else None
    except: return None

# --- [ส่วนที่ 4: UI ใหม่ รองรับ PDF และใบเซอร์ฯ] ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Insurance Sales Pro Simulator</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <style>
        :root { --primary: #1e3a8a; --accent: #dc2626; --gold: #d4af37; }
        body { font-family: 'Sarabun', sans-serif; background: #e2e8f0; margin: 0; padding: 10px; }
        .app-container { max-width: 500px; margin: auto; background: white; min-height: 90vh; display: flex; flex-direction: column; border-radius: 15px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.2); }
        .header { background: var(--primary); color: white; padding: 20px; text-align: center; border-bottom: 5px solid var(--accent); }
        #chat-box { flex: 1; overflow-y: auto; padding: 15px; display: flex; flex-direction: column; gap: 10px; background: #f8fafc; }
        .msg { padding: 10px 15px; border-radius: 10px; max-width: 80%; font-size: 0.9rem; }
        .staff { align-self: flex-end; background: var(--primary); color: white; }
        .customer { align-self: flex-start; background: #e5e7eb; color: #1f2937; }
        .controls { padding: 20px; text-align: center; background: white; border-top: 1px solid #ddd; }
        .btn-mic { width: 70px; height: 70px; border-radius: 50%; border: none; background: var(--accent); color: white; font-size: 30px; cursor: pointer; }
        .btn-mic.active { animation: pulse 1s infinite; background: #991b1b; }
        @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(220,38,38,0.7); } 70% { box-shadow: 0 0 0 15px rgba(220,38,38,0); } 100% { box-shadow: 0 0 0 0 rgba(220,38,38,0); } }
        .btn-action { margin-top: 10px; padding: 10px; width: 100%; border-radius: 5px; border: 1px solid var(--primary); background: white; color: var(--primary); font-weight: bold; cursor: pointer; display: none; }
        
        /* Modal Style for Evaluation & Certificate */
        #result-modal { display: none; position: fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); z-index: 100; overflow-y: auto; padding: 20px; box-sizing: border-box; }
        .modal-content { background: white; padding: 30px; border-radius: 10px; max-width: 600px; margin: auto; position: relative; }
        .cert-card { border: 10px double var(--gold); padding: 40px; text-align: center; background: #fffdf5; margin-top: 20px; }
        .cert-card h1 { color: var(--gold); font-family: 'Times New Roman', serif; }
    </style>
</head>
<body>
    <div class="app-container">
        <div class="header">
            <h2 id="cust-name">กำลังสุ่มลูกค้า...</h2>
            <div id="cust-desc" style="font-size: 0.8rem; opacity: 0.8;"></div>
            <div id="status">แตะไมค์เพื่อเริ่มคุย</div>
        </div>
        <div id="chat-box"></div>
        <div class="controls">
            <button id="mic-btn" class="btn-mic" onclick="toggleListen()">🎤</button>
            <button id="eval-btn" class="btn-action" onclick="showEvaluation()">📥 ดูผลประเมินและดาวน์โหลด</button>
        </div>
    </div>

    <div id="result-modal">
        <div class="modal-content">
            <button onclick="document.getElementById('result-modal').style.display='none'" style="float:right">❌ ปิด</button>
            <div id="pdf-area">
                <div id="eval-text"></div>
                <div id="cert-area" style="display: none;">
                    <div class="cert-card">
                        <p>--- TOP SALES CERTIFICATE ---</p>
                        <h1>ใบประกาศเกียรติคุณ</h1>
                        <p>ขอมอบให้แก่พนักงานขายยอดเยี่ยม</p>
                        <h2 id="user-display-name">ยอดนักขายมือโปร</h2>
                        <p>ที่สามารถปิดการขายลูกค้าที่ยากที่สุดได้สำเร็จ</p>
                        <p><i>ให้ไว้ ณ วันที่ 1 กุมภาพันธ์ 2026</i></p>
                    </div>
                </div>
            </div>
            <button class="btn-action" style="display:block; background: var(--primary); color:white" onclick="downloadPDF()">💾 ดาวน์โหลดเป็นไฟล์ PDF</button>
        </div>
    </div>

    <script>
        let history = [];
        let currentCustomer = {};
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        let recognition = new SpeechRecognition();
        recognition.lang = 'th-TH';

        // 1. สุ่มลูกค้าเมื่อโหลดหน้าเว็บ
        async function startSession() {
            const res = await fetch('/api/get_customer');
            currentCustomer = await res.json();
            document.getElementById('cust-name').innerText = "คุยกับ: " + currentCustomer.name;
            document.getElementById('cust-desc').innerText = currentCustomer.desc;
        }
        startSession();

        recognition.onresult = (e) => sendToAI(e.results[0][0].transcript);
        recognition.onend = () => document.getElementById('mic-btn').classList.remove('active');

        function toggleListen() {
            recognition.start();
            document.getElementById('mic-btn').classList.add('active');
            document.getElementById('status').innerText = "กำลังฟัง...";
        }

        async function sendToAI(text) {
            const chatBox = document.getElementById('chat-box');
            chatBox.innerHTML += `<div class="msg staff"><b>คุณ:</b> ${text}</div>`;
            history.push("พนักงาน: " + text);
            document.getElementById('status').innerText = "ลูกค้ากำลังคิด...";

            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: text, customer_prompt: currentCustomer.prompt})
            });
            const data = await res.json();
            chatBox.innerHTML += `<div class="msg customer"><b>${currentCustomer.name}:</b> ${data.reply}</div>`;
            history.push(currentCustomer.name + ": " + data.reply);
            chatBox.scrollTop = chatBox.scrollHeight;
            document.getElementById('eval-btn').style.display = 'block';

            if(data.audio) {
                const audio = new Audio("data:audio/mp3;base64," + data.audio);
                audio.play();
                document.getElementById('status').innerText = "ลูกค้ากำลังพูด...";
                audio.onended = () => document.getElementById('status').innerText = "คุยต่อได้เลย";
            }
        }

        async function showEvaluation() {
            document.getElementById('result-modal').style.display = 'block';
            document.getElementById('eval-text').innerText = "กำลังประมวลผลคะแนน...";
            
            const res = await fetch('/api/evaluate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({history: history.join("\\n")})
            });
            const data = await res.json();
            document.getElementById('eval-text').innerHTML = "<h2>ผลประเมิน</h2>" + data.evaluation.replace(/\\n/g, '<br>');
            
            // ถ้าปิดการขายได้ (มีคำว่า "สำเร็จ" หรือ "ตกลง") จะโชว์ใบเซอร์
            if (data.is_closed) {
                document.getElementById('cert-area').style.display = 'block';
            }
        }

        function downloadPDF() {
            const element = document.getElementById('pdf-area');
            html2pdf().from(element).set({
                margin: 10,
                filename: 'Sales_Evaluation.pdf',
                image: { type: 'jpeg', quality: 0.98 },
                html2canvas: { scale: 2 },
                jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
            }).save();
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home(): return render_template_string(HTML_TEMPLATE)

@app.route('/api/get_customer')
def get_customer():
    return jsonify(random.choice(CUSTOMERS))

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    user_msg = data.get('message')
    cust_prompt = data.get('customer_prompt')
    
    # สร้าง response โดยใช้ Prompt ของลูกค้าที่สุ่มได้
    response = model.generate_content([
        {"role": "user", "parts": [f"System: {cust_prompt}\\nUser: {user_msg}"]}
    ])
    reply_text = response.text
    audio_data = get_audio_base64(reply_text)
    return jsonify({"reply": reply_text, "audio": audio_data})

@app.route('/api/evaluate', methods=['POST'])
def evaluate():
    history = request.json.get('history')
    prompt = f"คุณคือโค้ชสอนการขาย ประเมินบทสนทนานี้ ให้คะแนน 1-10 และสรุปว่า 'ปิดการขายสำเร็จหรือไม่' โดยถ้าพนักงานทำได้ดีจนลูกค้าตกลงซื้อ ให้ตอบคำว่า [CLOSED_SUCCESS] ไว้ในบรรทัดแรก: {history}"
    evaluation = model.generate_content(prompt).text
    is_closed = "[CLOSED_SUCCESS]" in evaluation
    return jsonify({"evaluation": evaluation, "is_closed": is_closed})

if __name__ == "__main__":
    app.run(debug=True)
