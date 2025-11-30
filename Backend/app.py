import os
import re
import time
import logging
import importlib
import sys
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
import requests

# Optional PDF support
try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, VideoUnavailable

# Load environment
load_dotenv()
HF_API_KEY = os.getenv("HF_API_KEY")
# default summarization model (Hugging Face)
HF_SUMMARY_MODEL = os.getenv("HF_SUMMARY_MODEL", "sshleifer/distilbart-cnn-12-6")
# fallback translation model name pattern: Helsinki-NLP/opus-mt-<src>-en
TRANSLATION_MODEL_TEMPLATE = "Helsinki-NLP/opus-mt-{src}-en"
# sentiment analysis model
HF_SENTIMENT_MODEL = os.getenv("HF_SENTIMENT_MODEL", "cardiffnlp/twitter-roberta-base-sentiment-latest")

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HF_TIMEOUT = 60
HF_RETRIES = 2

# ---------------- utilities ----------------
def extract_video_id(url: str):
    if not url:
        return None
    # Check if it's a direct video ID (11 chars, alphanumeric + _ -)
    trimmed = url.strip()
    if re.match(r'^[a-zA-Z0-9_-]{11}$', trimmed):
        return trimmed
    # Comprehensive patterns to match all YouTube URL formats (case-insensitive)
    patterns = [
        r'(?:https?://)?(?:www\.|m\.)?(?:youtube\.com/(?:watch\?v=|embed/|v/)|youtu\.be/)([a-zA-Z0-9_-]{11})(?:\S*)?',
        r'(?:https?://)?(?:www\.|m\.)?youtube\.com/v/([a-zA-Z0-9_-]{11})(?:\S*)?',
        r'v=([a-zA-Z0-9_-]{11})(?:&|\s|$)',
        r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        r'youtu\.be/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/v/([a-zA-Z0-9_-]{11})'
    ]
    for pattern in patterns:
        m = re.search(pattern, trimmed, re.IGNORECASE)
        if m:
            return m.group(1)
    return None

def chunk_text(text: str, max_chars: int = 3000, overlap: int = 200):
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    chunks = []
    start = 0
    L = len(text)
    while start < L:
        end = start + max_chars
        if end >= L:
            chunks.append(text[start:].strip())
            break
        snippet = text[start:end]
        last_period = snippet.rfind('. ')
        if last_period > max_chars // 3:
            end = start + last_period + 1
        chunk = text[start:end].strip()
        chunks.append(chunk)
        start = end - overlap
        if start < 0:
            start = 0
    return chunks

def hf_inference(model: str, inputs: str, timeout: int = HF_TIMEOUT):
    """
    Call Hugging Face Inference API for given model and inputs.
    Returns (status_code, parsed_result_or_text)
    """
    if not HF_API_KEY:
        raise ValueError("HF_API_KEY not set in environment variables")
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    payload = {"inputs": inputs}
    # For summarization we may pass parameters; caller can extend payload if needed.
    try:
        r = requests.post(
            f"https://router.huggingface.co/hf-inference/models/{model}",
            headers=headers,
            json=payload,
            timeout=timeout
        )
    except Exception as e:
        logger.warning("HF request exception: %s", e)
        return None, {"error": str(e)}
    try:
        data = r.json()
    except Exception:
        data = r.text
    return r.status_code, data

def call_hf_summarize(text: str):
    """Summarize text using HF summary model with retries and robust parsing."""
    if not HF_API_KEY:
        raise ValueError("HF_API_KEY not configured")
    payload_template = {
        "inputs": text,
        "parameters": {"max_length": 150, "min_length": 50, "do_sample": False}
    }
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    last_err = None
    for attempt in range(HF_RETRIES + 1):
        try:
            resp = requests.post(
                f"https://router.huggingface.co/hf-inference/models/{HF_SUMMARY_MODEL}",
                headers=headers,
                json=payload_template,
                timeout=HF_TIMEOUT
            )
            # parse
            if resp.status_code == 200:
                try:
                    data = resp.json()
                except Exception:
                    return resp.text
                # handle shapes
                if isinstance(data, list) and len(data) and isinstance(data[0], dict):
                    # some models return [{'summary_text': '...'}]
                    if "summary_text" in data[0]:
                        return data[0]["summary_text"]
                    # other models might use 'generated_text'
                    if "generated_text" in data[0]:
                        return data[0]["generated_text"]
                    # fallback to first value
                    for v in data[0].values():
                        if isinstance(v, str):
                            return v
                    return str(data[0])
                if isinstance(data, dict):
                    if "summary_text" in data:
                        return data["summary_text"]
                    if "generated_text" in data:
                        return data["generated_text"]
                    # fallback
                    for v in data.values():
                        if isinstance(v, str):
                            return v
                    return str(data)
                if isinstance(data, str):
                    return data
                return str(data)
            else:
                last_err = f"{resp.status_code}: {resp.text}"
                logger.warning("HF summarize attempt %d failed: %s", attempt + 1, last_err)
                time.sleep(1 + attempt)
        except requests.RequestException as e:
            last_err = str(e)
            logger.warning("HF summarize request exception attempt %d: %s", attempt + 1, last_err)
            time.sleep(1 + attempt)
    raise RuntimeError(f"Hugging Face summarization failed after retries: {last_err}")

def call_hf_translate(text: str, src_lang: str):
    """
    Translate `text` from src_lang to English using HF translation model.
    Returns translated_text on success, None on failure.
    """
    if not HF_API_KEY:
        raise ValueError("HF_API_KEY not configured")
    # sanitize src_lang to simple code (e.g., 'hi' or 'pt' etc.)
    src = (src_lang or "").split("-")[0].lower()
    model_name = TRANSLATION_MODEL_TEMPLATE.format(src=src)
    logger.info("Attempting translation using model %s", model_name)
    # translate in chunks to avoid input length limits
    chunks = chunk_text(text, max_chars=2500, overlap=100)
    translated_chunks = []
    for i, ch in enumerate(chunks):
        status, data = hf_inference(model_name, ch)
        if status == 200 and data:
            # try common output keys
            translated = None
            if isinstance(data, list) and len(data) and isinstance(data[0], dict):
                # translation models often return {'translation_text': '...'} or {'generated_text': '...' }
                translated = data[0].get("translation_text") or data[0].get("generated_text") or next((v for v in data[0].values() if isinstance(v, str)), None)
            elif isinstance(data, dict):
                translated = data.get("translation_text") or data.get("generated_text") or next((v for v in data.values() if isinstance(v, str)), None)
            elif isinstance(data, str):
                translated = data
            if translated:
                translated_chunks.append(translated)
                continue
            else:
                logger.warning("Unexpected translation response shape: %s", type(data))
                return None
        else:
            logger.warning("Translation failed (status=%s): %s", status, data)
            return None
    # join and return
    return "\n".join(translated_chunks)

def call_hf_sentiment(text: str):
    """
    Analyze sentiment of text using HF sentiment model.
    Returns dict with 'label' (e.g., 'POSITIVE', 'NEGATIVE', 'NEUTRAL') and 'score' (confidence).
    """
    if not HF_API_KEY:
        raise ValueError("HF_API_KEY not configured")
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    payload = {"inputs": text}
    try:
        resp = requests.post(
            f"https://router.huggingface.co/hf-inference/models/{HF_SENTIMENT_MODEL}",
            headers=headers,
            json=payload,
            timeout=HF_TIMEOUT
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) and isinstance(data[0], list):
                # Some models return [[{'label': 'POSITIVE', 'score': 0.99}, ...]]
                if len(data[0]) > 0:
                    return data[0][0]  # Take the top sentiment
            elif isinstance(data, list) and len(data) and isinstance(data[0], dict):
                return data[0]
            elif isinstance(data, dict):
                return data
        logger.warning("Sentiment analysis failed: %s", resp.text)
        return None
    except Exception as e:
        logger.warning("Sentiment analysis exception: %s", e)
        return None

def chunk_transcript_by_time(transcript_list, interval_seconds=30):
    """
    Chunk transcript into time intervals.
    transcript_list: list of dicts with 'start', 'duration', 'text'
    Returns list of dicts: [{'start': 0, 'end': 30, 'text': '...'}, ...]
    """
    if not transcript_list:
        return []
    chunks = []
    current_start = 0
    current_text = []
    for item in transcript_list:
        start = item.get('start', 0)
        duration = item.get('duration', 0)
        text = item.get('text', '').strip()
        if not text:
            continue
        end = start + duration
        while start >= current_start + interval_seconds:
            if current_text:
                chunks.append({
                    'start': current_start,
                    'end': current_start + interval_seconds,
                    'text': ' '.join(current_text)
                })
                current_text = []
            current_start += interval_seconds
        current_text.append(text)
    if current_text:
        chunks.append({
            'start': current_start,
            'end': current_start + interval_seconds,
            'text': ' '.join(current_text)
        })
    return chunks

# ---------------- Routes ----------------

@app.route("/")
def home():
    return jsonify({"message": "API is running"})

@app.route("/favicon.ico")
def favicon():
    return send_from_directory("static", "favicon.ico")

@app.route("/summarize/text", methods=["POST"])
def summarize_text():
    data = request.json or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "No text provided"}), 400
    try:
        chunks = chunk_text(text, max_chars=3000)
        summaries = [call_hf_summarize(c) for c in chunks]
        final = call_hf_summarize("\n".join(summaries)) if len(summaries) > 1 else summaries[0]
        return jsonify({"summary": final})
    except Exception as e:
        logger.exception("Error in summarize_text: %s", e)
        return jsonify({"error": "Summarization failed", "detail": str(e)}), 500

@app.route("/summarize/pdf", methods=["POST"])
def summarize_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    f = request.files["file"]
    if f.filename == "":
        return jsonify({"error": "No file selected"}), 400
    try:
        if fitz is None:
            raise RuntimeError("PyMuPDF (fitz) is not installed. Install pymupdf to enable PDF summarization.")
        doc = fitz.open(stream=f.read(), filetype="pdf")
        pages_text = [page.get_text() for page in doc]
        full_text = "\n".join(pages_text).strip()
        if not full_text:
            return jsonify({"error": "PDF contains no extractable text"}), 400
        chunks = chunk_text(full_text, max_chars=3000)
        summaries = [call_hf_summarize(c) for c in chunks]
        final = call_hf_summarize("\n".join(summaries)) if len(summaries) > 1 else summaries[0]
        return jsonify({"summary": final})
    except Exception as e:
        logger.exception("Error in summarize_pdf: %s", e)
        return jsonify({"error": "PDF summarization failed", "detail": str(e)}), 500

@app.route("/summarize/youtube", methods=["POST"])
def summarize_youtube():
    data = request.json or {}
    video_url = data.get("video_url")
    if not video_url:
        return jsonify({"error": "No video URL provided"}), 400
    mood_analysis = request.args.get("mood", "false").lower() == "true"

    video_id = extract_video_id(video_url)
    if not video_id:
        logger.warning("Failed to extract video ID from URL: %s", video_url)
        return jsonify({"error": "Invalid YouTube URL / could not extract ID"}), 400

    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
    except TranscriptsDisabled:
        return jsonify({"error": "Transcripts are disabled for this video"}), 400
    except NoTranscriptFound:
        return jsonify({"error": "No transcript found for this video"}), 404
    except VideoUnavailable:
        return jsonify({"error": "Video is unavailable"}), 404
    except Exception as e:
        logger.exception("Error fetching transcript: %s", e)
        return jsonify({"error": "Failed to fetch transcript", "detail": str(e)}), 500

    if not transcript_list:
        return jsonify({"error": "Transcript empty"}), 404

    # Extract text for summarization
    text_pieces = [item['text'] for item in transcript_list if item['text'].strip()]
    transcript_text = " ".join(text_pieces).strip()
    if not transcript_text:
        return jsonify({"error": "Transcript empty"}), 404

    # Infer language (simple heuristic: if any non-ascii present -> not en)
    sample = transcript_text[:200].lower()
    if re.search(r'[^\x00-\x7f]', sample):
        src_lang = "unknown_non_en"
    else:
        src_lang = "en"

    logger.info("Transcript language inferred: %s", src_lang)

    # Always attempt translation to English, regardless of detected language
    translated_text = None
    translation_attempted = False
    translation_src = None
    try:
        # Determine source language for translation model
        if src_lang and src_lang != "unknown_non_en":
            translation_src = src_lang.split("-")[0]
        else:
            # For unknown or non-English inferred, try to infer or use a default
            # Since we always attempt, we'll try with the detected src_lang if available
            translation_src = src_lang.split("-")[0] if src_lang else None

        if translation_src:
            logger.info("Attempting translation from detected language: %s", translation_src)
            translated_text = call_hf_translate(transcript_text, translation_src)
            translation_attempted = True
            if translated_text:
                logger.info("Translation succeeded (lang=%s).", translation_src)
            else:
                logger.warning("Translation returned None; will fall back to summarizing original transcript.")
        else:
            logger.info("No source language detected; attempting translation with default model (may fail).")
            # Try with a common non-English language or skip, but since we want to always attempt, perhaps try 'auto' or something
            # For simplicity, if no src, we'll skip but mark as attempted
            translation_attempted = True
            logger.warning("Cannot determine source language for translation; falling back to original transcript.")
    except Exception as e:
        logger.warning("Translation attempt raised exception: %s", e)
        translated_text = None
        translation_attempted = True

    # Decide final_text to summarize
    if translated_text:
        final_text = translated_text
        summary_language_note = f"(translated from {src_lang})" if src_lang else "(translated)"
    else:
        final_text = transcript_text
        if translation_attempted:
            summary_language_note = f"(translation attempted but failed; original language: {src_lang})" if src_lang else "(translation attempted but failed)"
        else:
            summary_language_note = f"(original language: {src_lang})" if src_lang else ""

    # Summarize (may be long; chunk and merge)
    try:
        chunks = chunk_text(final_text, max_chars=3000, overlap=200)
        logger.info("Summarizing %d chunks", len(chunks))
        chunk_summaries = [call_hf_summarize(c) for c in chunks]
        if len(chunk_summaries) > 1:
            final_summary = call_hf_summarize("\n".join(chunk_summaries))
        else:
            final_summary = chunk_summaries[0]

        response = {
            "summary": final_summary,
            "note": summary_language_note,
            "transcript_language": src_lang or None
        }

        # Mood analysis if requested
        if mood_analysis:
            try:
                logger.info("Performing mood analysis on transcript intervals")
                time_chunks = chunk_transcript_by_time(transcript_list, interval_seconds=30)
                mood_intervals = []
                for chunk in time_chunks:
                    text = chunk.get('text', '').strip()
                    if text:
                        sentiment = call_hf_sentiment(text)
                        if sentiment:
                            mood_intervals.append({
                                'start': chunk['start'],
                                'end': chunk['end'],
                                'mood': sentiment.get('label', 'UNKNOWN'),
                                'score': sentiment.get('score', 0.0)
                            })
                        else:
                            mood_intervals.append({
                                'start': chunk['start'],
                                'end': chunk['end'],
                                'mood': 'UNKNOWN',
                                'score': 0.0
                            })
                response["mood_intervals"] = mood_intervals
                logger.info("Mood analysis completed with %d intervals", len(mood_intervals))
            except Exception as e:
                logger.warning("Mood analysis failed: %s", e)
                response["mood_intervals"] = []

        return jsonify(response)
    except Exception as e:
        logger.exception("Error during summarization: %s", e)
        return jsonify({"error": "Summarization failed", "detail": str(e)}), 500

@app.route("/summarize/youtube-debug", methods=["POST"])
def summarize_youtube_debug():
    data = request.json or {}
    video_url = data.get("video_url")
    if not video_url:
        return jsonify({"error": "No video URL provided"}), 400
    vid = extract_video_id(video_url) or "UNKNOWN"
    info = {"video_id": vid, "python_executable": sys.executable, "python_version": sys.version}
    try:
        yt_mod = importlib.import_module("youtube_transcript_api")
        info["yt_module_file"] = getattr(yt_mod, "__file__", None)
        info["yt_module_attrs_sample"] = [a for a in dir(yt_mod) if not a.startswith("_")][:200]
        YTClass = getattr(yt_mod, "YouTubeTranscriptApi", None)
        info["YouTubeTranscriptApi_present"] = bool(YTClass)
        if YTClass:
            info["YTClass_attrs"] = [a for a in dir(YTClass) if not a.startswith("_")]
            try:
                inst = YTClass()
                inst_attrs = [a for a in dir(inst) if not a.startswith("_")]
                info["instance_info"] = {
                    "inst_type": str(type(inst)),
                    "inst_attrs_sample": inst_attrs[:400],
                    "has_fetch": hasattr(inst, "fetch"),
                    "fetch_callable": callable(getattr(inst, "fetch", None)),
                    "has_get_transcript": hasattr(inst, "get_transcript"),
                    "get_transcript_callable": callable(getattr(inst, "get_transcript", None)),
                    "has_list": hasattr(inst, "list"),
                    "list_callable": callable(getattr(inst, "list", None)),
                }
            except Exception as e:
                info["instance_info_error"] = {"err": str(e), "err_type": type(e).__name__}
    except Exception as e:
        info["import_error"] = {"err": str(e), "err_type": type(e).__name__}
    try:
        import pkg_resources
        try:
            dist = pkg_resources.get_distribution("youtube-transcript-api")
            info["yt_distribution"] = {"project_name": dist.project_name, "version": dist.version, "location": dist.location}
        except Exception:
            info["yt_distribution"] = None
    except Exception:
        info["pkg_resources_available"] = False
    return jsonify({"debug": info})

# ---------------- run ----------------
if __name__ == "__main__":
    # development server
    app.run(debug=True)
