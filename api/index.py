import os
import requests
import re
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai

app = Flask(__name__)

# --- [ส่วนที่ 1: ตั้งค่า AI - บังคับใช้ Gemini 2.5 Flash] ---
GENAI_API_KEY = os.environ.get("GENAI_API_KEY")
TTS_API_KEY = os.environ.get("TTS_API_KEY")
genai.configure(api_key=GENAI_API_KEY)
model = genai.GenerativeModel(model_name="gemini-2.5-flash")

# --- [ส่วนที่ 2: ลอจิก Cold Call และ ความจำ] ---
COLD_CALL_RULES = """
คุณคือลูกค้าที่มีความจำดีเยี่ยมและเข้มงวด:
1. [การจดจำ]: คุณต้องอ่านประวัติการสนทนาทั้งหมดอย่างละเอียด หากพนักงานแจ้งชื่อ, เลขใบอนุญาต หรือขออัดเสียงไปแล้ว "ห้ามถามซ้ำ" และ "ห้ามทำเป็นลืม"
2. [คำแทนตัว]: ผู้หญิงใช้ 'ฉัน/เรา', ผู้ชายใช้ 'ผม' (ห้ามเรียกชื่อตัวเอง และห้ามมีหัวข้อชื่อนำหน้าข้อความ)
3. [ลำดับสาย]: เริ่มจากระแวง -> ปฏิเสธ 4-5 รอบ -> ยอมฟังเมื่อพูดถูกต้องตามกฎ คปภ.
"""

CUSTOMERS = {
    "1": {"name": "น้องฟ้า", "desc": "SuperSmartSave 20/9", "prompt": COLD_CALL_RULES + "คุณคือ 'ฟ้า' อายุ 25 ปี ลงท้าย 'ค่ะ' ถามเรื่องออม 9 ปี คุ้มครอง 20 ปี", "voice": {"name": "th-TH-Standard-A", "pitch": 2.0, "rate": 1.0}},
    "2": {"name": "คุณวิรัช", "desc": "Double Sure Health", "prompt": COLD_CALL_RULES + "คุณคือ 'วิรัช' อายุ 45 ปี ลงท้าย 'ครับ' ถามเรื่องสุขภาพเหมาจ่าย", "voice": {"name": "th-TH-Standard-A", "pitch": -4.0, "rate": 1.0}},
    "3": {"name": "คุณป้ามาลี", "desc": "Wealth 888", "prompt": COLD_CALL_RULES + "คุณคือ 'ป้ามาลี' ลงท้าย 'ค่ะ/จ๊ะ' ถามเรื่องมรดกให้หลาน", "voice": {"name": "th-TH-Standard-A", "pitch": -1.5, "rate": 0.9}},
    "4": {"name": "แม่แอน", "desc": "ยาก: ปฏิเสธหนักมาก", "prompt": COLD_CALL_RULES + "คุณคือ 'แอน' ปฏิเสธหนักและห่วงเรื่องค่าใช้จ่ายลูก ลงท้าย 'ค่ะ'", "voice": {"name": "th-TH-Standard-A", "pitch": 0.5, "rate": 1.0}},
    "5": {"name": "คุณอัครเดช", "desc": "ยากมาก: นักธุรกิจ (ต้องปิดการขายถึงได้ใบเซอร์)", "prompt": COLD_CALL_RULES + "คุณคือ 'อัครเดช' เวลาน้อยและเน้นความคุ้มค่าสูงสุด ลงท้าย 'ครับ'", "voice": {"name": "th-TH-Standard-A", "pitch": -5.0, "rate": 1.0}}
}

def get_audio_base64(text, voice_config):
    if not TTS_API_KEY: return None
    clean_text = re.sub(r'^.*?:', '', text)
    clean_text = re.sub(r'\(.*?\)', '', clean_text).strip()
    if not clean_text: return None
    url = "https://texttospeech.googleapis.com/v1/text:synthesize?key=" + TTS_API_KEY
    payload = {
        "input": {"text": clean_text},
        "voice": {"languageCode": "th-TH", "name": voice_config["name"]},
        "audioConfig": {"audioEncoding": "MP3", "pitch": voice_config["pitch"], "speakingRate": voice_config["rate"]}
    }
    try:
