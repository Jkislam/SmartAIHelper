from flask import Flask, request, jsonify
import openai
import pytesseract
from PIL import Image
import base64
import io
import os
import fitz  # PyMuPDF
import json
import requests
from config import API_KEY
from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs

openai.api_key = API_KEY
app = Flask(__name__)

# লিংক ফাইল লোড
with open("pdf_links.json", "r", encoding="utf-8") as f:
    pdf_links = json.load(f)

# ===========================
# হোম রুট
# ===========================
@app.route('/')
def home():
    return "<h3>✅ Smart AI Helper API is Live.<br>Use POST requests to endpoints like /summary, /mcq, /image-to-notes, /image-to-mcq, /image-to-cq, /routine, /chapter-to-mcq, /chapter-to-cq, /image-to-answer, /text-to-word-meaning, /text-to-answer, /math-solver, /image-to-math-solver</h3>"

# ===========================
# ১. ভিডিও ➡️ সামারি
# ===========================
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

# ===========================
# ২. অধ্যায় ➡️ MCQ
# ===========================
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

# ===========================
# ৩. ছবি ➡️ নোট
# ===========================
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

# ===========================
# ৪. ছবি ➡️ MCQ
# ===========================
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

# ===========================
# ৫. ছবি ➡️ CQ
# ===========================
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

# ===========================
# ৬. রুটিন প্ল্যানার
# ===========================
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

# ===========================
# ৭. অধ্যায় ➡️ MCQ (PDF থেকে)
# ===========================
@app.route('/chapter-to-mcq', methods=['POST'])
def chapter_to_mcq():
    data = request.json
    class_name = data.get("class")
    subject = data.get("subject")
    chapter = data.get("chapter")

    if not (class_name and subject and chapter):
        return jsonify({"error": "class, subject and chapter required"}), 400

    try:
        pdf_url = pdf_links[class_name][subject]
        response = requests.get(pdf_url)
        pdf_bytes = response.content
        text = ""
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page in doc:
                text += page.get_text()

        prompt = f"এই অধ্যায়ের নাম: '{chapter}'। নিচে বইয়ের কিছু লেখা আছে। এই অধ্যায়ের অংশ খুঁজে নিয়ে ৫টি MCQ তৈরি করো, অপশনসহ এবং সঠিক উত্তর দাও:\n\n{text[:4000]}"

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return jsonify({"mcqs": response['choices'][0]['message']['content']})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ===========================
# ৮. অধ্যায় ➡️ CQ (PDF থেকে)
# ===========================
@app.route('/chapter-to-cq', methods=['POST'])
def chapter_to_cq():
    data = request.json
    class_name = data.get("class")
    subject = data.get("subject")
    chapter = data.get("chapter")

    if not (class_name and subject and chapter):
        return jsonify({"error": "class, subject and chapter required"}), 400

    try:
        pdf_url = pdf_links[class_name][subject]
        response = requests.get(pdf_url)
        pdf_bytes = response.content
        text = ""
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page in doc:
                text += page.get_text()

        prompt = f"এই অধ্যায়ের নাম: '{chapter}'। নিচে বইয়ের কিছু লেখা আছে। এই অধ্যায়ের অংশ খুঁজে নিয়ে ২টি সৃজনশীল প্রশ্ন (CQ) তৈরি করো, প্রতিটির জন্য নম্বরসহ ধাপ ভাগ করে উত্তরসহ:\n\n{text[:4000]}"

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return jsonify({"cqs": response['choices'][0]['message']['content']})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ===========================
# ৯. ছবি ➡️ উত্তর
# ===========================
@app.route('/image-to-answer', methods=['POST'])
def image_to_answer():
    data = request.json
    image_data = data.get("image_base64", "")
    image = Image.open(io.BytesIO(base64.b64decode(image_data)))
    extracted_text = pytesseract.image_to_string(image, lang="eng+ben")

    prompt = f"প্রশ্ন: {extracted_text}\nএটির সঠিক উত্তর বাংলা ভাষায় দাও।"
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return jsonify({
        "extracted_text": extracted_text,
        "answer": response['choices'][0]['message']['content']
    })

# ===========================
# ১০. টেক্সট ➡️ শব্দার্থ
# ===========================
@app.route('/text-to-word-meaning', methods=['POST'])
def text_to_word_meaning():
    data = request.json
    text = data.get("text", "")

    prompt = f"এই শব্দগুলোর বাংলা অর্থ দাও:\n{text}"
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return jsonify({"word_meanings": response['choices'][0]['message']['content']})

# ===========================
# ১১. টেক্সট ➡️ উত্তর
# ===========================
@app.route('/text-to-answer', methods=['POST'])
def text_to_answer():
    data = request.json
    question = data.get("question", "")

    prompt = f"প্রশ্ন: {question}\nএটির সঠিক উত্তর বাংলা ভাষায় দাও।"
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return jsonify({"answer": response['choices'][0]['message']['content']})

# ===========================
# ১২. ম্যাথ সলভার
# ===========================
@app.route('/math-solver', methods=['POST'])
def math_solver():
    data = request.json
    math_problem = data.get("problem", "")

    prompt = f"সমস্যা: {math_problem}\nএটি ধাপে ধাপে সমাধান করো এবং প্রতিটি ধাপের ব্যাখ্যা দাও।"
    response = openai.ChatCompletion.create(
        model="gpt-4",  # বেশি সঠিকতার জন্য gpt-4
        messages=[{"role": "user", "content": prompt}]
    )
    return jsonify({"solution": response['choices'][0]['message']['content']})

# ===========================
# ১৩. ছবি ➡️ ম্যাথ সলভার
# ===========================
@app.route('/image-to-math-solver', methods=['POST'])
def image_to_math_solver():
    data = request.json
    image_data = data.get("image_base64", "")
    image = Image.open(io.BytesIO(base64.b64decode(image_data)))
    math_text = pytesseract.image_to_string(image, lang="eng")

    prompt = f"সমস্যা: {math_text}\nএটি ধাপে ধাপে সমাধান করো এবং প্রতিটি ধাপের ব্যাখ্যা দাও।"
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return jsonify({
        "extracted_text": math_text,
        "solution": response['choices'][0]['message']['content']
    })

# ===========================
# রান
# ===========================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 7860))
    app.run(host='0.0.0.0', port=port)
