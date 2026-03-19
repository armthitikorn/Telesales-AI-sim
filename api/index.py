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

# --- [ส่วนที่ 2: ตั้งค่าตัวละคร - แยกเสียงชาย/หญิง ชัดเจน] ---
COLD_CALL_RULES = """
คุณคือลูกค้าที่มีความจำดีเยี่ยม:
1. [การจดจำ]: อ่านประวัติการสนทนาให้ดี ห้ามถามชื่อพนักงานซ้ำถ้าเขาบอกแล้ว
2. [คำแทนตัว]: ผู้หญิงใช้ 'ฉัน/เรา', ผู้ชายใช้ 'ผม'
"""

CUSTOMERS = {
    "1": {
        "name": "น้องฟ้า", 
        "prompt": COLD_CALL_RULES + "คุณคือ 'ฟ้า' (หญิง) อายุ 25 ปี ลงท้าย 'ค่ะ'",
        # เสียงผู้หญิง Neural คุณภาพสูง
        "voice": {"name": "th-TH-Neural2-A", "pitch": 0.0, "rate": 1.1} 
    },
    "2": {
        "name": "คุณวิรัช", 
        "prompt": COLD_CALL_RULES + "คุณคือ 'วิรัช' (ชาย) อายุ 45 ปี ลงท้าย 'ครับ'",
        # เสียงผู้ชาย Neural (ตัวจริง)
        "voice": {"name": "th-TH-Neural2-C", "pitch": 0.0, "rate": 1.0} 
    },
    "5": {
        "name": "คุณอัครเดช", 
        "prompt": COLD_CALL_RULES + "คุณคือ 'อัครเดช' (ชาย) นักธุรกิจดุๆ ลงท้าย 'ครับ'",
        # เสียงผู้ชาย Neural ปรับ Pitch ให้ทุ้มขึ้นเล็กน้อย
        "voice": {"name": "th-TH-Neural2-C", "pitch": -2.0, "rate": 1.0} 
    }
}

def get_audio_base64(text, voice_config):
    if not TTS_API_KEY: 
        print("Error: Missing TTS_API_KEY")
        return None
    
    # --- จุดแก้ไข: ล้างวงเล็บทุกรูปแบบ (ไทย/สากล/เหลี่ยม) และการขึ้นบรรทัดใหม่ ---
    clean_text = re.sub(r'[\(\[（].*?[\)\]）]', '', text, flags=re.DOTALL)
    clean_text = re.sub(r'^.*?:', '', clean_text).strip()
    
    if not clean_text: 
        print("Warning: No text to speak after cleaning")
        return None

    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={TTS_API_KEY}"
    payload = {
        "input": {"text": clean_text},
        "voice": {"languageCode": "th-TH", "name": voice_config["name"]},
        "audioConfig": {
            "audioEncoding": "MP3", 
            "pitch": voice_config["pitch"], 
            "speakingRate": voice_config["rate"]
        }
    }
    
    try:
        res = requests.post(url, json=payload)
        if res.status_code != 200:
            print(f"Google TTS API Error: {res.text}") # แสดง Error จริงจาก Google
            return None
        return res.json().get("audioContent")
    except Exception as e:
        print(f"Network Error: {str(e)}")
        return None

# --- [ส่วนที่ 3: Routes] ---

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    lvl = data.get('lvl', '1')
    user_msg = data.get('message', '')
    history = data.get('history', [])
    
    cust = CUSTOMERS.get(lvl, CUSTOMERS["1"])
    context = "\n".join(history)
    full_prompt = f"System: {cust['prompt']}\nHistory:\n{context}\nUser: {user_msg}"
    
    try:
        response = model.generate_content(full_prompt)
        reply_text = response.text
        # เรียกใช้ฟังก์ชันแปลงเสียง
        audio_data = get_audio_base64(reply_text, cust['voice'])
        return jsonify({"reply": reply_text, "audio": audio_data})
    except Exception as e:
        print(f"Gemini Error: {str(e)}")
        return jsonify({"reply": "ขออภัยจ้า ระบบขัดข้องนิดหน่อย", "audio": None})

# ... (ส่วน HTML_TEMPLATE และ Route อื่นๆ เหมือนต้นฉบับที่คุณอาร์มมี) ...

if __name__ == "__main__":
    app.run(debug=True, port=5000)
    
