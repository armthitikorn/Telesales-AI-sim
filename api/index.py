import os
import requests
import re
import json
import csv
import traceback
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai

app = Flask(__name__)

# --- [ส่วนที่ 1: ตั้งค่า API & Logging] ---
GENAI_API_KEY = os.environ.get("GENAI_API_KEY")
TTS_API_KEY = os.environ.get("TTS_API_KEY")
LOG_FILE = "/tmp/sales_performance.csv" 

genai.configure(api_key=GENAI_API_KEY)
model = genai.GenerativeModel(model_name="gemini-2.5-flash")

def save_to_csv(staff_name, customer_name, scores, total, passed):
    try:
        file_exists = os.path.isfile(LOG_FILE)
        with open(LOG_FILE, mode='a', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            if not file_exists:
                header = ["Timestamp", "Staff Name", "Customer Name", "Total Score", "Status"] + [f"S_{i}" for i in range(1, 18)]
                writer.writerow(header)
            writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M"), staff_name, customer_name, total, "PASS" if passed else "FAIL"] + scores)
    except Exception as e:
        print("ไม่สามารถบันทึกไฟล์ CSV ได้:", e)

# --- [ส่วนที่ 2: ลอจิกการโต้ตอบ & Persona ที่เป็นธรรมชาติมากขึ้น] ---
COLD_CALL_RULES = """
[กฎเหล็กและลักษณะความเป็นมนุษย์]:
1. คุณคือ "ลูกค้า" มนุษย์จริงๆ ที่กำลังใช้ชีวิตอยู่ ไม่ใช่ AI ตอบคำถาม ห้ามไกด์สคริปต์หรือช่วยพนักงานเด็ดขาด
2. ตอบสั้น กระชับ เป็นธรรมชาติ (1-3 ประโยค) ตามสไตล์คนที่กำลังคุยโทรศัพท์
3. ความเป็นมนุษย์: สามารถอุทาน ใช้คำเติมเต็มช่องว่าง เช่น "เอ่อ...", "อืม...", "อ๋อครับ", "แบบว่า..." หรือแสดงอาการลังเลใจ ถอนหายใจ ถ้ายุ่งอยู่ก็บอกว่ายุ่ง
4. สภาพอารมณ์: จะเปลี่ยนไปตามวิธีพูดของพนักงาน ถ้าพนักงานพูดจาไม่ชัดเจน ตะกุกตะกัก หรือพูดเร็วเกินไป คุณจะเริ่มรำคาญหรือถามซ้ำ แต่ถ้าพนักงานหาจุดสนใจ (Hook) หรือ Fact Finding เจอสิ่งที่ตรงกับปัญหาชีวิตคุณ คุณจะเริ่มเปิดใจฟังมากขึ้น
5. การระบุตัวเลข: ให้พิมพ์เป็นคำอ่านภาษาไทยเสมอ ห้ามใช้ตัวเลขอารบิกเด็ดขาด (เช่น "สองหมื่นห้าพันบาท" แทน "25,000 บาท", "สี่สิบห้า" แทน "45") เพื่อให้ระบบ Text-to-Speech ออกเสียงได้ลื่นไหลที่สุด
6. การเช็กข้อมูล: หากพนักงานแนะนำตัวไม่ครบ หรือพูดรวบรัด ให้ถามแทรกตามสัญชาตญาณ เช่น "เอ่อ เดี๋ยวคุยกับใครอยู่นะคะ?", "โทรมาจากที่ไหนนะ?"
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
    <title>Sales Mastery Simulator</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root { --blue: #1e3a8a; --red: #be123c; --gray: #94a3b8; --green: #15803d; --gold: #b45309; }
        body { font-family: sans-serif; background: #f1f5f9; margin:0; -webkit-tap-highlight-color: transparent; }
        
        .modal-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); display: flex; align-items: center; justify-content: center; z-index: 2000; }
        .modal-card { background: white; padding: 25px; border-radius: 15px; max-width: 500px; width: 90%; text-align: center; }
        
        #lobby { padding: 20px; text-align: center; max-width: 600px; margin: auto; }
        .card { background: white; padding: 15px; margin: 10px 0; border-radius: 12px; border-left: 8px solid var(--blue); text-align: left; cursor: pointer; }
        #main-app { display: none; flex-direction: column; height: 100vh; background: white; }
        .header { background: var(--blue); color: white; padding: 15px; text-align: center; position: relative; }
        #chat-box { flex: 1; overflow-y: auto; padding: 15px; display: flex; flex-direction: column; gap: 10px; background: #f8fafc; }
        .msg { padding: 10px 15px; border-radius: 15px; max-width: 85%; line-height: 1.4; position: relative; }
        .staff { align-self: flex-end; background: var(--blue); color: white; }
        .customer { align-self: flex-start; background: #e2e8f0; color: #1e293b; }
        .controls { padding: 15px; background: white; border-top: 1px solid #ddd; text-align: center; }
        .btn-mic { width: 70px; height: 70px; border-radius: 50%; border: none; background: var(--red); color: white; font-size: 30px; cursor: pointer; }
        
        .btn-play-audio { display: block; margin-top: 8px; padding: 5px 12px; background: #cbd5e1; border: none; border-radius: 10px; font-size: 12px; cursor: pointer; }
        
        #analytics-section { display:none; padding: 20px; background: white; border-radius: 15px; margin: 20px auto; max-width: 800px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
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
        <button onclick="toggleAnalytics()" style="width:100%; margin-top:10px; padding:10px; border-radius:8px; border:none; background:var(--gray); color:white;">ปิด</button>
    </div>

    <div id="main-app">
        <div class="header">
            <h2 id="active-name" style="margin:0;">ลูกค้า</h2>
            <button onclick="location.reload()" style="position: absolute; right: 15px; top: 15px; background: rgba(255,255,255,0.2); border: 1px solid white; color: white; padding: 5px 10px; border-radius: 5px; cursor: pointer; font-size: 12px;">🏠 กลับหน้าหลัก</button>
        </div>
        <div id="chat-box"></div>
        <div class="controls">
            <button id="mic-btn" class="btn-mic" onclick="toggleListen()">🎤</button>
            <p id="status" style="margin: 8px 0; font-size: 13px; color: #64748b;">แตะไมค์เพื่อพูด</p>
            <div style="display:flex; gap:5px;">
                <input type="text" id="text-input" placeholder="พิมพ์โต้ตอบ..." style="flex:1; padding:10px; border-radius:8px; border:1px solid #ddd;" onkeypress="if(event.key==='Enter') sendMsg()">
                <button onclick="sendMsg()" style="padding:10px 20px; background:var(--blue); color:white; border:none; border-radius:8px;">ส่ง</button>
            </div>
            <button id="eval-btn" style="display:none; width:100%; padding:12px; border-radius:20px; border:1px solid var(--blue); color:var(--blue); background:none; margin-top:10px; font-weight:bold;" onclick="showEvaluation()">🏁 ประเมินผล</button>
        </div>
    </div>

    <div id="eval-modal" style="display:none;" class="modal-overlay">
        <div style="background:white; padding:20px; border-radius:15px; width:90%; max-width:600px; max-height:90vh; overflow-y:auto;">
             <div id="eval-printable-area">
                <h2 style="text-align:center; color:var(--blue);">📊 รายงานผลการทดสอบ</h2>
                <div id="score-banner" style="text-align:center; padding:15px; border-radius:10px; color:white; font-size:20px; font-weight:bold; margin-bottom:15px;"></div>
                <div id="fb-content"></div>
                <div id="eval-details" style="font-size:12px;"></div>
             </div>
             <button onclick="location.reload()" style="width:100%; padding:15px; background:var(--blue); color:white; border:none; border-radius:8px; margin-top:15px;">เสร็จสิ้น (กลับหน้าหลัก)</button>
        </div>
    </div>

    <audio id="audio-player" playsinline style="display:none;"></audio>

    <script>
        var history_log = [];
        var activeLvl = "";
        var isThinking = false;
        var customers = {{ CUSTOMERS | tojson | safe }};
        var audioPlayer = document.getElementById('audio-player');
        
        function unlockAudio() {
            audioPlayer.src = "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=";
            audioPlayer.play().then(() => {
                audioPlayer.pause();
            }).catch(e => console.log("Unlock failed", e));
        }

        function acceptConsent() {
            unlockAudio(); 
            document.getElementById('consent-modal').style.display = 'none';
            document.getElementById('lobby').style.display = 'block';
        }

        // --- นี่คือฟังก์ชันที่หายไป ทำให้คลิกเลือกลูกค้าไม่ได้ครับ นำกลับมาใส่ให้แล้วครับ! ---
        function startApp(lvl) {
            if(!document.getElementById('staff-name').value) { alert("ระบุชื่อก่อนครับ"); return; }
            activeLvl = lvl;
            document.getElementById('lobby').style.display = 'none';
            document.getElementById('main-app').style.display = 'flex';
            document.getElementById('active-name').innerText = customers[lvl].name;
        }

        var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        var recognition = SpeechRecognition ? new SpeechRecognition() : null;
        
        var speechTimeout; 
        // ลบ var currentSpeech = ""; ออกไปได้เลย ไม่จำเป็นต้องใช้แล้ว

        if(recognition) {
            recognition.lang = 'th-TH';
            recognition.continuous = true; 
            recognition.interimResults = true; 

            recognition.onresult = (e) => {
                if(isThinking) return;

                let interimTranscript = '';
                let finalTranscript = '';

                // แก้ไข: เปลี่ยนการวนลูปจาก e.resultIndex เป็น 0 เสมอ
                // เพื่อประกอบประโยคใหม่ทั้งหมดจากสิ่งที่เบราว์เซอร์จำได้ จะได้ไม่เกิดการเบิ้ลคำ
                for (let i = 0; i < e.results.length; ++i) {
                    if (e.results[i].isFinal) {
                        finalTranscript += e.results[i][0].transcript;
                    } else {
                        interimTranscript += e.results[i][0].transcript;
                    }
                }

                let inputField = document.getElementById('text-input');
                // อัปเดตช่องข้อความโดยใช้ค่าที่อ่านได้โดยตรง
                inputField.value = finalTranscript + interimTranscript;

                clearTimeout(speechTimeout);

                speechTimeout = setTimeout(() => {
                    let finalMsg = inputField.value.trim();
                    if(finalMsg !== "") {
                        sendToAI(finalMsg);
                        inputField.value = "";
                        recognition.stop(); 
                    }
                }, 2500); 
            };

            recognition.onend = () => {
                if(!isThinking) document.getElementById('status').innerText = "✅ พร้อมคุยต่อ (แตะไมค์อีกครั้งเพื่อพูด)";
            };
        }

        function toggleListen() {
            unlockAudio();
            document.getElementById('text-input').value = "";
            clearTimeout(speechTimeout);
            try { 
                recognition.start(); 
                document.getElementById('status').innerText = "🔊 กำลังฟัง... (หยุดพูด 2.5 วิ ระบบจะส่งข้อความอัตโนมัติ)"; 
            } catch(e){}
        }

        function sendMsg() {
            unlockAudio(); 
            clearTimeout(speechTimeout); 
            if(recognition) recognition.stop(); 
            
            let input = document.getElementById('text-input');
            if(input.value && !isThinking) sendToAI(input.value);
            input.value = "";
        }


        function toggleListen() {
            unlockAudio();
            currentSpeech = ""; 
            document.getElementById('text-input').value = "";
            clearTimeout(speechTimeout);
            try { 
                recognition.start(); 
                document.getElementById('status').innerText = "🔊 กำลังฟัง... (หยุดพูด 2.5 วิ ระบบจะส่งข้อความอัตโนมัติ)"; 
            } catch(e){}
        }

        function sendMsg() {
            unlockAudio(); 
            clearTimeout(speechTimeout); 
            if(recognition) recognition.stop(); 
            
            let input = document.getElementById('text-input');
            if(input.value && !isThinking) sendToAI(input.value);
            input.value = "";
            currentSpeech = ""; 
        }

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
                    audioPlayer.play().catch(err => {
                        let playBtn = document.createElement('button');
                        playBtn.className = "btn-play-audio";
                        playBtn.innerHTML = "🔊 กดเพื่อฟังเสียง";
                        playBtn.onclick = () => { audioPlayer.play(); playBtn.remove(); };
                        botDiv.appendChild(playBtn);
                    });
                }
            } catch(e) {
                alert("เกิดปัญหาการเชื่อมต่อ: " + e.message);
            }
            
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
            let btn = document.getElementById('eval-btn');
            let status = document.getElementById('status');
            let originalText = btn.innerText;
            
            btn.disabled = true;
            btn.innerText = "⏳ กำลังประมวลผล... (อาจใช้เวลาสักครู่)";
            status.innerText = "ระบบกำลังให้ AI วิเคราะห์บทสนทนา...";
            
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
                banner.innerText = `คะแนนรวม: ${data.total}/85 (${data.passed ? "ผ่านเกณฑ์ ✅" : "ไม่ผ่านเกณฑ์ ❌"})`;
                banner.style.background = data.passed ? "var(--green)" : "var(--red)";
                
                document.getElementById('fb-content').innerHTML = `
                    <div style="background:#f1f5f9; padding:15px; border-radius:8px; margin-bottom:15px; line-height:1.6; font-size:14px; text-align:left;">
                        <b style="color:var(--green);">🟢 จุดแข็ง:</b> ${data.strengths || "-"}<br><br>
                        <b style="color:var(--red);">🔴 จุดอ่อน:</b> ${data.weaknesses || "-"}<br><br>
                        <b style="color:var(--blue);">💡 ข้อเสนอแนะ:</b> ${data.improvements || "-"}
                    </div>`;
                
                let detailsHtml = "<b style='color:var(--blue); font-size:14px;'>ตารางคะแนน QC Matrix (17 ข้อ):</b><div style='display:grid; grid-template-columns: 1fr 1fr; gap:8px; margin-top:10px; text-align:left;'>";
                
                const qc_titles = [
                    "1. แนะนำตัว/บริษัท", "2. แจ้งวัตถุประสงค์", "3. สร้าง Hook", "4. Fact Finding", "5. นำเสนอตรงความต้องการ",
                    "6. อธิบายผลประโยชน์", "7. แจ้งข้อยกเว้น", "8. แจ้งเบี้ย/งวด", "9. ขจัดข้อโต้แย้ง", "10. ไม่บังคับลูกค้า",
                    "11. สิทธิ Free look", "12. แถลงสุขภาพ", "13. ช่องทางชำระเงิน", "14. สรุปข้อมูล", "15. ปิดการขาย",
                    "16. น้ำเสียงสุภาพ", "17. กล่าวลา/ขอบคุณ"
                ];
                
                let scoresArray = data.scores || [];
                
                for(let i=0; i<17; i++) {
                    let score = scoresArray[i] !== undefined ? scoresArray[i] : 0;
                    detailsHtml += `<div style="background:#f8fafc; padding:8px; border-radius:5px; border:1px solid #e2e8f0; font-size:12px;">
                        ${qc_titles[i]}<br><b style="color: ${score >= 3 ? 'var(--green)' : 'var(--red)'}; font-size:14px;">${score}/5</b>
                    </div>`;
                }
                detailsHtml += "</div>";
                
                document.getElementById('eval-details').innerHTML = detailsHtml;
                document.getElementById('eval-modal').style.display = 'flex';
                
            } catch (e) {
                console.error("Evaluation Error:", e);
                alert("การประเมินผลขัดข้อง กรุณาลองใหม่อีกครั้งครับ");
            } finally {
                btn.disabled = false;
                btn.innerText = originalText;
                status.innerText = "✅ พร้อมคุยต่อ";
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
        context = "\n".join(history)
        full_prompt = f"{cust['prompt']}\nประวัติคุย: {context}\nพนักงาน: {user_msg}\nลูกค้าตอบกลับสั้นๆ:"
        response = model.generate_content(full_prompt)
        reply_text = response.text.strip()
        audio_data = get_audio_base64(reply_text, cust['voice'])
        return jsonify({"reply": reply_text, "audio": audio_data})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"reply": f"ระบบ AI ขัดข้อง: {str(e)}", "error": True, "audio": None})

@app.route('/api/evaluate', methods=['POST'])
def evaluate():
    try:
        data = request.json
        history = data.get('history', '')
        staff_name = data.get('staff_name', 'Unknown')
        customer_name = data.get('customer_name', 'Unknown')
        
        eval_prompt = f"""ในฐานะ QA ประเมินการขายประกันผ่านโทรศัพท์
        จงให้คะแนนประวัติการสนทนานี้ตามเกณฑ์ 17 ข้อ (ให้คะแนนข้อละ 0 ถึง 5 คะแนน เป็นตัวเลขจำนวนเต็มเท่านั้น)

        หัวข้อทั้ง 17 ข้อ:
        1. แนะนำตัว/บริษัท 2. แจ้งวัตถุประสงค์ 3. สร้าง Hook 4. Fact Finding 5. นำเสนอตรงความต้องการ
        6. อธิบายผลประโยชน์ 7. แจ้งข้อยกเว้น 8. แจ้งเบี้ย/งวด 9. ขจัดข้อโต้แย้ง 10. ไม่บังคับลูกค้า
        11. สิทธิ Free look 12. แถลงสุขภาพ 13. ช่องทางชำระเงิน 14. สรุปข้อมูล 15. ปิดการขาย
        16. น้ำเสียงสุภาพ 17. กล่าวลา/ขอบคุณ
        
        ประวัติการสนทนา: 
        {history}
        
        คำสั่งเด็ดขาด: ตอบกลับเป็น JSON อย่างเดียวเท่านั้น ห้ามมีข้อความอธิบายใดๆ นอกเหนือจากใน JSON 
        ตัวอย่างโครงสร้างที่ถูกต้อง:
        {{
            "scores": [5, 4, 0, 3, 5, 2, 0, 0, 4, 5, 0, 0, 0, 0, 0, 5, 5],
            "strengths": "อธิบายจุดแข็งที่พนักงานทำได้ดีในบทสนทนานี้ พร้อมเหตุผลประกอบอย่างละเอียด (3-4 ประโยค)",
            "weaknesses": "อธิบายจุดอ่อนหรือสิ่งที่พนักงานพลาดไป พร้อมเหตุผลประกอบอย่างละเอียดว่าควรแก้ไขอย่างไร (3-4 ประโยค)",
            "improvements": "ข้อเสนอแนะเพิ่มเติมเพื่อการพัฒนาและปิดการขาย..."
        }}"""
        
        response = model.generate_content(eval_prompt)
        res_text = response.text.strip()
        
        if "```json" in res_text:
            res_text = res_text.split("```json")[1].split("```")[0]
        elif "```" in res_text:
            res_text = res_text.split("```")[1].split("```")[0]
            
        match = re.search(r'\{.*\}', res_text, re.DOTALL)
        if match:
            res_text = match.group(0)
            
        eval_data = json.loads(res_text)
        
        raw_scores = eval_data.get("scores", [0]*17)
        scores = []
        for s in raw_scores:
            try:
                scores.append(int(s))
            except:
                scores.append(0)
                
        while len(scores) < 17:
            scores.append(0)
        scores = scores[:17]
        
        total = sum(scores)
        passed = total >= 50
        
        save_to_csv(staff_name, customer_name, [str(s) for s in scores], total, passed)
        
        eval_data["scores"] = scores
        eval_data["total"] = total
        eval_data["passed"] = passed
        return jsonify(eval_data)
        
    except Exception as e:
        traceback.print_exc()
        raw_ai_text = response.text if 'response' in locals() else 'ไม่มีข้อมูล'
        return jsonify({
            "scores": [0]*17,
            "total": 0,
            "passed": False,
            "strengths": "เกิดข้อผิดพลาดในการประมวลผล JSON",
            "weaknesses": "AI ส่งรูปแบบข้อมูลกลับมาผิดเพี้ยน",
            "improvements": f"รายละเอียด Error: {str(e)} | ข้อความจาก AI: {raw_ai_text}"
        })

@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    labels = []
    values = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, mode='r', encoding='utf-8-sig') as f:
                rows = list(csv.DictReader(f))
                for row in rows[-10:]:
                    labels.append(f"{row['Staff Name']} ({row['Timestamp']})")
                    values.append(int(row['Total Score']))
        except:
            pass
    return jsonify({"labels": labels, "values": values})

if __name__ == "__main__":
    app.run(debug=True)
