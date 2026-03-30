import os
import requests
import re
import json
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai

app = Flask(__name__)

# --- [ส่วนที่ 1: ตั้งค่า API] ---
GENAI_API_KEY = os.environ.get("GENAI_API_KEY")
TTS_API_KEY = os.environ.get("TTS_API_KEY")

genai.configure(api_key=GENAI_API_KEY)
model = genai.GenerativeModel(model_name="gemini-2.5-flash")

# --- [ส่วนที่ 2: ลอจิก Cold Call และ รายชื่อลูกค้า] ---
COLD_CALL_RULES = """
[คำสั่งเด็ดขาด]: คุณคือ "ลูกค้า" เท่านั้น ห้ามตอบหรือสวมบทบาทเป็นพนักงานเด็ดขาด
1. [การจดจำ]: อ่าน History ให้ละเอียด ห้ามถามชื่อพนักงานหรือเลขใบอนุญาตซ้ำหากเคยแจ้งแล้ว
2. [คำแทนตัว]: ผู้หญิงใช้ 'ฉัน/เรา', ผู้ชายใช้ 'ผม' 
3. [บุคลิก]: เริ่มจากไม่ไว้วางใจ ปฏิเสธการขายในช่วงแรก 4-5 รอบ จนกว่าพนักงานจะพูดถูกต้องตามกฎ คปภ.
4. [กฎการแนะนำตัว]: หากพนักงาน "ยังไม่ได้แนะนำตัวครบถ้วนไม่ต้องเตือนให้พนักงานพูด" (ชื่อ-นามสกุล, ชื่อบริษัท, เลขใบอนุญาต) แต่ห้ามยอมให้พนักงานอธิบายรายละเอียดลึกๆ ของแบบประกัน (เช่น เงื่อนไข, ข้อยกเว้น, หรือค่าเบี้ยประกัน) เด็ดขาด ให้ตัดบทหรือท้วงถามทันที
5. [การอนุโลมจุดขาย / Hook]: หากพนักงานยังไม่แนะนำตัว แต่เปิดบทสนทนาด้วย "จุดขายเพื่อดึงดูดความสนใจ" (เช่น วงเงินคุ้มครองสูง, ผลตอบแทนสูงสุด x%, เงินคืนทุกปี) ให้อนุโลมรับฟังและแสดงความสนใจได้เล็กน้อย แต่ต้องวกกลับไปถามตัวตนพนักงานเสมอ
"""

CUSTOMERS = {
    "1": {
        "name": "น้องฟ้า", 
        "desc": "ออม 20/9", 
        "prompt": COLD_CALL_RULES + "คุณคือ 'ฟ้า' อายุ 25 ปี ลงท้าย 'ค่ะ'", 
        "voice": {"name": "th-TH-Chirp3-HD-Aoede", "gender": "FEMALE"} 
    },
    "2": {
        "name": "คุณวิรัช", 
        "desc": "สุขภาพ", 
        "prompt": COLD_CALL_RULES + "คุณคือ 'วิรัช' อายุ 45 ปี ลงท้าย 'ครับ' เน้นถามเรื่องความคุ้มครองสุขภาพ", 
        "voice": {"name": "th-TH-Chirp3-HD-Achird", "gender": "MALE"}
    },
    "3": {
        "name": "คุณป้ามาลี", 
        "desc": "มรดก", 
        "prompt": COLD_CALL_RULES + "คุณคือ 'ป้ามาลี' อายุ 50 ปี ลงท้าย 'ค่ะ/จ๊ะ'", 
        "voice": {"name": "th-TH-Chirp3-HD-Kore", "gender": "FEMALE"} 
    },
    "4": {
        "name": "แม่แอน", 
        "desc": "ปฏิเสธหนัก", 
        "prompt": COLD_CALL_RULES + "คุณคือ 'แอน' ปฏิเสธเรื่องประกันตลอด", 
        "voice": {"name": "th-TH-Chirp3-HD-Leda", "gender": "FEMALE"} 
    },
    "5": {
        "name": "คุณอัครเดช", 
        "desc": "นักธุรกิจ", 
        "prompt": COLD_CALL_RULES + "คุณคือ 'อัครเดช' เวลาน้อยและดุ", 
        "voice": {"name": "th-TH-Chirp3-HD-Charon", "gender": "MALE"} 
    }
}

def get_audio_base64(text, voice_config):
    if not TTS_API_KEY: return None
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
    if "Chirp3" not in voice_name:
        payload["audioConfig"]["pitch"] = voice_config.get("pitch", 0.0)
        payload["audioConfig"]["speakingRate"] = voice_config.get("rate", 1.0)
        
    try:
        res = requests.post(url, json=payload, timeout=10)
        res_json = res.json()
        return res_json.get("audioContent")
    except: return None

# --- [ส่วนที่ 3: UI และ HTML] ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Sales Mastery Simulator</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <style>
        :root { --blue: #1e3a8a; --red: #be123c; --gray: #94a3b8; --gold: #b45309; --green: #15803d; }
        body { font-family: sans-serif; background: #f1f5f9; margin:0; }
        #lobby { padding: 20px; text-align: center; max-width: 600px; margin: auto; }
        input[type="text"] { padding: 15px; width: 85%; border-radius: 8px; border: 1px solid #ddd; font-size: 16px; box-sizing: border-box; }
        .card { background: white; padding: 15px; margin: 10px 0; border-radius: 12px; border-left: 8px solid var(--blue); text-align: left; cursor: pointer; }
        #main-app { display: none; flex-direction: column; height: 100vh; background: white; }
        .header { background: var(--blue); color: white; padding: 15px; text-align: center; }
        #chat-box { flex: 1; overflow-y: auto; padding: 15px; display: flex; flex-direction: column; gap: 10px; background: #f8fafc; }
        .msg { padding: 10px 15px; border-radius: 15px; max-width: 85%; line-height: 1.4; word-wrap: break-word; }
        .staff { align-self: flex-end; background: var(--blue); color: white; }
        .customer { align-self: flex-start; background: #e2e8f0; color: #1e293b; display: flex; flex-direction: column; gap: 5px; }
        .controls { padding: 15px; text-align: center; background: white; border-top: 1px solid #ddd; }
        .btn-mic { width: 70px; height: 70px; border-radius: 50%; border: none; background: var(--red); color: white; font-size: 30px; cursor: pointer; margin-bottom: 5px; }
        .btn-mic:disabled { background: var(--gray) !important; opacity: 0.6; }
        .fallback-input-container { display: flex; gap: 8px; margin-top: 10px; justify-content: center; }
        .fallback-input-container input { width: 75%; padding: 12px; font-size: 16px; margin: 0; }
        .fallback-input-container button { padding: 12px 20px; background: var(--blue); color: white; border: none; border-radius: 8px; font-size: 16px; cursor: pointer; }
        
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
    <!-- แก้ไข 1: เพิ่มแท็ก Audio สำหรับ iOS -->
    <audio id="audio-player" playsinline style="display:none;"></audio>

    <div id="lobby">
        <h1 style="color: var(--blue)">🏆 Sales Mastery Academy</h1>
        <input type="text" id="staff-name" placeholder="ระบุชื่อพนักงาน" style="margin-bottom: 20px;">
        <div id="customer-list"></div>
    </div>

    <div id="main-app">
        <div class="header"><h2 id="active-name" style="margin:0;">ลูกค้า</h2></div>
        <div id="chat-box"></div>
        <div class="controls">
            <button id="mic-btn" class="btn-mic" onclick="toggleListen()">🎤</button>
            <p id="status" style="margin: 0; font-size: 14px; color: #64748b;">แตะไมค์เพื่อพูด</p>
            
            <!-- แก้ไข 5: ช่องพิมพ์สำรองเผื่อไมค์ใช้ไม่ได้ -->
            <div class="fallback-input-container">
                <input type="text" id="text-fallback" placeholder="หรือพิมพ์ข้อความที่นี่..." onkeypress="handleEnter(event)">
                <button onclick="sendFallbackText()">ส่ง</button>
            </div>

            <button id="eval-btn" style="display:none; width:100%; padding:15px; border-radius:30px; border:2px solid var(--blue); color:var(--blue); background:none; font-weight:bold; margin-top: 15px;" onclick="showEvaluation()">🏁 ประเมินผล QC Matrix</button>
        </div>
    </div>

    <div id="eval-modal">
        <!-- โค้ด Modal ของเดิม -->
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
                
                <h3 style="margin-top:20px;">รายละเอียดคะแนน (17 หัวข้อ)</h3>
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
            if(!document.getElementById('staff-name').value) { alert("ระบุชื่อก่อนครับ"); return; }
            activeLvl = lvl;
            document.getElementById('lobby').style.display = 'none';
            document.getElementById('main-app').style.display = 'flex';
            document.getElementById('active-name').innerText = customers[lvl].name;
            unlockAudio();
        }

        // แก้ไข 2: ปลดล็อค Audio Context ด้วยไฟล์เสียงเงียบ
        function unlockAudio() {
            audioPlayer.src = "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=";
            var playPromise = audioPlayer.play();
            if (playPromise !== undefined) {
                playPromise.catch(function(e) { console.log("Unlock audio blocked."); });
            }
        }

        // แก้ไข 3: แปลง Base64 เป็น Blob URL
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
            } catch (e) {
                return null;
            }
        }

        if(recognition) {
            recognition.onresult = function(e) {
                var t = e.results[0][0].transcript;
                if (t.length > 0 && !isThinking) { sendToAI(t); }
            };

            recognition.onerror = function(e) {
                console.error("Speech Recognition Error:", e.error);
                document.getElementById('status').innerText = "❌ ไมค์มีปัญหา (" + e.error + ") กรุณาพิมพ์แทน";
                resetMicUI();
            };

            recognition.onend = function() {
                if(!isThinking) resetMicUI();
            };
        }

        function toggleListen() {
            if (isThinking) return;
            unlockAudio();
            
            if(!recognition) {
                alert("เบราว์เซอร์ของคุณไม่รองรับการพิมพ์ด้วยเสียง กรุณาใช้ช่องพิมพ์ข้อความครับ");
                return;
            }

            try {
                audioPlayer.pause();
                recognition.start();
                document.getElementById('mic-btn').style.opacity = "0.5";
                document.getElementById('status').innerText = "กำลังฟัง... (พูดได้เลย)";
            } catch(e) {
                console.error("Mic start error", e);
            }
        }

        function resetMicUI() {
            document.getElementById('mic-btn').style.opacity = "1";
            if(document.getElementById('status').innerText.includes("กำลังฟัง")) {
                document.getElementById('status').innerText = "แตะไมค์เพื่อพูด หรือพิมพ์ข้อความ";
            }
        }

        function handleEnter(e) {
            if(e.key === 'Enter') sendFallbackText();
        }

        function sendFallbackText() {
            var input = document.getElementById('text-fallback');
            var t = input.value.trim();
            if(t !== "" && !isThinking) {
                input.value = "";
                if(recognition) recognition.stop();
                unlockAudio(); 
                sendToAI(t);
            }
        }

        // ฟังก์ชันวาดกล่องข้อความ
        function appendMessage(role, name, text) {
            var box = document.getElementById('chat-box');
            var div = document.createElement('div');
            if (role === 'staff') {
                div.className = "msg staff";
                div.innerHTML = "<b>" + name + ":</b> " + text;
            } else {
                div.className = "msg customer";
                div.innerHTML = "<div><b>" + name + ":</b> " + text + "</div>";
            }
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
                        var playPromise = audioPlayer.play();
                        
                        if (playPromise !== undefined) {
                            playPromise.then(_ => {
                                audioPlayer.onended = function() { resetUI(); };
                            }).catch(e => {
                                console.error("Autoplay blocked by iOS:", e);
                                document.getElementById('status').innerText = "✅ พร้อมคุยต่อ (เสียงถูกระบบบล็อก)";
                                
                                // แก้ไข 4: เพิ่มปุ่มเล่นเสียงสำรองถ้า iOS บล็อก
                                const playBtn = document.createElement('button');
                                playBtn.style.cssText = "margin-top: 5px; padding: 5px 10px; background: #cbd5e1; color: #334155; border: none; border-radius: 15px; font-size: 12px; cursor: pointer;";
                                playBtn.innerHTML = "🔊 กดเพื่อฟังเสียง";
                                playBtn.onclick = () => {
                                    audioPlayer.src = blobUrl;
                                    audioPlayer.play();
                                    playBtn.remove();
                                };
                                botMessageDiv.appendChild(playBtn);
                                resetUI();
                            });
                        } else {
                            audioPlayer.onended = function() { resetUI(); };
                        }
                    } else { resetUI(); }
                } else { resetUI(); }
            } catch (e) { 
                console.error(e);
                resetUI(); 
            }
        }

        function resetUI() {
            isThinking = false;
            document.getElementById('mic-btn').disabled = false;
            resetMicUI();
            if(!document.getElementById('status').innerText.includes("ระบบบล็อก")) {
                document.getElementById('status').innerText = "✅ พร้อมคุยต่อ";
            }
            document.getElementById('eval-btn').style.display = 'block';
        }

        async function showEvaluation() {
            document.getElementById('status').innerText = "⌛ กำลังให้ AI ตรวจสอบ QC Matrix...";
            
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
                const resultText = data.passed ? "ผ่านเกณฑ์" : "ไม่ผ่านเกณฑ์";
                banner.innerText = "คะแนนรวม: " + data.total + "/85 (" + resultText + ")";
                banner.className = data.passed ? "score-box pass" : "score-box fail";
                
                document.getElementById('fb-strength').innerText = data.strengths;
                document.getElementById('fb-weakness').innerText = data.weaknesses;
                document.getElementById('fb-improve').innerText = data.improvements;
                
                let detailsHTML = "";
                for(let i=0; i<17; i++) {
                    let score = data.scores[i] || 0;
                    let stars = "⭐".repeat(score) + "❌".repeat(5-score);
                    detailsHTML += `<div class="eval-item"><span>${criteriaList[i]}</span><span class="stars">${stars} (${score}/5)</span></div>`;
                }
                document.getElementById('eval-details').innerHTML = detailsHTML;
                
                if(data.passed && activeLvl === "5") {
                    document.getElementById('cert-btn').style.display = "block";
                }
                
                document.getElementById('eval-modal').style.display = "block";
                document.getElementById('status').innerText = "✅ ประเมินเสร็จสิ้น";

            } catch (e) {
                alert("เกิดข้อผิดพลาดในการประเมินผล");
                document.getElementById('status').innerText = "✅ พร้อมคุยต่อ";
            }
        }
        
        function closeEvaluation() {
            document.getElementById('eval-modal').style.display = "none";
        }

        function downloadEvalPDF() {
            var element = document.getElementById('eval-printable-area');
            var staffName = document.getElementById('staff-name').value || 'Staff';
            var opt = {
                margin:       0.5,
                filename:     'QC_Evaluation_' + staffName + '.pdf',
                image:        { type: 'jpeg', quality: 0.98 },
                html2canvas:  { scale: 2 },
                jsPDF:        { unit: 'in', format: 'a4', orientation: 'portrait' }
            };
            html2pdf().set(opt).from(element).save();
        }
        
        function generateCert() {
            document.getElementById('pdf-staff').innerText = document.getElementById('staff-name').value;
            var el = document.getElementById('cert-area');
            el.style.display = 'block';
            html2pdf().from(el).save().then(function(){ el.style.display = 'none'; });
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
    try:
        data = request.json
        lvl, user_msg, history = data.get('lvl'), data.get('message'), data.get('history', [])
        cust = CUSTOMERS[lvl]
        
        context = "\n".join(history) 
        
        full_prompt = f"""บทบาทของคุณ: {cust['prompt']}
ประวัติการคุยตั้งแต่ต้น:
{context}
พนักงานขายพูดว่า: "{user_msg}"
จงตอบกลับในฐานะลูกค้าเท่านั้น:"""

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
        ในฐานะผู้ตรวจสอบคุณภาพ (QA) ของบริษัทประกันภัย จงประเมินบทสนทนาการขายทางโทรศัพท์ต่อไปนี้
        ประวัติการสนทนา:
        {history}

        ให้ประเมินผล 17 ข้อ (ตั้งแต่ข้อ 4 ถึงข้อ 20) โดยให้คะแนนข้อละ 1-5 ดาว 
        (1=แย่มากหรือไม่พูดถึงเลย, 5=ทำได้ดีเยี่ยมครบถ้วน)
        
        รายการประเมิน:
        4. การเปิดตัวแจ้งชื่อ-นามสกุล พนักงาน
        5. การเปิดตัวแจ้ง เลขที่ใบอนุญาต และรหัสพนักงาน
        6. การเปิดตัวแจ้ง ชื่อบริษัทต้นสังกัด
        7. การเปิดตัวแจ้ง ถามความสะดวกในการสนทนากับลูกค้า และขออนุญาตบันทึกเทป
        8. บทเปิดตัวมีการเชื่อมโยงและโน้มน้าว เพื่อนำไปสู่บทการนำเสนอ
        9. บทการนำเสนอผลิตภัณฑ์ อธิบายผลประโยชน์ เงื่อนไข และข้อยกเว้น
        10. บทการนำแจ้งค่าเบี้ยประกันให้ลูกค้ารับทราบ
        11. บทการนำเสนออธิบายเกี่ยวกับมูลค่ากรมธรรม์ การเวนคืนได้ถูกต้อง
        12. บทการนำเสนออธิบายถึงการนำเบี้ยประกันไปลดหย่อนภาษี
        13. ประโยคและวิธีการตอบคำถามและข้อโต้แย้งชัดเจน ตรงประเด็น และโน้มน้าวให้ตกลงซื้อ
        14. อธิบายและชี้ช่องการการสมัคร พร้อมวิธีการชำระเบี้ยประกันชีวิต
        15. ใช้ประโยคปิดการขายภายหลังจากนำเสนอ และ/หรือการตอบข้อโต้แย้ง ไม่น้อยกว่า 3 ครั้ง
        16. ประโยคสคริปต์การขายโดยรวม
        17. น้ำเสียงการสนทนาโดยรวมสร้างความประทับใจให้ลูกค้า (วิเคราะห์จากบริบทการพิมพ์)
        18. ระหว่างการสนทนาตั้งแต่เริ่มจนวางสาย พนักงานสามารถควบคุมสถานการณ์ อารมณ์ และน้ำเสียง 
        19. มีทักษะและไหวพริบการรับฟัง ตอบคำถาม และสร้างการสนทนาโต้ตอบกับลูกค้า 
        20. พนักงานสามารถฝึกฝนและพัฒนา สคริปท์การขายและทักษะการโน้มน้าวได้

        วิเคราะห์และสรุป:
        - จุดแข็ง (Strengths) ของพนักงานคนนี้
        - จุดอ่อน (Weaknesses) ที่พนักงานพลาดไป
        - จุดที่ต้องปรับปรุงพัฒนา (Improvements) เพื่อให้ผ่านเกณฑ์หรือยอดเยี่ยมขึ้น

        จงตอบกลับข้อมูลในรูปแบบ JSON เท่านั้น ห้ามมีข้อความอื่นปน (ไม่ต้องมีเครื่องหมาย ```json) ดังโครงสร้างนี้:
        {{
            "scores": [คะแนนข้อ4, คะแนนข้อ5, ..., คะแนนข้อ20], 
            "strengths": "คำอธิบายจุดแข็ง...",
            "weaknesses": "คำอธิบายจุดอ่อน...",
            "improvements": "คำอธิบายจุดที่ต้องพัฒนา..."
        }}
        """
        
        response = model.generate_content(eval_prompt)
        result_text = response.text.strip()
        
        if result_text.startswith("```json"):
            result_text = result_text[7:-3].strip()
        elif result_text.startswith("```"):
            result_text = result_text[3:-3].strip()
            
        eval_data = json.loads(result_text)
        
        scores_array = eval_data.get("scores", [0]*17)
        total_score = sum(scores_array)
        is_passed = total_score >= 50
        
        eval_data["total"] = total_score
        eval_data["passed"] = is_passed
        
        return jsonify(eval_data)
        
    except Exception as e:
        print(f"Eval Error: {e}")
        return jsonify({
            "scores": [0]*17,
            "total": 0,
            "passed": False,
            "strengths": "ไม่สามารถวิเคราะห์ข้อมูลได้",
            "weaknesses": "เกิดข้อผิดพลาดในการประมวลผล",
            "improvements": "กรุณาลองใหม่อีกครั้ง"
        }), 500

if __name__ == "__main__":
    app.run(debug=True)
