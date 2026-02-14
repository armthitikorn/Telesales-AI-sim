import os
import requests
import re
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai

app = Flask(__name__)

# --- [ส่วนที่ 1: ตั้งค่า AI] ---
GENAI_API_KEY = os.environ.get("GENAI_API_KEY")
TTS_API_KEY = os.environ.get("TTS_API_KEY")
genai.configure(api_key=GENAI_API_KEY)
model = genai.GenerativeModel(model_name="gemini-2.5-flash")

# --- [ส่วนที่ 2: ตั้งค่าเสียง - ใช้ Neural2] ---
CUSTOMERS = {
    "1": {"name": "น้องฟ้า", "desc": "SuperSmartSave 20/9", "prompt": "คุณคือ 'ฟ้า' อายุ 25 ปี ลงท้าย 'ค่ะ' คุยเรื่องออมเงิน", "voice": {"name": "th-TH-Neural2-A", "pitch": 0.0, "rate": 1.0}},
    "2": {"name": "คุณวิรัช", "desc": "Double Sure Health", "prompt": "คุณคือ 'วิรัช' อายุ 45 ปี ลงท้าย 'ครับ' คุยเรื่องสุขภาพ", "voice": {"name": "th-TH-Neural2-B", "pitch": -1.0, "rate": 1.0}},
    "3": {"name": "คุณป้ามาลี", "desc": "Wealth 888", "prompt": "คุณคือ 'ป้ามาลี' ลงท้าย 'ค่ะ/จ๊ะ' คุยเรื่องมรดก", "voice": {"name": "th-TH-Neural2-A", "pitch": -2.0, "rate": 0.9}},
    "4": {"name": "แม่แอน", "desc": "ยาก: ปฏิเสธหนักมาก", "prompt": "คุณคือ 'แอน' ปฏิเสธเก่งมากและยุ่งตลอดเวลา", "voice": {"name": "th-TH-Neural2-A", "pitch": 0.0, "rate": 1.0}},
    "5": {"name": "คุณอัครเดช", "desc": "ยากมาก: นักธุรกิจ", "prompt": "คุณคือ 'อัครเดช' นักธุรกิจมาดเนี้ยบ เน้นความคุ้มค่า", "voice": {"name": "th-TH-Neural2-B", "pitch": -1.5, "rate": 1.05}}
}

def get_audio_base64(text, voice_config):
    if not TTS_API_KEY: return None
    # ลบเครื่องหมายพิเศษเพื่อให้ AI อ่านต่อเนื่อง
    clean_text = re.sub(r'[*#_มหาศาล]', '', text)
    clean_text = re.sub(r'\(.*?\)', '', clean_text).strip()
    
    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={TTS_API_KEY}"
    payload = {
        "input": {"text": clean_text},
        "voice": {"languageCode": "th-TH", "name": voice_config["name"]},
        "audioConfig": {"audioEncoding": "MP3", "pitch": voice_config["pitch"], "speakingRate": voice_config["rate"]}
    }
    
    try:
        res = requests.post(url, json=payload, timeout=10)
        res_data = res.json()
        if "error" in res_data:
            print(f"TTS API Error: {res_data['error']['message']}")
            return None
        return res_data.get("audioContent")
    except Exception as e:
        print(f"TTS Request Failed: {e}")
        return None

# --- [ส่วนที่ 3: UI] ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telesales Simulator AI</title>
    <style>
        body { font-family: sans-serif; background: #f0f2f5; margin: 0; padding: 20px; }
        .container { max-width: 600px; margin: auto; }
        .card { background: white; padding: 15px; margin: 10px 0; border-radius: 10px; cursor: pointer; border-left: 5px solid #1e3a8a; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        #chat { height: 400px; overflow-y: auto; background: #fff; padding: 15px; border-radius: 10px; margin-bottom: 20px; border: 1px solid #ddd; display: flex; flex-direction: column; }
        .msg { margin-bottom: 10px; padding: 10px; border-radius: 10px; max-width: 80%; line-height: 1.5; }
        .staff { background: #1e3a8a; color: white; align-self: flex-end; }
        .customer { background: #e4e6eb; color: black; align-self: flex-start; }
        .controls { text-align: center; }
        .btn-mic { width: 80px; height: 80px; border-radius: 50%; background: #be123c; color: white; border: none; font-size: 35px; cursor: pointer; transition: 0.3s; }
        .btn-mic:active { transform: scale(0.9); }
    </style>
</head>
<body>
    <div id="lobby" class="container">
        <h2>🏆 Telesales Mastery AI</h2>
        <input type="text" id="staff-name" placeholder="ใส่ชื่อพนักงานของคุณ" style="width: 100%; padding: 12px; margin-bottom: 15px; border-radius: 8px; border: 1px solid #ddd; box-sizing: border-box;">
        <div id="customer-list"></div>
    </div>

    <div id="app" class="container" style="display:none;">
        <h3 id="active-name"></h3>
        <div id="chat"></div>
        <div class="controls">
            <button class="btn-mic" onclick="listen()">🎤</button>
            <p id="status" style="font-weight:bold; margin-top: 10px;">แตะไมค์เพื่อเริ่มพูด</p>
        </div>
    </div>

    <script>
        var history_log = [];
        var activeLvl = "";
        var isThinking = false;
        var player = new Audio();
        var recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
        recognition.lang = 'th-TH';

        var custs = {{ CUSTOMERS | tojson | safe }};
        var list = document.getElementById('customer-list');
        for (var k in custs) {
            let lvl = k;
            let d = document.createElement('div');
            d.className = 'card';
            d.innerHTML = '<b>'+custs[lvl].name+'</b><br><small>'+custs[lvl].desc+'</small>';
            d.onclick = () => {
                if(!document.getElementById('staff-name').value) return alert("กรุณาระบุชื่อพนักงานก่อนเริ่มครับ");
                activeLvl = lvl;
                document.getElementById('lobby').style.display='none';
                document.getElementById('app').style.display='block';
                document.getElementById('active-name').innerText = "กำลังคุยกับ: " + custs[lvl].name;
            };
            list.appendChild(d);
        }

        recognition.onresult = (e) => {
            let transcript = e.results[0][0].transcript;
            if (transcript && !isThinking) talk(transcript);
        };

        async function talk(t) {
            isThinking = true;
            document.getElementById('status').innerText = "⌛ ลูกค้ากำลังคิด...";
            let chatBox = document.getElementById('chat');
            chatBox.innerHTML += '<div class="msg staff"><b>คุณ:</b> '+t+'</div>';
            chatBox.scrollTop = chatBox.scrollHeight;
            
            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: t, lvl: activeLvl, history: history_log})
                });
                const data = await res.json();
                
                chatBox.innerHTML += '<div class="msg customer"><b>'+custs[activeLvl].name+':</b> '+data.reply+'</div>';
                chatBox.scrollTop = chatBox.scrollHeight;
                
                // อัปเดตประวัติการสนทนา
                history_log.push("พนักงาน: " + t);
                history_log.push(custs[activeLvl].name + ": " + data.reply);

                if (data.audio) {
                    player.src = "data:audio/mp3;base64," + data.audio;
                    player.play().catch(e => console.log("Audio Play Blocked"));
                    player.onended = () => { 
                        isThinking = false;
                        document.getElementById('status').innerText = "✅ พร้อมคุยต่อ";
                    };
                } else {
                    isThinking = false;
                    document.getElementById('status').innerText = "❌ เสียงไม่ทำงาน (ตรวจสอบ API Key)";
                }
            } catch (e) {
                isThinking = false;
                document.getElementById('status').innerText = "❌ เกิดข้อผิดพลาดในการเชื่อมต่อ";
            }
        }

        function listen() {
            if(isThinking) return;
            player.pause();
            try { recognition.start(); } catch(e) {}
            document.getElementById('status').innerText = "🔴 กำลังฟัง...";
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
    lvl = data.get('lvl')
    user_msg = data.get('message')
    history = data.get('history', [])
    
    cust = CUSTOMERS[lvl]
    # รวมประวัติเพื่อส่งให้ Gemini
    context = "\\n".join(history)
    full_prompt = f"System: {cust['prompt']}\\nHistory:\\n{context}\\nUser: {user_msg}"
    
    try:
        response = model.generate_content(full_prompt)
        reply_text = response.text
        audio_data = get_audio_base64(reply_text, cust['voice'])
        return jsonify({"reply": reply_text, "audio": audio_data})
    except Exception as e:
        return jsonify({"reply": "ขออภัย ระบบขัดข้องชั่วคราว", "audio": None})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
