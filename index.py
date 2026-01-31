from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai
from supabase import create_client, Client
import os

app = Flask(__name__)

# --- คอนฟิก (แนะนำให้ใส่ใน Vercel Environment Variables) ---
GENAI_API_KEY = "ใส่_API_KEY_ของคุณที่นี่"
genai.configure(api_key=GENAI_API_KEY)

# เชื่อมต่อระบบ (ถ้ายังไม่ใช้ Supabase ทันทีให้ปล่อยว่างไว้ก่อนได้)
# SUPABASE_URL = "..."
# SUPABASE_KEY = "..."
# supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ตั้งค่า Gemini 2.5 Flash
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash", # ใช้รุ่นล่าสุดตามต้องการ
    system_instruction="คุณคือคุณวีระ อายุ 45 ปี สุภาพ ช่างคุย มีความดันสูง (บอกเมื่อถูกถามเท่านั้น) และสนใจประกันออมทรัพย์ให้ลูก"
)

# หน้าตา UI (HTML)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Telesale AI Simulator</title>
    <style>
        body { font-family: sans-serif; background: #f4f7f6; display: flex; justify-content: center; padding: 20px; }
        .chat-card { width: 100%; max-width: 500px; background: white; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); overflow: hidden; }
        .header { background: #1a73e8; color: white; padding: 15px; text-align: center; }
        #chat-content { height: 400px; overflow-y: auto; padding: 15px; border-bottom: 1px solid #eee; }
        .input-box { display: flex; padding: 10px; }
        input { flex: 1; padding: 10px; border: 1px solid #ddd; border-radius: 4px; outline: none; }
        button { background: #34a853; color: white; border: none; padding: 10px 20px; margin-left: 5px; border-radius: 4px; cursor: pointer; }
    </style>
</head>
<body>
    <div class="chat-card">
        <div class="header">คุยกับคุณวีระ (Simulator)</div>
        <div id="chat-content"></div>
        <div class="input-box">
            <input type="text" id="user-input" placeholder="พิมพ์บทพูดของคุณ...">
            <button onclick="send()">ส่ง</button>
        </div>
    </div>
    <script>
        async function send() {
            const input = document.getElementById('user-input');
            const box = document.getElementById('chat-content');
            if(!input.value) return;
            const msg = input.value;
            box.innerHTML += `<div><b>คุณ:</b> ${msg}</div>`;
            input.value = '';
            
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: msg})
            });
            const data = await res.json();
            box.innerHTML += `<div style="color:blue"><b>คุณวีระ:</b> ${data.reply}</div>`;
            box.scrollTop = box.scrollHeight;
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/chat', methods=['POST'])
def chat():
    user_msg = request.json.get('message')
    # ใน Vercel (Serverless) เรามักจะไม่ได้ใช้ chat_session แบบค้างไว้ 
    # แต่สามารถส่งประวัติกลับไปกลับมาได้ หรือส่งแบบ Single message
    response = model.generate_content(user_msg)
    return jsonify({"reply": response.text})

# สำหรับรันในเครื่องตัวเองเพื่อทดสอบ
if __name__ == "__main__":
    app.run(debug=True)