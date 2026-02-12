"""Background worker for council meeting processing."""

import json
import logging
import os
import tempfile
import threading
from datetime import datetime, timezone

from app.chunker import chunk_text
from app.config import get_settings
from app.council_meetings import (
    download_audio,
    download_meeting_pdf,
    extract_action_items,
    generate_executive_summary,
    transcribe_audio,
)
from app.council_scraper import EScribeScraper

logger = logging.getLogger(__name__)

# Global processing state (mirrors crawl_in_progress pattern in main.py)
meeting_processing_active = False
meeting_processing_status: dict = {
    "is_running": False,
    "current_meeting": None,
    "total_meetings": 0,
    "processed": 0,
    "failed": 0,
    "current_step": None,
    "started_at": None,
    "errors": [],
}
_processing_lock = threading.Lock()


def get_processing_status() -> dict:
    """Return current processing status (thread-safe)."""
    with _processing_lock:
        return dict(meeting_processing_status)


def process_all_meetings(db_session_factory, vector_store, whisper_model: str = "small"):
    """Process all unprocessed council meetings in a background thread."""
    global meeting_processing_active

    if meeting_processing_active:
        logger.warning("Meeting processing already in progress")
        return

    def _worker():
        global meeting_processing_active
        meeting_processing_active = True
        with _processing_lock:
            meeting_processing_status.update({
                "is_running": True,
                "current_step": "discovering",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "processed": 0,
                "failed": 0,
                "errors": [],
                "current_meeting": None,
                "total_meetings": 0,
            })
        try:
            _run_full_processing(db_session_factory, vector_store, whisper_model)
        except Exception as e:
            logger.error(f"Meeting processing failed: {e}")
            with _processing_lock:
                meeting_processing_status["errors"].append(str(e)[:300])
        finally:
            meeting_processing_active = False
            with _processing_lock:
                meeting_processing_status["is_running"] = False
                meeting_processing_status["current_step"] = None
                meeting_processing_status["current_meeting"] = None

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


def process_single_meeting(
    meeting_id: int, db_session_factory, vector_store, whisper_model: str = "small"
):
    """Process a single meeting by database ID in a background thread."""
    global meeting_processing_active

    if meeting_processing_active:
        logger.warning("Meeting processing already in progress")
        return

    def _worker():
        global meeting_processing_active
        meeting_processing_active = True
        with _processing_lock:
            meeting_processing_status.update({
                "is_running": True,
                "current_step": "starting",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "processed": 0,
                "failed": 0,
                "errors": [],
                "total_meetings": 1,
                "current_meeting": None,
            })
        try:
            settings = get_settings()
            _process_one_meeting(
                meeting_id, db_session_factory, vector_store, whisper_model, settings
            )
        except Exception as e:
            logger.error(f"Single meeting processing failed: {e}")
            with _processing_lock:
                meeting_processing_status["errors"].append(str(e)[:300])
        finally:
            meeting_processing_active = False
            with _processing_lock:
                meeting_processing_status["is_running"] = False
                meeting_processing_status["current_step"] = None
                meeting_processing_status["current_meeting"] = None

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


def _run_full_processing(db_session_factory, vector_store, whisper_model: str):
    """Discover meetings, upsert to DB, then process all pending."""
    from app.database import CouncilMeeting

    settings = get_settings()

    # Step 1: Discover meetings
    scraper = EScribeScraper(portal_url=settings.escribe_portal_url)
    discovered = scraper.discover_meetings()

    with _processing_lock:
        meeting_processing_status["total_meetings"] = len(discovered)

    # Step 2: Upsert to database
    db = db_session_factory()
    try:
        for m_data in discovered:
            existing = (
                db.query(CouncilMeeting)
                .filter_by(escribe_id=m_data.escribe_id)
                .first()
            )
            if not existing:
                meeting = CouncilMeeting(
                    escribe_id=m_data.escribe_id,
                    title=m_data.title,
                    meeting_type=m_data.meeting_type,
                    meeting_date=m_data.meeting_date,
                    video_url=m_data.video_url,
                    agenda_url=m_data.agenda_url,
                    minutes_url=m_data.minutes_url,
                    status="pending",
                )
                db.add(meeting)
        db.commit()

        # Get all pending meetings (video, PDF, or both)
        pending = (
            db.query(CouncilMeeting)
            .filter(CouncilMeeting.status.in_(["pending", "error"]))
            .order_by(CouncilMeeting.meeting_date.desc())
            .all()
        )
        meeting_ids = [m.id for m in pending]
    finally:
        db.close()

    with _processing_lock:
        meeting_processing_status["total_meetings"] = len(meeting_ids)

    # Step 3: Process each meeting
    for mid in meeting_ids:
        if not meeting_processing_active:
            break  # Allow graceful stop
        _process_one_meeting(mid, db_session_factory, vector_store, whisper_model, settings)


def _process_one_meeting(
    meeting_id: int,
    db_session_factory,
    vector_store,
    whisper_model: str,
    settings,
):
    """Process a single meeting through the full pipeline.

    Handles three cases:
    - Video meetings: download audio -> transcribe -> summarize -> index + ingest PDFs
    - PDF-only meetings: download agenda/minutes PDFs -> summarize from minutes -> index
    - No content: skip (mark complete with no data)
    """
    from app.database import CouncilMeeting

    db = db_session_factory()
    audio_path = None
    try:
        meeting = db.query(CouncilMeeting).get(meeting_id)
        if not meeting:
            return

        has_video = bool(meeting.video_url)
        has_agenda = bool(meeting.agenda_url)
        has_minutes = bool(meeting.minutes_url)

        if not has_video and not has_agenda and not has_minutes:
            meeting.status = "complete"
            meeting.processing_completed_at = datetime.now(timezone.utc)
            db.commit()
            with _processing_lock:
                meeting_processing_status["processed"] += 1
            return

        with _processing_lock:
            meeting_processing_status["current_meeting"] = meeting.title

        meeting.status = "downloading"
        meeting.processing_started_at = datetime.now(timezone.utc)
        meeting.error_message = None
        db.commit()

        try:
            date_label = meeting.meeting_date.strftime('%Y-%m-%d') if meeting.meeting_date else 'unknown date'
            source_url = f"council-meeting://{meeting.escribe_id}"
            all_chunks = []

            # --- Step 1: Download and parse agenda/minutes PDFs ---
            with _processing_lock:
                meeting_processing_status["current_step"] = "downloading_docs"

            if has_agenda:
                logger.info(f"Downloading agenda PDF for {meeting.title}")
                agenda_text = download_meeting_pdf(meeting.agenda_url)
                if agenda_text:
                    meeting.agenda_text = agenda_text
                    agenda_chunks = chunk_text(
                        text=agenda_text,
                        source_url=f"{source_url}/agenda",
                        title=f"Agenda: {meeting.title} ({date_label})",
                        chunk_size=settings.chunk_size,
                        chunk_overlap=settings.chunk_overlap,
                    )
                    all_chunks.extend(agenda_chunks)
                    logger.info(f"Agenda: {len(agenda_chunks)} chunks from {meeting.title}")

            if has_minutes:
                logger.info(f"Downloading minutes PDF for {meeting.title}")
                minutes_text = download_meeting_pdf(meeting.minutes_url)
                if minutes_text:
                    meeting.minutes_text = minutes_text
                    minutes_chunks = chunk_text(
                        text=minutes_text,
                        source_url=f"{source_url}/minutes",
                        title=f"Minutes: {meeting.title} ({date_label})",
                        chunk_size=settings.chunk_size,
                        chunk_overlap=settings.chunk_overlap,
                    )
                    all_chunks.extend(minutes_chunks)
                    logger.info(f"Minutes: {len(minutes_chunks)} chunks from {meeting.title}")

            db.commit()

            # --- Step 2: Video processing (if available) ---
            if has_video:
                with _processing_lock:
                    meeting_processing_status["current_step"] = "downloading"

                fd, audio_path = tempfile.mkstemp(suffix=".wav")
                os.close(fd)

                scraper = EScribeScraper(portal_url=settings.escribe_portal_url)
                hls_url = scraper.get_hls_url(meeting.video_url)
                if not hls_url:
                    raise ValueError(
                        f"Could not determine HLS URL from {meeting.video_url}"
                    )

                success = download_audio(hls_url, audio_path)
                if not success:
                    raise RuntimeError("ffmpeg audio download failed")

                # Transcribe
                meeting.status = "transcribing"
                db.commit()
                with _processing_lock:
                    meeting_processing_status["current_step"] = "transcribing"

                transcription = transcribe_audio(audio_path, model_size=whisper_model)
                meeting.transcription = transcription

                # Index transcription
                transcription_chunks = chunk_text(
                    text=transcription,
                    source_url=f"{source_url}/transcription",
                    title=f"Council Meeting Transcription: {meeting.title} ({date_label})",
                    chunk_size=settings.chunk_size,
                    chunk_overlap=settings.chunk_overlap,
                )
                all_chunks.extend(transcription_chunks)

            # --- Step 3: Summarize ---
            # Use transcription if available, otherwise use minutes text
            summary_source = meeting.transcription or meeting.minutes_text
            if summary_source and settings.anthropic_api_key:
                meeting.status = "summarizing"
                db.commit()
                with _processing_lock:
                    meeting_processing_status["current_step"] = "summarizing"

                meeting.executive_summary = generate_executive_summary(
                    summary_source,
                    meeting.title,
                    api_key=settings.anthropic_api_key,
                    model=settings.claude_model,
                )

                action_items = extract_action_items(
                    summary_source,
                    meeting.title,
                    api_key=settings.anthropic_api_key,
                    model=settings.claude_model,
                )
                meeting.action_items_json = json.dumps(action_items)

            # --- Step 4: Index all chunks in ChromaDB ---
            meeting.status = "indexing"
            db.commit()
            with _processing_lock:
                meeting_processing_status["current_step"] = "indexing"

            if all_chunks:
                vector_store.ingest(all_chunks)
                logger.info(f"Indexed {len(all_chunks)} total chunks for {meeting.title}")

            # Mark complete
            meeting.status = "complete"
            meeting.processing_completed_at = datetime.now(timezone.utc)
            db.commit()

            with _processing_lock:
                meeting_processing_status["processed"] += 1

            logger.info(f"Successfully processed: {meeting.title}")

        except Exception as e:
            meeting.status = "error"
            meeting.error_message = str(e)[:500]
            db.commit()

            with _processing_lock:
                meeting_processing_status["failed"] += 1
                meeting_processing_status["errors"].append(
                    f"{meeting.title}: {str(e)[:200]}"
                )

            logger.error(f"Failed to process meeting {meeting.title}: {e}")

        finally:
            # Always clean up temp audio file
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)

    finally:
        db.close()
