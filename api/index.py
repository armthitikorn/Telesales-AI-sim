import os
import requests
import re
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai

app = Flask(__name__)

# --- [ส่วนที่ 1: ตั้งค่า API] ---
GENAI_API_KEY = os.environ.get("GENAI_API_KEY")
TTS_API_KEY = os.environ.get("TTS_API_KEY") # ใช้คีย์จาก Positive ที่อาร์มเพิ่งเปลี่ยนใน Vercel
genai.configure(api_key=GENAI_API_KEY)
model = genai.GenerativeModel(model_name="gemini-2.5-flash")

# --- [ส่วนที่ 2: ลอจิกบทบาทและรายชื่อลูกค้า] ---
COLD_CALL_RULES = """คุณคือลูกค้าที่เข้มงวด: 
1. ผู้หญิงใช้ 'ฉัน/เรา', ผู้ชายใช้ 'ผม' 
2. ห้ามสวมบทเป็นพนักงานเด็ดขาด"""

CUSTOMERS = {
    "1": {"name": "น้องฟ้า", "desc": "ออม 20/9", "prompt": COLD_CALL_RULES + "คุณคือ 'ฟ้า'...", "voice": {"name": "th-TH-Standard-A", "pitch": 0.0, "rate": 1.0}},
    "2": {"name": "คุณวิรัช", "desc": "สุขภาพ", "prompt": COLD_CALL_RULES + "คุณคือ 'วิรัช'...", "voice": {"name": "th-TH-Neural2-C", "pitch": 0.0, "rate": 1.0}}, # ใช้รหัส -C เท่านั้น
    "3": {"name": "คุณป้ามาลี", "desc": "มรดก", "prompt": COLD_CALL_RULES + "คุณคือ 'ป้ามาลี'...", "voice": {"name": "th-TH-Standard-A", "pitch": -1.5, "rate": 0.9}},
    "4": {"name": "แม่แอน", "desc": "ปฏิเสธหนัก", "prompt": COLD_CALL_RULES + "คุณคือ 'แอน'...", "voice": {"name": "th-TH-Standard-A", "pitch": 0.0, "rate": 1.0}},
    "5": {"name": "คุณอัครเดช", "desc": "นักธุรกิจ", "prompt": COLD_CALL_RULES + "คุณคือ 'อัครเดช'...", "voice": {"name": "th-TH-Neural2-C", "pitch": 0.0, "rate": 1.0}} # ใช้รหัส -C เท่านั้น
}

def get_audio_base64(text, voice_config):
    if not TTS_API_KEY: return None
    clean_text = re.sub(r'^.*?:', '', text)
    clean_text = re.sub(r'\(.*?\)', '', clean_text).strip()
    if not clean_text: return None
    
    # บังคับใช้ v1beta1 เพื่อให้เสียงผู้ชาย (-C) ออก
    url = f"https://texttospeech.googleapis.com/v1beta1/text:synthesize?key={TTS_API_KEY}"
    
    payload = {
        "input": {"text": clean_text},
        "voice": {"languageCode": "th-TH", "name": voice_config["name"]},
        "audioConfig": {"audioEncoding": "MP3", "pitch": voice_config["pitch"], "speakingRate": voice_config["rate"]}
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.json().get("audioContent")
    except: return None

# --- [ส่วนที่ 3: HTML_TEMPLATE (ใช้ตัวเดิมของคุณอาร์มได้เลย)] ---
HTML_TEMPLATE = """ (เอาส่วน HTML ของอาร์มมาวางตรงนี้ทั้งหมดครับ) """

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE, CUSTOMERS=CUSTOMERS)

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        lvl, user_msg, history = data.get('lvl'), data.get('message'), data.get('history', [])
        cust = CUSTOMERS[lvl]
        context = "\\n".join(history[-10:])
        full_prompt = f"Role: {cust['prompt']}\\nHistory: {context}\\nSalesman: {user_msg}\\nAnswer as Customer:"
        response = model.generate_content(full_prompt)
        reply_text = response.text
        audio_data = get_audio_base64(reply_text, cust['voice'])
        return jsonify({"reply": reply_text, "audio": audio_data})
    except Exception as e:
        return jsonify({"reply": f"Error: {str(e)}", "audio": None})

@app.route('/api/evaluate', methods=['POST'])
def evaluate():
    # (เอาส่วน Evaluate ของเดิมมาวางตรงนี้ครับ)
    pass

if __name__ == "__main__":
    app.run(debug=True)
