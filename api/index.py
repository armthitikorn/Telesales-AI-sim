import os
import re
import requests
from flask import Flask, request, jsonify
import google.generativeai as genai

# ==================================================
# ✅ FLASK ENTRYPOINT (สำคัญมาก)
# ==================================================
app = Flask(__name__)

# ==================================================
# ✅ ENV CONFIG
# ==================================================
GENAI_API_KEY = os.environ.get("GENAI_API_KEY")
TTS_API_KEY = os.environ.get("TTS_API_KEY")

if not GENAI_API_KEY:
    raise RuntimeError("Missing GENAI_API_KEY")

if not TTS_API_KEY:
    raise RuntimeError("Missing TTS_API_KEY")

genai.configure(api_key=GENAI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# ==================================================
# ✅ CUSTOMER CONFIG
# ==================================================
COLD_CALL_RULES = """
คุณคือลูกค้าที่เป็นมนุษย์จริง
- ห้ามถามชื่อพนักงานซ้ำ
- ผู้หญิงใช้ ฉัน / เรา
- ผู้ชายใช้ ผม
- ถ้าพนักงานพูดยาวหรือสคริปต์ → แสดงอาการเบื่อ
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

# ==================================================
# ✅ GOOGLE TTS (กันเสียงหาย)
# ==================================================
def get_audio_base64(text: str, voice: dict):
    # ล้างวงเล็บ (กันเสียงเงียบ)
    clean_text = re.sub(r'[\(\[\（].*?[\)\]\）]', '', text, flags=re.DOTALL)
    clean_text = re.sub(
        r'^(System|User|Assistant|ลูกค้า|พนักงาน)\s*[:：]\s*',
        '',
        clean_text
    ).strip()

    # ✅ fallback ถ้าข้อความว่าง
    if not clean_text:
        clean_text = text.strip()

    if not clean_text:
        return None

    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={TTS_API_KEY}"
    payload = {
        "input": {"text": clean_text},
        "voice": {
            "languageCode": "th-TH",
            "name": voice["name"]
        },
        "audioConfig": {
            "audioEncoding": "MP3",
            "pitch": voice["pitch"],
            "speakingRate": voice["rate"]
        }
    }

    try:
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code != 200:
            print("TTS ERROR:", res.text)
            return None
        return res.json().get("audioContent")
    except Exception as e:
        print("TTS NETWORK ERROR:", e)
        return None

# ==================================================
# ✅ CHAT API
# ==================================================
@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json or {}

    lvl = str(data.get("lvl", "1"))
    user_msg = data.get("message", "")
    history = data.get("history", [])

    customer = CUSTOMERS.get(lvl, CUSTOMERS["1"])

    # ✅ รองรับ history ได้หลายรูปแบบ
    context = "\n".join(
        h if isinstance(h, str) else h.get("text", "")
        for h in history
    )

    full_prompt = f"""
System: {customer['prompt']}
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
        audio = get_audio_base64(reply_text, customer["voice"])

        return jsonify({
            "reply": reply_text,
            "audio": audio,
            "character": customer["name"]
        })

    except Exception as e:
        print("GEMINI ERROR:", e)
        return jsonify({
            "reply": "ขออภัยค่ะ ระบบขัดข้องชั่วคราว",
            "audio": None
        })

# ==================================================
# ❌ ห้ามมี app.run() ใน production
# Platform จะเป็นคนรันให้เอง
# ==================================================
``
