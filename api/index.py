import os
import requests
import re
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai

app = Flask(__name__)

# --- [ส่วนที่ 1: ตั้งค่า API] ---
GENAI_API_KEY = os.environ.get("GENAI_API_KEY")
TTS_API_KEY = os.environ.get("TTS_API_KEY")
genai.configure(api_key=GENAI_API_KEY)
# บังคับใช้ Gemini 2.5 Flash ตามคำขอของอาร์ม
model = genai.GenerativeModel(model_name="gemini-2.5-flash")

# --- [ส่วนที่ 2: ลอจิก Cold Call และ รายชื่อลูกค้า] ---
COLD_CALL_RULES = """
[คำสั่งเด็ดขาด]: คุณคือ "ลูกค้า" เท่านั้น ห้ามตอบหรือสวมบทบาทเป็นพนักงานเด็ดขาด
1. [การจดจำ]: อ่าน History ให้ละเอียด ห้ามถามชื่อพนักงานหรือเลขใบอนุญาตซ้ำหากเคยแจ้งแล้ว
2. [คำแทนตัว]: ผู้หญิงใช้ 'ฉัน/เรา', ผู้ชายใช้ 'ผม' 
3. [บุคลิก]: เริ่มจากไม่ไว้วางใจ ปฏิเสธการขายในช่วงแรก 4-5 รอบ จนกว่าพนักงานจะพูดถูกต้องตามกฎ คปภ.
"""

CUSTOMERS = {
    "1": {"name": "น้องฟ้า", "desc": "ออม 20/9", "prompt": COLD_CALL_RULES + "คุณคือ 'ฟ้า' อายุ 25 ปี ลงท้าย 'ค่ะ'", "voice": {"name": "th-TH-Standard-A", "pitch": 0.0, "rate": 1.0}},
    "2": {"name": "คุณวิรัช", "desc": "สุขภาพ", "prompt": COLD_CALL_RULES + "คุณคือ 'วิรัช' อายุ 45 ปี ลงท้าย 'ครับ' เน้นถามเรื่องความคุ้มครองสุขภาพ", "voice": {"name": "th-TH-Neural2-C", "pitch": 0.0, "rate": 1.0}},
    "3": {"name": "คุณป้ามาลี", "desc": "มรดก", "prompt": COLD_CALL_RULES + "คุณคือ 'ป้ามาลี' อายุ 50 ปี ลงท้าย 'ค่ะ/จ๊ะ'", "voice": {"name": "th-TH-Standard-A", "pitch": -1.5, "rate": 0.9}},
    "4": {"name": "แม่แอน", "desc": "ปฏิเสธหนัก", "prompt": COLD_CALL_RULES + "คุณคือ 'แอน' ปฏิเสธเรื่องประกันตลอด", "voice": {"name": "th-TH-Standard-A", "pitch": 0.0, "rate": 1.0}},
    "5": {"name": "คุณอัครเดช", "desc": "นักธุรกิจ", "prompt": COLD_CALL_RULES + "คุณคือ 'อัครเดช' เวลาน้อยและดุ", "voice": {"name": "th-TH-Neural2-C", "pitch": -0.5, "rate": 1.0}}
}

def get_audio_base64(text, voice_config):
    if not TTS_API_KEY: return None
    
    # ล้างข้อความ (ตัดชื่อผู้พูดออกเพื่อให้เสียงลื่นไหล)
    clean_text = re.sub(r'^.*?:', '', text)
    clean_text = re.sub(r'\(.*?\)', '', clean_text).strip()
    if not clean_text: return None
    
    # อัปเกรดเป็น v1beta1 เพื่อรองรับเสียง Neural2-C (เสียงผู้ชาย)
    url = f"https://texttospeech.googleapis.com/v1beta1/text:synthesize?key={TTS_API_KEY}"
    
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
        res = requests.post(url, json=payload, timeout=10)
        return res.json().get("audioContent")
    except: return None

# --- [ส่วนที่ 3: UI และ JavaScript (ใช้ตัวเดิมของคุณอาร์มได้เลย)] ---
# ... (ก๊อปปี้ส่วน HTML_TEMPLATE จากไฟล์เดิมมาวางตรงนี้ได้เลยครับ) ...

# --- [ส่วนที่ 4: API Chat - แก้ไขโครงสร้าง Prompt เพื่อล็อกบทบาทลูกค้า] ---
@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        lvl, user_msg, history = data.get('lvl'), data.get('message'), data.get('history', [])
        cust = CUSTOMERS[lvl]
        
        # ปรับโครงสร้าง Prompt ให้ชัดเจนขึ้น
        context = "\n".join(history[-8:]) # เอา 8 ประโยคล่าสุดพอ เพื่อความจำ
        
        full_prompt = f"""บทบาทของคุณ: {cust['prompt']}
ประวัติการคุย:
{context}
พนักงานขายพูดว่า: "{user_msg}"
จงตอบกลับในฐานะลูกค้าเท่านั้น:"""

        response = model.generate_content(full_prompt)
        reply_text = response.text
        
        # ดึงเสียง
        audio_data = get_audio_base64(reply_text, cust['voice'])
        
        return jsonify({"reply": reply_text, "audio": audio_data})
    except Exception as e:
        return jsonify({"reply": f"เกิดข้อผิดพลาด: {str(e)}", "audio": None}), 500

# (เพิ่มส่วน evaluate ตามไฟล์เดิมของคุณอาร์มได้เลยครับ)
