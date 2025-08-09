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

# -------------------------
# Config
# -------------------------
openai.api_key = API_KEY
app = Flask(__name__)

# Ensure file paths work regardless of cwd
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_LINKS_PATH = os.path.join(BASE_DIR, "pdf_links.json")

# Load pdf_links.json if exists
pdf_links = {}
if os.path.exists(PDF_LINKS_PATH):
    try:
        with open(PDF_LINKS_PATH, "r", encoding="utf-8") as f:
            pdf_links = json.load(f)
    except Exception as e:
        print("Warning: failed to load pdf_links.json:", e)
else:
    print("Notice: pdf_links.json not found at", PDF_LINKS_PATH)

# -------------------------
# Home (HTML docs with CSS)
# -------------------------
@app.route('/')
def home():
    return """
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width,initial-scale=1" />
      <title>Smart AI Helper API</title>
      <style>
        :root{--accent:#0f766e;--muted:#6b7280;--bg:#f3f4f6}
        body{font-family:Inter,ui-sans-serif,system-ui,Segoe UI,Roboto,"Helvetica Neue",Arial; background:var(--bg); margin:0}
        header{background:linear-gradient(90deg,var(--accent),#10b981); color:white; padding:36px 20px; text-align:center}
        .wrap{max-width:980px;margin:24px auto;padding:20px}
        .card{background:white;border-radius:12px;padding:18px;box-shadow:0 6px 20px rgba(2,6,23,0.08);margin-bottom:16px}
        h1{margin:0;font-size:28px}
        p.lead{color:var(--muted);margin-top:8px}
        .endpoints{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}
        .ep{border-left:4px solid var(--accent);padding:12px;border-radius:8px;background:#fbfbfb}
        code{background:#11182710;padding:2px 6px;border-radius:6px;font-family:monospace}
        pre{background:#0f172a08;padding:12px;border-radius:8px;overflow:auto}
        footer{padding:16px;text-align:center;color:var(--muted);font-size:14px}
        @media(max-width:760px){.endpoints{grid-template-columns:1fr}}
      </style>
    </head>
    <body>
      <header>
        <h1>✅ Smart AI Helper API</h1>
        <p class="lead">One-stop API for summaries, notes, MCQ/CQ, image Q&A, math solver, and NCTB chapter processing (Class 1–12).</p>
      </header>

      <div class="wrap">
        <div class="card">
          <h3>Available Endpoints</h3>
          <div class="endpoints">
            <div class="ep"><b>POST</b> <code>/summary</code><br><small class="lead">YouTube link or text → Bengali summary</small></div>
            <div class="ep"><b>POST</b> <code>/mcq</code><br><small>Text/chapter → 5 MCQs</small></div>
            <div class="ep"><b>POST</b> <code>/image-to-notes</code><br><small>Image → extracted notes</small></div>
            <div class="ep"><b>POST</b> <code>/image-to-mcq</code><br><small>Image → MCQs</small></div>
            <div class="ep"><b>POST</b> <code>/image-to-cq</code><br><small>Image → CQ</small></div>
            <div class="ep"><b>POST</b> <code>/routine</code><br><small>Subjects+hours → weekly routine</small></div>
            <div class="ep"><b>POST</b> <code>/chapter-to-mcq</code><br><small>class,subject,chapter → PDF-based MCQs</small></div>
            <div class="ep"><b>POST</b> <code>/chapter-to-cq</code><br><small>class,subject,chapter → PDF-based CQs</small></div>
            <div class="ep"><b>POST</b> <code>/image-to-answer</code><br><small>Image of question → answer</small></div>
            <div class="ep"><b>POST</b> <code>/text-to-word-meaning</code><br><small>Text → meanings of important words</small></div>
            <div class="ep"><b>POST</b> <code>/text-to-answer</code><br><small>Text question → answer</small></div>
            <div class="ep"><b>POST</b> <code>/math-solver</code><br><small>Math problem text → step-by-step solution</small></div>
            <div class="ep"><b>POST</b> <code>/image-to-math-solver</code><br><small>Image of math problem → solution</small></div>
          </div>
        </div>

        <div class="card">
          <h3>Quick Examples</h3>
          <pre>
POST /summary
Content-Type: application/json

{ "video_url": "https://www.youtube.com/watch?v=abcd1234" }

POST /chapter-to-mcq
{ "class": "Class 7", "subject": "Science", "chapter": "জীবনের বৈচিত্র্য" }

POST /image-to-mcq
{ "image_base64": "<BASE64_IMAGE>" }
          </pre>
          <p class="lead">All requests must be <code>POST</code> with JSON body. Responses are JSON.</p>
        </div>

        <div class="card">
          <h3>Notes & Tips</h3>
          <ul>
            <li>Make sure <code>config.py</code> contains your OpenAI API key.</li>
            <li>Install Tesseract OCR on the server for image -> text (pytesseract) to work.</li>
            <li>If you use <code>/chapter-to-mcq</code>, ensure <code>pdf_links.json</code> is present and contains the requested class & subject.</li>
          </ul>
        </div>
      </div>

      <footer>
        Developed by Sakil Islam Sabbir · Smart AI Helper · (Class 1–12 support)
      </footer>
    </body>
    </html>
    """

# -------------------------
# Helper: call OpenAI chat (simple wrapper)
# -------------------------
def openai_chat_reply(prompt, model="gpt-3.5-turbo", max_tokens=1500, temperature=0.2):
    try:
        resp = openai.ChatCompletion.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature
        )
        return resp['choices'][0]['message']['content']
    except Exception as e:
        return f"Error from OpenAI: {e}"

# -------------------------
# /summary
# -------------------------
@app.route('/summary', methods=['POST'])
def summarize():
    data = request.json or {}
    text = data.get("text", "") or ""
    video_url = data.get("video_url", "") or ""

    if video_url and not text:
        try:
            parsed_url = urlparse(video_url)
            video_id = parse_qs(parsed_url.query).get("v")
            if not video_id:
                return jsonify({"error": "Invalid YouTube URL"}), 400
            video_id = video_id[0]
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['bn', 'en'])
            text = " ".join([entry['text'] for entry in transcript])
        except Exception as e:
            return jsonify({"error": f"Transcript error: {e}"}), 400

    if not text:
        return jsonify({"error": "No text or video transcript provided."}), 400

    prompt = f"এই বক্তব্যটা সংক্ষেপে বাংলা ভাষায় বুঝিয়ে দাও:\n\n{text}"
    summary = openai_chat_reply(prompt)
    return jsonify({"summary": summary})

# -------------------------
# /mcq
# -------------------------
@app.route('/mcq', methods=['POST'])
def mcq():
    data = request.json or {}
    chapter = data.get("chapter", "")
    if not chapter:
        return jsonify({"error": "Provide 'chapter' text"}), 400
    prompt = f"{chapter}\n\nএই বিষয় থেকে ৫টি MCQ তৈরি করো, প্রতিটি MCQ-এ ৪টি অপশন দাও এবং সঠিক অপশনের নাম উল্লেখ করো।"
    result = openai_chat_reply(prompt)
    return jsonify({"mcqs": result})

# -------------------------
# /image-to-notes
# -------------------------
@app.route('/image-to-notes', methods=['POST'])
def image_to_notes():
    data = request.json or {}
    image_data = data.get("image_base64", "")
    if not image_data:
        return jsonify({"error": "Provide image_base64"}), 400
    try:
        image = Image.open(io.BytesIO(base64.b64decode(image_data)))
        extracted_text = pytesseract.image_to_string(image, lang="eng+ben")
    except Exception as e:
        return jsonify({"error": f"Image processing error: {e}"}), 400

    prompt = f"এই লেখাটির বাংলা সংক্ষিপ্ত নোট লিখো:\n\n{extracted_text}"
    summary = openai_chat_reply(prompt)
    return jsonify({"extracted_text": extracted_text, "summary": summary})

# -------------------------
# /image-to-mcq
# -------------------------
@app.route('/image-to-mcq', methods=['POST'])
def image_to_mcq():
    data = request.json or {}
    image_data = data.get("image_base64", "")
    if not image_data:
        return jsonify({"error": "Provide image_base64"}), 400
    try:
        image = Image.open(io.BytesIO(base64.b64decode(image_data)))
        extracted_text = pytesseract.image_to_string(image, lang="eng+ben")
    except Exception as e:
        return jsonify({"error": f"Image processing error: {e}"}), 400

    prompt = f"নিচের লেখা দেখে ৫টি MCQ তৈরি করো (প্রতিটি MCQ-তে ৪টি অপশন এবং সঠিক উত্তর দিন):\n\n{extracted_text}"
    mcqs = openai_chat_reply(prompt)
    return jsonify({"extracted_text": extracted_text, "mcqs": mcqs})

# -------------------------
# /image-to-cq
# -------------------------
@app.route('/image-to-cq', methods=['POST'])
def image_to_cq():
    data = request.json or {}
    image_data = data.get("image_base64", "")
    if not image_data:
        return jsonify({"error": "Provide image_base64"}), 400
    try:
        image = Image.open(io.BytesIO(base64.b64decode(image_data)))
        extracted_text = pytesseract.image_to_string(image, lang="eng+ben")
    except Exception as e:
        return jsonify({"error": f"Image processing error: {e}"}), 400

    prompt = f"নিচের লেখা দেখে ১টি সাধারন/সৃজনশীল (CQ) প্রশ্ন তৈরী করুন এবং উত্তরসহ ব্যাখ্যা দিন:\n\n{extracted_text}"
    cq = openai_chat_reply(prompt)
    return jsonify({"extracted_text": extracted_text, "cq": cq})

# -------------------------
# /routine
# -------------------------
@app.route('/routine', methods=['POST'])
def routine():
    data = request.json or {}
    subjects = data.get("subjects", "")
    hours = data.get("hours", 2)
    if not subjects:
        return jsonify({"error": "Provide subjects"}), 400
    prompt = f"এই বিষয়গুলো: {subjects} দিয়ে প্রতিদিন {hours} ঘন্টা করে ১ সপ্তাহের পড়াশোনার রুটিন বানাও।"
    resp = openai_chat_reply(prompt)
    return jsonify({"routine": resp})

# -------------------------
# /chapter-to-mcq
# -------------------------
@app.route('/chapter-to-mcq', methods=['POST'])
def chapter_to_mcq():
    data = request.json or {}
    class_name = data.get("class")
    subject = data.get("subject")
    chapter = data.get("chapter")
    if not (class_name and subject and chapter):
        return jsonify({"error": "class, subject and chapter required"}), 400

    try:
        pdf_url = pdf_links[class_name][subject]
    except Exception:
        return jsonify({"error": "PDF link not found for given class/subject"}), 404

    try:
        r = requests.get(pdf_url, timeout=15)
        r.raise_for_status()
        pdf_bytes = r.content
        text = ""
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page in doc:
                text += page.get_text()
        prompt = f"অধ্যায়: '{chapter}' সম্পর্কিত অংশ খুঁজে নিয়ে ৫টি MCQ তৈরি করো (অপশনসহ এবং সঠিক উত্তর):\n\n{text[:4000]}"
        mcqs = openai_chat_reply(prompt)
        return jsonify({"mcqs": mcqs})
    except Exception as e:
        return jsonify({"error": f"Failed to process PDF: {e}"}), 500

# -------------------------
# /chapter-to-cq
# -------------------------
@app.route('/chapter-to-cq', methods=['POST'])
def chapter_to_cq():
    data = request.json or {}
    class_name = data.get("class")
    subject = data.get("subject")
    chapter = data.get("chapter")
    if not (class_name and subject and chapter):
        return jsonify({"error": "class, subject and chapter required"}), 400

    try:
        pdf_url = pdf_links[class_name][subject]
    except Exception:
        return jsonify({"error": "PDF link not found for given class/subject"}), 404

    try:
        r = requests.get(pdf_url, timeout=15)
        r.raise_for_status()
        pdf_bytes = r.content
        text = ""
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page in doc:
                text += page.get_text()
        prompt = f"অধ্যায়: '{chapter}' সম্পর্কিত অংশ খুঁজে নিয়ে ২টি সৃজনশীল প্রশ্ন (CQ) তৈরি করো এবং প্রতিটির উত্তর ধাপে ধাপে লিখো:\n\n{text[:4000]}"
        cqs = openai_chat_reply(prompt)
        return jsonify({"cqs": cqs})
    except Exception as e:
        return jsonify({"error": f"Failed to process PDF: {e}"}), 500

# -------------------------
# /image-to-answer
# -------------------------
@app.route('/image-to-answer', methods=['POST'])
def image_to_answer():
    data = request.json or {}
    image_data = data.get("image_base64", "")
    if not image_data:
        return jsonify({"error": "Provide image_base64"}), 400
    try:
        image = Image.open(io.BytesIO(base64.b64decode(image_data)))
        extracted_text = pytesseract.image_to_string(image, lang="eng+ben")
    except Exception as e:
        return jsonify({"error": f"Image processing error: {e}"}), 400

    prompt = f"প্রশ্ন: {extracted_text}\nএটির সংক্ষিপ্ত ও পরিষ্কার উত্তর বাংলা ভাষায় দাও:"
    answer = openai_chat_reply(prompt)
    return jsonify({"extracted_text": extracted_text, "answer": answer})

# -------------------------
# /text-to-word-meaning
# -------------------------
@app.route('/text-to-word-meaning', methods=['POST'])
def text_to_word_meaning():
    data = request.json or {}
    text = data.get("text", "")
    if not text:
        return jsonify({"error": "Provide text"}), 400
   
