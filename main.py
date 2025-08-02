from flask import Flask, request, jsonify
import openai
import pytesseract
from PIL import Image
import base64
import io
import os
from config import API_KEY
from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs

openai.api_key = API_KEY
app = Flask(__name__)

# 🔹 হোম রুট
@app.route('/')
def home():
    return "<h3>✅ Smart AI Helper API is Live.<br>Use POST to /summary, /mcq, /image-to-notes, /image-to-mcq, /image-to-cq or /routine</h3>"

# 🔹 ১. ভিডিও ➡️ সামারি
@app.route('/summary', methods=['POST'])
def summarize():
    data = request.json
    text = data.get("text", "")
    video_url = data.get("video_url", "")

    if video_url:
        try:
            parsed_url = urlparse(video_url)
            video_id = parse_qs(parsed_url.query).get("v")
            if video_id:
                video_id = video_id[0]
                transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['bn', 'en'])
                text = " ".join([entry['text'] for entry in transcript])
            else:
                return jsonify({"error": "Invalid YouTube URL"}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    if not text:
        return jsonify({"error": "No text or video transcript provided."}), 400

    prompt = f"এই বক্তব্যটা সংক্ষেপে বাংলা ভাষায় বুঝিয়ে দাও:\n{text}"
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
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

    prompt = f"এই লেখাটার বাংলা ভাষায় সংক্ষিপ্ত নোট বানাও:\n{extracted_text}"
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return jsonify({
        "extracted_text": extracted_text,
        "summary": response['choices'][0]['message']['content']
    })

# 🔹 ৪. ছবি ➡️ MCQ
@app.route('/image-to-mcq', methods=['POST'])
def image_to_mcq():
    data = request.json
    image_data = data.get("image_base64", "")
    image = Image.open(io.BytesIO(base64.b64decode(image_data)))
    extracted_text = pytesseract.image_to_string(image, lang="eng+ben")

    prompt = f"এই লেখাটার ভিত্তিতে ৫টি MCQ তৈরি করো, অপশনসহ এবং সঠিক উত্তরসহ:\n{extracted_text}"
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return jsonify({
        "extracted_text": extracted_text,
        "mcqs": response['choices'][0]['message']['content']
    })

# 🔹 ৫. ছবি ➡️ CQ
@app.route('/image-to-cq', methods=['POST'])
def image_to_cq():
    data = request.json
    image_data = data.get("image_base64", "")
    image = Image.open(io.BytesIO(base64.b64decode(image_data)))
    extracted_text = pytesseract.image_to_string(image, lang="eng+ben")

    prompt = f"এই লেখাটার ভিত্তিতে একটি সৃজনশীল প্রশ্ন তৈরি করো। অনুচ্ছেদ, প্রশ্ন এবং উত্তরসহ:\n{extracted_text}"
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return jsonify({
        "extracted_text": extracted_text,
        "cq": response['choices'][0]['message']['content']
    })

# 🔹 ৬. রুটিন প্ল্যানার
@app.route('/routine', methods=['POST'])
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
    port = int(os.environ.get("PORT", 7860))
    app.run(host='0.0.0.0', port=port)
