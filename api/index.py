import os
import requests
import re
from flask import Flask, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# =======================
# 1) CONFIG
# =======================
GENAI_API_KEY = os.environ.get("GENAI_API_KEY")
TTS_API_KEY = os.environ.get("TTS_API_KEY")

genai.configure(api_key=GENAI_API_KEY)
model = genai.GenerativeModel(model_name="gemini-2.5-flash")

# =======================
# 2) CUSTOMER CONFIG
# =======================
COLD_CALL_RULES = """
คุณคือลูกค้าที่มีความจำดี:
- ห้ามถามชื่อพนักงานซ้ำ
- ผู้หญิงใช้ ฉัน/เรา
- ผู้ชายใช้ ผม
"""

CUSTOMERS = {
    "1": {
        "name": "น้องฟ้า",
        "prompt": COLD_CALL_RULES + "คุณคือ 'ฟ้า' ผู้หญิง อายุ 25 ปี ลงท้าย 'ค่ะ'",
        "voice": {"name": "th-TH-Neural2-A", "pitch": 0.0, "rate": 1.1}
    },
    "2": {
        "name": "คุณวิรัช",
        "prompt": COLD_CALL_RULES + "คุณคือ 'วิรัช' ผู้ชาย อายุ 45 ปี ลงท้าย 'ครับ'",
        "voice": {"name": "th-TH-Neural2-C", "pitch": 0.0, "rate": 1.0}
    },
    "5": {
        "name": "คุณอัครเดช",
        "prompt": COLD_CALL_RULES + "คุณคือ 'อัครเดช' นักธุรกิจดุ ลงท้าย 'ครับ'",
        "voice": {"name": "th-TH-Neural2-C", "pitch": -2.0, "rate": 1.0}
    }
}

# =======================
# 3) GOOGLE TTS
# =======================
def get_audio_base64(text, voice_config):
    if not TTS_API_KEY:
        print("Missing TTS_API_KEY")
        return None

    # ✅ ล้างวงเล็บให้ถูกต้อง
    clean_text = re.sub(r'[\(\[\（].*?[\)\]\）]', '', text, flags=re.DOTALL)
    clean_text = re.sub(
        r'^(System|User|Assistant|ลูกค้า|พนักงาน)\s*[:：]\s*',
        '',
        clean_text
    ).strip()

    # ✅ fallback กันเสียงเงียบ
    if not clean_text.strip():
        clean_text = text.strip()

    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={TTS_API_KEY}"
    payload = {
        "input": {"text": clean_text},
        "voice": {
            "languageCode": "th-TH",
            "name": voice_config["name"]
        },
        "audioConfig": {
            "audioEncoding": "MP3",
            "pitch": voice_config["pitch"],
            "speakingRate": voice_config["rate"]
        }
    }

    try:
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code != 200:
            print("Google TTS Error:", res.text)
            return None
        return res.json().get("audioContent")
    except Exception as e:
        print("TTS Network Error:", e)
        return None

# =======================
# 4) CHAT API
# =======================
@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json or {}
    lvl = data.get('lvl', '1')
    user_msg = data.get('message', '')
    history = data.get('history', [])

    cust = CUSTOMERS.get(lvl, CUSTOMERS["1"])

    context = "\n".join(
        h if isinstance(h, str) else h.get("text", "")
        for h in history
    )

    full_prompt = f"""
System: {cust['prompt']}
History:
{context}
User: {user_msg}
"""

    try:
        response = model.generate_content(
            full_prompt,
            generation_config={
                "temperature": 0.6,
                "top_p": 0.9
            }
        )

        reply_text = response.text or ""
        audio_data = get_audio_base64(reply_text, cust["voice"])

        return jsonify({
            "reply": reply_text,
            "audio": audio_data
        })

    except Exception as e:
        print("Gemini Error:", e)
        return jsonify({
            "reply": "ขออภัยค่ะ ระบบขัดข้องเล็กน้อย",
            "audio": None
        })

if __name__ == "__main__":
    app.run(debug=True, port=5000)
``
