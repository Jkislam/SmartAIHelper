from flask import Flask, request, jsonify
import openai
import pytesseract
from PIL import Image
import base64
import io
import os
from config import API_KEY

openai.api_key = API_KEY
app = Flask(__name__)

# 🔹 ১. ভিডিও ➡️ সামারি
@app.route('/summary', methods=['POST'])
def summarize():
    data = request.json
    text = data.get("text", "")
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": f"এই বক্তব্যটা সংক্ষেপে বাংলা ভাষায় বুঝিয়ে দাও:\n{text}"}]
    )
    return jsonify({"summary": response['choices'][0]['message']['content']})

# 🔹 ২. অধ্যায় ➡️ MCQ
@app.route('/mcq', methods=['POST'])
def mcq():
    data = request.json
    chapter = data.get("chapter", "")
    prompt = f"{chapter} বিষয় থেকে ৫টি MCQ তৈরি করো, অপশনসহ এবং সঠিক উত্তর দাও।"
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return jsonify({"mcqs": response['choices'][0]['message']['content']})

# 🔹 ৩. ছবি ➡️ নোট
@app.route('/image-to-notes', methods=['POST'])
def image_to_notes():
    data = request.json
    image_data = data.get("image_base64", "")
    image = Image.open(io.BytesIO(base64.b64decode(image_data)))
    extracted_text = pytesseract.image_to_string(image, lang="eng+ben")

    # Now summarize
    prompt = f"এই লেখাটার বাংলা ভাষায় সংক্ষিপ্ত নোট বানাও:\n{extracted_text}"
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return jsonify({
        "extracted_text": extracted_text,
        "summary": response['choices'][0]['message']['content']
    })

# 🔹 ৪. রুটিন প্ল্যানার
@app.route('/')
def home():
    return "<h3>✅ Smart AI Helper API is Live.<br>Use POST to /summary, /mcq, /image-to-notes or /routine</h3>"
def routine():
    data = request.json
    subjects = data.get("subjects", "")
    hours = data.get("hours", 2)
    prompt = f"এই বিষয়গুলো: {subjects} দিয়ে প্রতিদিন {hours} ঘন্টা করে ১ সপ্তাহের পড়াশোনার রুটিন বানাও।"
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return jsonify({"routine": response['choices'][0]['message']['content']})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 7860))  # Render PORT ধরে
    app.run(host='0.0.0.0', port=port)

