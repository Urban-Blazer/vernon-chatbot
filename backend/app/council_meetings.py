"""Council meeting audio download, transcription, summarization, and PDF ingestion."""

import io
import json
import logging
import subprocess

import anthropic
import requests

logger = logging.getLogger(__name__)

# Whisper model singleton to avoid reloading per-meeting
_whisper_model = None
_whisper_model_size = None


def download_audio(hls_url: str, output_path: str, timeout: int = 7200) -> bool:
    """Download and extract audio from an HLS stream using ffmpeg.

    Outputs 16kHz mono WAV (optimal for Whisper).
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", hls_url,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        output_path,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        if result.returncode != 0:
            logger.error(f"ffmpeg error: {result.stderr[-500:]}")
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error(f"ffmpeg download timed out after {timeout}s")
        return False
    except FileNotFoundError:
        logger.error("ffmpeg not found — install ffmpeg as a system dependency")
        return False


def transcribe_audio(audio_path: str, model_size: str = "small") -> str:
    """Transcribe an audio file using faster-whisper (CTranslate2 backend).

    The model is loaded once and cached for subsequent calls.
    """
    global _whisper_model, _whisper_model_size

    from faster_whisper import WhisperModel

    if _whisper_model is None or _whisper_model_size != model_size:
        logger.info(f"Loading Whisper model '{model_size}' (CPU, int8)...")
        _whisper_model = WhisperModel(model_size, device="cpu", compute_type="int8")
        _whisper_model_size = model_size
        logger.info("Whisper model loaded")

    segments, info = _whisper_model.transcribe(audio_path, beam_size=5)
    logger.info(
        f"Detected language: {info.language} "
        f"(probability {info.language_probability:.2f})"
    )

    text_parts = []
    for segment in segments:
        text_parts.append(segment.text.strip())

    return " ".join(text_parts)


def generate_executive_summary(
    transcription: str,
    meeting_title: str,
    api_key: str,
    model: str = "claude-sonnet-4-5-20250929",
) -> str:
    """Generate an executive summary of a council meeting using Claude."""
    client = anthropic.Anthropic(api_key=api_key)

    # Truncate to fit context — a 3-hour meeting is ~30K words ≈ 40K tokens
    max_chars = 400_000
    truncated = transcription[:max_chars]

    response = client.messages.create(
        model=model,
        max_tokens=2000,
        system=(
            "You are a municipal government assistant. Generate a concise executive "
            "summary of this City of Vernon council meeting transcription. Include:\n"
            "1. **Meeting Overview** (2-3 sentences)\n"
            "2. **Key Topics Discussed** (bulleted list)\n"
            "3. **Decisions Made** (motions passed/failed)\n"
            "4. **Notable Public Comments** (if any)\n\n"
            "Be factual and concise. Use professional government language."
        ),
        messages=[
            {
                "role": "user",
                "content": f"Meeting: {meeting_title}\n\nTranscription:\n{truncated}",
            }
        ],
    )
    return response.content[0].text.strip()


def extract_action_items(
    transcription: str,
    meeting_title: str,
    api_key: str,
    model: str = "claude-sonnet-4-5-20250929",
) -> list[dict]:
    """Extract action items, motions, and directives from a council meeting."""
    client = anthropic.Anthropic(api_key=api_key)

    max_chars = 400_000
    truncated = transcription[:max_chars]

    response = client.messages.create(
        model=model,
        max_tokens=2000,
        system=(
            "You are a municipal government assistant. Extract all action items, "
            "motions, and directives from this council meeting transcription.\n\n"
            "For each item provide a JSON object with:\n"
            '- "description": What needs to be done\n'
            '- "assigned_to": Who is responsible (e.g., "Staff", "Council", specific department)\n'
            '- "deadline": Any mentioned deadline or timeline (null if none)\n'
            '- "motion_number": Formal motion number if stated (null if none)\n'
            '- "status": "passed", "failed", "tabled", "referred", or "pending"\n\n'
            "Return ONLY a valid JSON array. If no items found, return []."
        ),
        messages=[
            {
                "role": "user",
                "content": f"Meeting: {meeting_title}\n\nTranscription:\n{truncated}",
            }
        ],
    )

    raw = response.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Failed to parse action items JSON, wrapping raw text")
        return [{"description": raw, "assigned_to": None, "deadline": None, "status": "unknown"}]


def download_meeting_pdf(url: str, timeout: int = 60) -> str | None:
    """Download a PDF from a URL and extract its text content.

    Returns the extracted text, or None if download/parsing fails.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.error("pypdf is not installed")
        return None

    try:
        session = requests.Session()
        session.verify = False  # eScribe portal has SSL cert issues
        resp = session.get(url, timeout=timeout)
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"Failed to download PDF from {url}: {e}")
        return None

    try:
        reader = PdfReader(io.BytesIO(resp.content))
    except Exception as e:
        logger.warning(f"Failed to parse PDF from {url}: {e}")
        return None

    text_parts = []
    for page in reader.pages:
        try:
            page_text = page.extract_text()
            if page_text and page_text.strip():
                text_parts.append(page_text.strip())
        except Exception:
            pass

    if not text_parts:
        logger.warning(f"No text extracted from PDF at {url}")
        return None

    return "\n\n".join(text_parts)
