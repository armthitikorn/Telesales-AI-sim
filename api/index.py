import os
import requests
import re
import json
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai

app = Flask(__name__)

# --- [ส่วนที่ 1: ตั้งค่า API - อัปเกรดเป็น Gemini 3.1 Flash-Lite] ---
GENAI_API_KEY = os.environ.get("GENAI_API_KEY")
TTS_API_KEY = os.environ.get("TTS_API_KEY")

genai.configure(api_key=GENAI_API_KEY)

# ใช้รุ่น 3.1 Flash-Lite: เร็วที่สุดในปัจจุบัน (Low Latency) และฉลาดในเชิงตรรกะมนุษย์
model = genai.GenerativeModel(
    model_name="gemini-3.1-flash-lite-preview"
)

# --- [ส่วนที่ 2: ลอจิกการโต้ตอบแบบสมจริง (Universal Persona-Based)] ---
COLD_CALL_RULES = """
[คำสั่งเด็ดขาด]: คุณคือ "ลูกค้าตัวจริง" ที่กำลังยุ่ง ห้ามสวมบทบาทพนักงานหรือครูฝึกเด็ดขาด
1. [ความสมจริง]: ตอบให้สั้น กระชับ (Short & Blunt) เหมือนคนรับสายแปลกๆ ห้ามพูดยาวเกิน 2 ประโยคในช่วงแรก
2. [ห้ามสอนงาน/ห้ามไกด์]: ห้ามแนะนำหรือเตือนพนักงานเรื่องการพูดสคริปต์ (เช่น ห้ามพูดว่า "คุณยังไม่ได้แจ้งเลขใบอนุญาตนะ") หากเขาทำผิดกฎ คุณแค่ต้องรู้สึก "ไม่ไว้ใจ" และถามจี้ว่า "คุณเป็นใครนะ?", "โทรมาจากไหน?"
3. [เปิดรับทุกประกัน]: คุณพร้อมฟังประกันทุกรูปแบบ (ชีวิต, สุขภาพ, ออมทรัพย์, รถยนต์, มรดก) โดยให้ตัดสินใจโต้ตอบตาม "พื้นฐานชีวิต" ของคุณ
4. [ตรรกะการปฏิเสธ]: ปฏิเสธแบบคนทั่วไปในช่วงแรก เช่น "ไม่ว่าง", "มีเยอะแล้ว", "ติดธุระ" จนกว่าพนักงานจะมีจุดสนใจ (Hook) ที่ตรงกับชีวิตคุณจริงๆ
5. [ภาษา]: ใช้ภาษาพูดธรรมชาติ (Natural Thai) ไม่ต้องสุภาพเป็นทางการเหมือนหุ่นยนต์
"""

CUSTOMERS = {
    "1": {
        "name": "น้องฟ้า", 
        "desc": "พนักงานออฟฟิศจบใหม่ (First Jobber)", 
        "prompt": COLD_CALL_RULES + "คุณคือ 'ฟ้า' อายุ 23 ปี เพิ่งเริ่มทำงาน เงินเดือนยังน้อย ห่วงเรื่องการออมเงินและการใช้จ่ายรายวัน ถ้าเสนอประกันที่เบี้ยแพงเกินไปจะบ่นทันที ลงท้าย 'ค่ะ' แบบรีบๆ", 
        "voice": {"name": "th-TH-Chirp3-HD-Aoede", "gender": "FEMALE"} 
    },
    "2": {
        "name": "เฮียวิรัช", 
        "desc": "เจ้าของอู่ซ่อมรถ (SME Owner)", 
        "prompt": COLD_CALL_RULES + "คุณคือ 'วิรัช' อายุ 45 ปี มีครอบครัว กังวลเรื่องค่ารักษาพยาบาลที่แพงขึ้นและภาษีธุรกิจ ชอบคุยเรื่องความคุ้มค่าและตัวเลขตรงๆ ลงท้าย 'ครับ'", 
        "voice": {"name": "th-TH-Chirp3-HD-Achird", "gender": "MALE"}
    },
    "3": {
        "name": "ป้ามาลี", 
        "desc": "แม่ค้าตลาดสด (คนหัวเก่า)", 
        "prompt": COLD_CALL_RULES + "คุณคือ 'ป้ามาลี' อายุ 60 ปี มีเงินเก็บแต่ไม่ไว้ใจบริษัทประกัน ชอบถามว่า 'ตายแล้วได้เงินจริงไหม' 'เบิกยากไหม' เน้นภาษาชาวบ้าน ลงท้าย 'จ๊ะ/ค่ะ'", 
        "voice": {"name": "th-TH-Chirp3-HD-Kore", "gender": "FEMALE"} 
    },
    "4": {
        "name": "คุณแอน", 
        "desc": "คุณแม่ลูกอ่อน (สายปกป้องลูก)", 
        "prompt": COLD_CALL_RULES + "คุณคือ 'แอน' อายุ 32 ปี ห่วงลูกมากที่สุด อะไรที่เป็นประโยชน์กับลูกจะยอมฟัง แต่ถ้าโทรมาจังหวะลูกร้องจะหงุดหงิดมาก ลงท้าย 'ค่ะ'", 
        "voice": {"name": "th-TH-Chirp3-HD-Leda", "gender": "FEMALE"} 
    },
    "5": {
        "name": "คุณอัครเดช", 
        "desc": "ผู้บริหารระดับสูง (HNW)", 
        "prompt": COLD_CALL_RULES + "คุณคือ 'อัครเดช' อายุ 55 ปี รู้เรื่องการเงินดีมาก ถ้าพนักงานพูดจาวนไปวนมาหรือไม่มืออาชีพจะวางสายทันที สนใจเรื่องการส่งต่อมรดกและภาษี ลงท้าย 'ครับ'", 
        "voice": {"name": "th-TH-Chirp3-HD-Charon", "gender": "MALE"} 
    }
}

def get_audio_base64(text, voice_config):
    if not TTS_API_KEY: return None
    # ทำความสะอาดข้อความก่อนส่งไป TTS
    clean_text = re.sub(r'^.*?:', '', text)
    clean_text = re.sub(r'\(.*?\)', '', clean_text).replace('*', '').strip()
    if not clean_text: return None
    
    url = f"https://texttospeech.googleapis.com/v1beta1/text:synthesize?key={TTS_API_KEY}"
    voice_name = voice_config["name"]
    payload = {
        "input": {"text": clean_text},
        "voice": {
            "languageCode": "th-TH", 
            "name": voice_name,
            "ssmlGender": voice_config.get("gender", "FEMALE")
        },
        "audioConfig": {"audioEncoding": "MP3"}
    }
    
    try:
        res = requests.post(url, json=payload, timeout=10)
        res_json = res.json()
        return res_json.get("audioContent")
    except: return None

# --- [ส่วนที่ 3: UI และ HTML Template (คงเดิมแต่ปรับปรุงส่วนแสดงผล)] ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Sales Mastery Simulator v3.1</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <style>
        :root { --blue: #1e3a8a; --red: #be123c; --gray: #94a3b8; --gold: #b45309; --green: #15803d; }
        body { font-family: sans-serif; background: #f1f5f9; margin:0; }
        #lobby { padding: 20px; text-align: center; max-width: 600px; margin: auto; }
        input[type="text"] { padding: 15px; width: 85%; border-radius: 8px; border: 1px solid #ddd; font-size: 16px; box-sizing: border-box; }
        .card { background: white; padding: 15px; margin: 10px 0; border-radius: 12px; border-left: 8px solid var(--blue); text-align: left; cursor: pointer; transition: 0.2s; }
        .card:hover { transform: scale(1.02); }
        #main-app { display: none; flex-direction: column; height: 100vh; background: white; }
        .header { background: var(--blue); color: white; padding: 15px; text-align: center; }
        #chat-box { flex: 1; overflow-y: auto; padding: 15px; display: flex; flex-direction: column; gap: 10px; background: #f8fafc; }
        .msg { padding: 10px 15px; border-radius: 15px; max-width: 85%; line-height: 1.4; word-wrap: break-word; }
        .staff { align-self: flex-end; background: var(--blue); color: white; }
        .customer { align-self: flex-start; background: #e2e8f0; color: #1e293b; }
        .controls { padding: 15px; text-align: center; background: white; border-top: 1px solid #ddd; }
        .btn-mic { width: 70px; height: 70px; border-radius: 50%; border: none; background: var(--red); color: white; font-size: 30px; cursor: pointer; margin-bottom: 5px; }
        .btn-mic:disabled { background: var(--gray) !important; opacity: 0.6; }
        .fallback-input-container { display: flex; gap: 8px; margin-top: 10px; justify-content: center; }
        .fallback-input-container input { width: 75%; padding: 12px; font-size: 16px; margin: 0; }
        .fallback-input-container button { padding: 12px 20px; background: var(--blue); color: white; border: none; border-radius: 8px; cursor: pointer; }
        
        #eval-modal { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); z-index:1000; overflow-y:auto; }
        .eval-content { background:white; max-width:600px; margin:30px auto; padding:25px; border-radius:15px; }
        .score-box { text-align:center; padding:20px; border-radius:10px; margin-bottom:20px; color:white; font-size:24px; font-weight:bold; }
        .pass { background: var(--green); }
        .fail { background: var(--red); }
        .feedback-box { background: #f1f5f9; padding: 15px; border-left: 5px solid var(--blue); margin-bottom: 15px; border-radius: 5px; }
        .eval-item { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #eee; font-size: 14px; }
        .stars { color: #eab308; font-weight: bold; }
        #cert-area { display:none; background: white; padding: 40px; border: 15px double var(--gold); text-align: center; }
    </style>
</head>
<body>
    <audio id="audio-player" playsinline style="display:none;"></audio>

    <div id="lobby">
        <h1 style="color: var(--blue)">🏆 Sales Mastery Academy</h1>
        <p>ยกระดับทักษะการโทรด้วย AI Simulator รุ่น 3.1 Flash-Lite</p>
        <input type="text" id="staff-name" placeholder="ระบุชื่อพนักงานเพื่อเริ่มการทดสอบ">
        <div id="customer-list"></div>
    </div>

    <div id="main-app">
        <div class="header"><h2 id="active-name" style="margin:0;">ลูกค้า</h2></div>
        <div id="chat-box"></div>
        <div class="controls">
            <button id="mic-btn" class="btn-mic" onclick="toggleListen()">🎤</button>
            <p id="status" style="margin: 0; font-size: 14px; color: #64748b;">แตะไมค์เพื่อพูด</p>
            
            <div class="fallback-input-container">
                <input type="text" id="text-fallback" placeholder="หรือพิมพ์โต้ตอบที่นี่..." onkeypress="handleEnter(event)">
                <button onclick="sendFallbackText()">ส่ง</button>
            </div>

            <button id="eval-btn" style="display:none; width:100%; padding:15px; border-radius:30px; border:2px solid var(--blue); color:var(--blue); background:none; font-weight:bold; margin-top: 15px;" onclick="showEvaluation()">🏁 ประเมินผล QC Matrix</button>
        </div>
    </div>

    <!-- Modal และหน้ารายงาน (คงไว้ตามเดิม) -->
    <div id="eval-modal">
        <div class="eval-content" id="eval-report-container">
            <div id="eval-printable-area">
                <h2 style="text-align:center; color:var(--blue);">📊 รายงานผลการทดสอบสคริปต์</h2>
                <p style="text-align:center; font-weight:bold;">พนักงาน: <span id="report-staff-name"></span> | ลูกค้า: <span id="report-customer-name"></span></p>
                <div id="score-banner" class="score-box pass">รอผลประเมิน...</div>
                
                <div class="feedback-box">
                    <b>💪 จุดแข็ง:</b> <span id="fb-strength"></span>
                </div>
                <div class="feedback-box" style="border-left-color: var(--red);">
                    <b>⚠️ จุดอ่อน:</b> <span id="fb-weakness"></span>
                </div>
                <div class="feedback-box" style="border-left-color: var(--gold);">
                    <b>📈 จุดที่ต้องพัฒนา:</b> <span id="fb-improve"></span>
                </div>
                
                <h3 style="margin-top:20px;">รายละเอียดคะแนน (QC Matrix)</h3>
                <div id="eval-details"></div>
            </div>
            
            <div data-html2canvas-ignore="true">
                <button onclick="downloadEvalPDF()" style="width:100%; padding:15px; background:var(--green); color:white; border:none; border-radius:8px; margin-top:20px; font-size:16px;">📥 ดาวน์โหลดผลประเมิน (PDF)</button>
                <button onclick="closeEvaluation()" style="width:100%; padding:15px; background:var(--blue); color:white; border:none; border-radius:8px; margin-top:10px; font-size:16px;">ปิดหน้าต่าง</button>
                <button id="cert-btn" onclick="generateCert()" style="display:none; width:100%; padding:15px; background:var(--gold); color:white; border:none; border-radius:8px; margin-top:10px; font-size:16px;">🎓 รับใบประกาศนียบัตร</button>
            </div>
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
        var recognition = SpeechRecognition ? new SpeechRecognition() : null;
        if(recognition) recognition.lang = 'th-TH';
        
        var audioPlayer = document.getElementById('audio-player');

        const criteriaList = [
            "4. แจ้งชื่อ-นามสกุล พนักงาน", "5. แจ้งเลขที่ใบอนุญาต และรหัสพนักงาน",
            "6. แจ้งชื่อบริษัทต้นสังกัด", "7. ถามความสะดวก และขออนุญาตบันทึกเทป",
            "8. บทเปิดตัวมีการเชื่อมโยง/โน้มน้าว", "9. นำเสนอผลิตภัณฑ์ อธิบายผลประโยชน์/เงื่อนไข/ข้อยกเว้น",
            "10. แจ้งค่าเบี้ยประกัน", "11. อธิบายมูลค่ากรมธรรม์/การเวนคืน",
            "12. อธิบายการลดหย่อนภาษี", "13. ตอบข้อโต้แย้งชัดเจน ตรงประเด็น โน้มน้าว",
            "14. อธิบายวิธีการสมัครและชำระเบี้ย", "15. ใช้ประโยคปิดการขายไม่น้อยกว่า 3 ครั้ง",
            "16. ประโยคสคริปต์การขายโดยรวม", "17. น้ำเสียงสร้างความประทับใจให้ลูกค้า",
            "18. ควบคุมสถานการณ์ อารมณ์ และน้ำเสียงได้", "19. ทักษะไหวพริบการรับฟัง ตอบคำถาม",
            "20. พนักงานสามารถฝึกฝนและพัฒนาต่อได้"
        ];

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
            if(!document.getElementById('staff-name').value) { alert("กรุณาระบุชื่อพนักงานก่อนครับ"); return; }
            activeLvl = lvl;
            document.getElementById('lobby').style.display = 'none';
            document.getElementById('main-app').style.display = 'flex';
            document.getElementById('active-name').innerText = customers[lvl].name;
            unlockAudio();
        }

        function unlockAudio() {
            audioPlayer.src = "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=";
            audioPlayer.play().catch(e => console.log("Audio unlock interaction needed"));
        }

        function b64toBlobUrl(b64Data, contentType='audio/mp3') {
            try {
                const byteCharacters = atob(b64Data);
                const byteArrays = [];
                for (let offset = 0; offset < byteCharacters.length; offset += 512) {
                    const slice = byteCharacters.slice(offset, offset + 512);
                    const byteNumbers = new Array(slice.length);
                    for (let i = 0; i < slice.length; i++) {
                        byteNumbers[i] = slice.charCodeAt(i);
                    }
                    byteArrays.push(new Uint8Array(byteNumbers));
                }
                return URL.createObjectURL(new Blob(byteArrays, {type: contentType}));
            } catch (e) { return null; }
        }

        if(recognition) {
            recognition.onresult = function(e) {
                var t = e.results[0][0].transcript;
                if (t.length > 0 && !isThinking) { sendToAI(t); }
            };
            recognition.onend = function() { resetMicUI(); };
        }

        function toggleListen() {
            if (isThinking) return;
            unlockAudio();
            if(!recognition) { alert("เบราว์เซอร์ไม่รองรับ Speech Recognition"); return; }
            try {
                recognition.start();
                document.getElementById('mic-btn').style.opacity = "0.5";
                document.getElementById('status').innerText = "กำลังฟัง... (พูดได้เลย)";
            } catch(e) {}
        }

        function resetMicUI() {
            document.getElementById('mic-btn').style.opacity = "1";
            document.getElementById('status').innerText = "แตะไมค์เพื่อพูด หรือพิมพ์ข้อความ";
        }

        function handleEnter(e) { if(e.key === 'Enter') sendFallbackText(); }

        function sendFallbackText() {
            var input = document.getElementById('text-fallback');
            var t = input.value.trim();
            if(t !== "" && !isThinking) {
                input.value = "";
                sendToAI(t);
            }
        }

        function appendMessage(role, name, text) {
            var box = document.getElementById('chat-box');
            var div = document.createElement('div');
            div.className = "msg " + role;
            div.innerHTML = "<b>" + name + ":</b> " + text;
            box.appendChild(div);
            box.scrollTop = box.scrollHeight;
            return div;
        }

        async function sendToAI(t) {
            isThinking = true;
            document.getElementById('mic-btn').disabled = true;
            document.getElementById('status').innerText = "⌛ ลูกค้ากำลังคิด...";
            
            appendMessage('staff', 'คุณ', t);
            history_log.push("พนักงาน: " + t);

            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: t, lvl: activeLvl, history: history_log})
                });
                const data = await res.json();
                var cleanReply = data.reply.replace(/^.*?:/g, '').trim();
                
                var botMessageDiv = appendMessage('customer', customers[activeLvl].name, cleanReply);
                history_log.push(customers[activeLvl].name + ": " + cleanReply);

                if (data.audio) {
                    const blobUrl = b64toBlobUrl(data.audio);
                    if (blobUrl) {
                        audioPlayer.src = blobUrl;
                        audioPlayer.play().catch(e => {
                            const playBtn = document.createElement('button');
                            playBtn.innerText = "🔊 กดเพื่อฟังเสียง";
                            playBtn.onclick = () => audioPlayer.play();
                            botMessageDiv.appendChild(playBtn);
                        });
                        audioPlayer.onended = () => { resetUI(); };
                    } else { resetUI(); }
                } else { resetUI(); }
            } catch (e) { resetUI(); }
        }

        function resetUI() {
            isThinking = false;
            document.getElementById('mic-btn').disabled = false;
            document.getElementById('status').innerText = "✅ พร้อมคุยต่อ";
            document.getElementById('eval-btn').style.display = 'block';
        }

        async function showEvaluation() {
            document.getElementById('status').innerText = "⌛ กำลังตรวจสอบ QC Matrix...";
            try {
                const res = await fetch('/api/evaluate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({history: history_log.join("\\n")})
                });
                const data = await res.json();
                
                document.getElementById('report-staff-name').innerText = document.getElementById('staff-name').value;
                document.getElementById('report-customer-name').innerText = customers[activeLvl].name;

                const banner = document.getElementById('score-banner');
                banner.innerText = "คะแนนรวม: " + data.total + "/85 (" + (data.passed ? "ผ่านเกณฑ์" : "ไม่ผ่านเกณฑ์") + ")";
                banner.className = data.passed ? "score-box pass" : "score-box fail";
                
                document.getElementById('fb-strength').innerText = data.strengths;
                document.getElementById('fb-weakness').innerText = data.weaknesses;
                document.getElementById('fb-improve').innerText = data.improvements;
                
                let detailsHTML = "";
                for(let i=0; i<17; i++) {
                    let score = data.scores[i] || 0;
                    detailsHTML += `<div class="eval-item"><span>${criteriaList[i]}</span><span class="stars">${"⭐".repeat(score)}${"❌".repeat(5-score)} (${score}/5)</span></div>`;
                }
                document.getElementById('eval-details').innerHTML = detailsHTML;
                if(data.passed && activeLvl === "5") document.getElementById('cert-btn').style.display = "block";
                document.getElementById('eval-modal').style.display = "block";
                document.getElementById('status').innerText = "✅ ประเมินเสร็จสิ้น";
            } catch (e) { alert("การประเมินผิดพลาด"); }
        }
        
        function closeEvaluation() { document.getElementById('eval-modal').style.display = "none"; }
        function downloadEvalPDF() {
            var element = document.getElementById('eval-printable-area');
            html2pdf().from(element).save('QC_Report_' + document.getElementById('staff-name').value + '.pdf');
        }
        function generateCert() {
            document.getElementById('pdf-staff').innerText = document.getElementById('staff-name').value;
            var el = document.getElementById('cert-area');
            el.style.display = 'block';
            html2pdf().from(el).save().then(() => el.style.display = 'none');
        }
    </script>
</body>
</html>
"""

# --- [ส่วนที่ 4: เชื่อมต่อ API และประมวลผล] ---
@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE, CUSTOMERS=CUSTOMERS)

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        lvl, user_msg, history = data.get('lvl'), data.get('message'), data.get('history', [])
        cust = CUSTOMERS[lvl]
        context = "\n".join(history[-5:]) # ส่งเฉพาะ 5 ล่าสุดเพื่อความไวและประหยัด token
        
        full_prompt = f"{cust['prompt']}\nประวัติคุย: {context}\nพนักงาน: {user_msg}\nลูกค้าตอบกลับสั้นๆ:"
        
        response = model.generate_content(full_prompt)
        reply_text = response.text
        audio_data = get_audio_base64(reply_text, cust['voice'])
        return jsonify({"reply": reply_text, "audio": audio_data})
    except Exception as e:
        return jsonify({"reply": f"เกิดข้อผิดพลาด: {str(e)}", "audio": None}), 500

@app.route('/api/evaluate', methods=['POST'])
def evaluate():
    try:
        history = request.json.get('history', '')
        eval_prompt = f"""
        วิเคราะห์ประวัติการขายประกันนี้ตาม QC Matrix 17 ข้อ (ข้อ 4-20) 
        ประวัติ: {history}
        
        ให้คะแนน 1-5 ดาว ในแต่ละข้อ และสรุปจุดแข็ง จุดอ่อน จุดพัฒนา
        ตอบกลับเป็น JSON เท่านั้น:
        {{
            "scores": [คะแนนข้อ4, ..., คะแนนข้อ20],
            "strengths": "...",
            "weaknesses": "...",
            "improvements": "..."
        }}
        """
        response = model.generate_content(eval_prompt)
        result_text = response.text.strip()
        
        # คลีน JSON จาก Markdown
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()
            
        eval_data = json.loads(result_text)
        total_score = sum(eval_data.get("scores", [0]*17))
        eval_data["total"] = total_score
        eval_data["passed"] = total_score >= 50
        
        return jsonify(eval_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
