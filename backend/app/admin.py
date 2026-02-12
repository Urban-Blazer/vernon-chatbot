import logging

from fastapi import APIRouter, Depends, HTTPException, Header, Query

from app.analytics import AnalyticsService
from app.config import get_settings

logger = logging.getLogger(__name__)

admin_router = APIRouter(prefix="/api/admin", tags=["admin"])


async def verify_admin_key(x_admin_key: str = Header(...)):
    settings = get_settings()
    if not settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Admin API key not configured")
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Invalid admin key")


def _get_analytics() -> AnalyticsService:
    # Import here to avoid circular imports
    from app.main import db_session_factory
    db = db_session_factory()
    return AnalyticsService(db)


@admin_router.get("/analytics/summary", dependencies=[Depends(verify_admin_key)])
async def analytics_summary(days: int = Query(default=30, ge=1, le=365)):
    analytics = _get_analytics()
    try:
        return analytics.get_summary(days=days)
    finally:
        analytics.db.close()


@admin_router.get("/analytics/top-questions", dependencies=[Depends(verify_admin_key)])
async def top_questions(
    limit: int = Query(default=10, ge=1, le=100),
    days: int = Query(default=30, ge=1, le=365),
):
    analytics = _get_analytics()
    try:
        return analytics.get_top_questions(limit=limit, days=days)
    finally:
        analytics.db.close()


@admin_router.get("/analytics/unanswered", dependencies=[Depends(verify_admin_key)])
async def unanswered_questions(days: int = Query(default=30, ge=1, le=365)):
    analytics = _get_analytics()
    settings = get_settings()
    try:
        return analytics.get_unanswered_questions(
            confidence_threshold=settings.confidence_threshold, days=days
        )
    finally:
        analytics.db.close()


@admin_router.get("/analytics/feedback", dependencies=[Depends(verify_admin_key)])
async def feedback_details(days: int = Query(default=30, ge=1, le=365)):
    analytics = _get_analytics()
    try:
        return analytics.get_feedback_details(days=days)
    finally:
        analytics.db.close()


@admin_router.get("/analytics/hourly", dependencies=[Depends(verify_admin_key)])
async def hourly_distribution(days: int = Query(default=7, ge=1, le=90)):
    analytics = _get_analytics()
    try:
        return analytics.get_hourly_distribution(days=days)
    finally:
        analytics.db.close()


@admin_router.get("/conversations", dependencies=[Depends(verify_admin_key)])
async def list_conversations(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
):
    from app.main import db_session_factory
    from app.database import ChatSession, ConversationMessage
    from sqlalchemy import func

    db = db_session_factory()
    try:
        total = db.query(func.count(ChatSession.id)).scalar() or 0

        sessions = (
            db.query(ChatSession)
            .order_by(ChatSession.last_active.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        result = []
        for session in sessions:
            msg_count = (
                db.query(func.count(ConversationMessage.id))
                .filter_by(session_id=session.id)
                .scalar() or 0
            )
            last_msg = (
                db.query(ConversationMessage)
                .filter_by(session_id=session.id, role="user")
                .order_by(ConversationMessage.created_at.desc())
                .first()
            )
            result.append({
                "session_id": session.id,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "last_active": session.last_active.isoformat() if session.last_active else None,
                "language": session.language,
                "message_count": msg_count,
                "last_question": last_msg.content[:100] if last_msg else None,
            })

        return {"total": total, "page": page, "per_page": per_page, "conversations": result}
    finally:
        db.close()


@admin_router.get("/conversations/{session_id}", dependencies=[Depends(verify_admin_key)])
async def get_conversation(session_id: str):
    from app.main import db_session_factory
    from app.database import ChatSession, ConversationMessage, Feedback
    import json

    db = db_session_factory()
    try:
        session = db.query(ChatSession).filter_by(id=session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        messages = (
            db.query(ConversationMessage)
            .filter_by(session_id=session_id)
            .order_by(ConversationMessage.created_at)
            .all()
        )

        return {
            "session_id": session.id,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "language": session.language,
            "messages": [
                {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "sources": json.loads(msg.sources_json) if msg.sources_json else None,
                    "confidence": msg.confidence,
                    "response_time_ms": msg.response_time_ms,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                    "feedback": (
                        {"rating": msg.feedback.rating, "comment": msg.feedback.comment}
                        if msg.feedback else None
                    ),
                }
                for msg in messages
            ],
        }
    finally:
        db.close()


@admin_router.get("/crawl-status", dependencies=[Depends(verify_admin_key)])
async def crawl_status():
    from app.main import vector_store, crawl_metadata, last_crawl_time, crawl_in_progress, response_cache

    return {
        "knowledge_base_chunks": vector_store.count() if vector_store else 0,
        "tracked_pages": len(crawl_metadata.records) if crawl_metadata else 0,
        "cache_size": response_cache.size if response_cache else 0,
        "last_crawl_time": last_crawl_time,
        "crawl_in_progress": crawl_in_progress,
    }


@admin_router.post("/crawl/trigger", dependencies=[Depends(verify_admin_key)])
async def trigger_crawl(full: bool = False):
    from app.main import crawl_in_progress

    if crawl_in_progress:
        raise HTTPException(status_code=409, detail="Crawl already in progress")

    # Reuse the ingest logic by importing the function
    from app.main import _build_scraper, _full_ingest, _incremental_ingest
    from app.main import crawl_metadata, response_cache
    import app.main as main_module

    settings = get_settings()
    main_module.crawl_in_progress = True
    try:
        scraper = _build_scraper(settings.target_url)
        pages = scraper.crawl()
        if not pages:
            raise HTTPException(status_code=400, detail="No content found")

        if full or not crawl_metadata.records:
            result = _full_ingest(pages, settings, settings.target_url)
        else:
            result = _incremental_ingest(pages, settings, settings.target_url)

        if response_cache:
            response_cache.invalidate()

        return result
    finally:
        main_module.crawl_in_progress = False


@admin_router.post("/cache/clear", dependencies=[Depends(verify_admin_key)])
async def clear_cache():
    from app.main import response_cache

    if response_cache:
        response_cache.invalidate()
        return {"status": "ok", "message": "Cache cleared"}
    return {"status": "ok", "message": "No cache to clear"}


# --- Audit log endpoints ---

@admin_router.get("/audit-logs", dependencies=[Depends(verify_admin_key)])
async def get_audit_logs(
    days: int = Query(default=30, ge=1, le=365),
    action: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=100),
):
    from app.main import db_session_factory
    from app.database import AuditLog
    from sqlalchemy import func
    from datetime import datetime, timezone, timedelta
    import json

    db = db_session_factory()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        query = db.query(AuditLog).filter(AuditLog.timestamp >= cutoff)
        if action:
            query = query.filter(AuditLog.action == action)

        total = query.count()
        logs = (
            query.order_by(AuditLog.timestamp.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        return {
            "total": total,
            "page": page,
            "logs": [
                {
                    "id": log.id,
                    "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                    "action": log.action,
                    "session_id": log.session_id,
                    "user_input": log.user_input,
                    "retrieved_chunks": json.loads(log.retrieved_chunks) if log.retrieved_chunks else None,
                    "response_preview": log.response_preview,
                    "confidence": log.confidence,
                    "topic": log.topic,
                    "metadata": json.loads(log.metadata_json) if log.metadata_json else None,
                }
                for log in logs
            ],
        }
    finally:
        db.close()


# --- Topic analytics ---

@admin_router.get("/analytics/topics", dependencies=[Depends(verify_admin_key)])
async def topic_distribution(days: int = Query(default=30, ge=1, le=365)):
    from app.main import db_session_factory
    from app.database import AnalyticsEvent
    from datetime import datetime, timezone, timedelta
    from app.topic_router import get_topic_label
    import json

    db = db_session_factory()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        events = (
            db.query(AnalyticsEvent)
            .filter(
                AnalyticsEvent.created_at >= cutoff,
                AnalyticsEvent.event_type == "chat",
            )
            .all()
        )

        topic_counts: dict[str, int] = {}
        for event in events:
            if event.data_json:
                data = json.loads(event.data_json)
                topic = data.get("topic", "general")
                topic_counts[topic] = topic_counts.get(topic, 0) + 1

        return [
            {"topic": t, "count": c, "label": get_topic_label(t)}
            for t, c in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
        ]
    finally:
        db.close()


# --- Document management ---

@admin_router.get("/documents", dependencies=[Depends(verify_admin_key)])
async def list_documents():
    from app.main import crawl_metadata

    docs = []
    if crawl_metadata:
        for url, record in crawl_metadata.records.items():
            if url.startswith("pdf://"):
                docs.append({
                    "url": url,
                    "filename": url.replace("pdf://", ""),
                    "title": record.title,
                    "last_crawled": record.last_crawled,
                })
    return docs


@admin_router.delete("/documents/{filename}", dependencies=[Depends(verify_admin_key)])
async def delete_document(filename: str):
    from app.main import vector_store, crawl_metadata, response_cache

    url = f"pdf://{filename}"
    if not crawl_metadata or url not in crawl_metadata.records:
        raise HTTPException(status_code=404, detail="Document not found")

    deleted = vector_store.delete_by_url(url) if vector_store else 0
    crawl_metadata.remove(url)
    crawl_metadata.save()

    if response_cache:
        response_cache.invalidate()

    return {"status": "ok", "chunks_removed": deleted}


# --- Council meeting endpoints ---

@admin_router.get("/meetings", dependencies=[Depends(verify_admin_key)])
async def list_meetings(
    status: str | None = Query(default=None),
    meeting_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
):
    from app.main import db_session_factory
    from app.database import CouncilMeeting

    db = db_session_factory()
    try:
        query = db.query(CouncilMeeting)
        if status:
            query = query.filter(CouncilMeeting.status == status)
        if meeting_type:
            query = query.filter(CouncilMeeting.meeting_type == meeting_type)

        total = query.count()
        meetings = (
            query.order_by(CouncilMeeting.meeting_date.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "meetings": [
                {
                    "id": m.id,
                    "escribe_id": m.escribe_id,
                    "title": m.title,
                    "meeting_type": m.meeting_type,
                    "meeting_date": m.meeting_date.isoformat() if m.meeting_date else None,
                    "status": m.status,
                    "has_video": bool(m.video_url),
                    "has_transcription": bool(m.transcription),
                    "has_summary": bool(m.executive_summary),
                    "error_message": m.error_message,
                    "processing_started_at": m.processing_started_at.isoformat() if m.processing_started_at else None,
                    "processing_completed_at": m.processing_completed_at.isoformat() if m.processing_completed_at else None,
                }
                for m in meetings
            ],
        }
    finally:
        db.close()


@admin_router.get("/meetings/processing-status", dependencies=[Depends(verify_admin_key)])
async def meeting_processing_status():
    from app.meeting_worker import get_processing_status
    return get_processing_status()


@admin_router.get("/meetings/{meeting_id}", dependencies=[Depends(verify_admin_key)])
async def get_meeting_detail(meeting_id: int):
    from app.main import db_session_factory
    from app.database import CouncilMeeting
    import json

    db = db_session_factory()
    try:
        meeting = db.query(CouncilMeeting).get(meeting_id)
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")

        return {
            "id": meeting.id,
            "escribe_id": meeting.escribe_id,
            "title": meeting.title,
            "meeting_type": meeting.meeting_type,
            "meeting_date": meeting.meeting_date.isoformat() if meeting.meeting_date else None,
            "video_url": meeting.video_url,
            "status": meeting.status,
            "executive_summary": meeting.executive_summary,
            "action_items": json.loads(meeting.action_items_json) if meeting.action_items_json else None,
            "transcription_preview": meeting.transcription[:2000] if meeting.transcription else None,
            "transcription_length": len(meeting.transcription) if meeting.transcription else 0,
            "error_message": meeting.error_message,
            "processing_started_at": meeting.processing_started_at.isoformat() if meeting.processing_started_at else None,
            "processing_completed_at": meeting.processing_completed_at.isoformat() if meeting.processing_completed_at else None,
        }
    finally:
        db.close()


@admin_router.post("/meetings/discover", dependencies=[Depends(verify_admin_key)])
async def discover_meetings():
    from app.main import db_session_factory
    from app.database import CouncilMeeting
    from app.council_scraper import EScribeScraper
    from app.audit import log_audit

    settings = get_settings()
    scraper = EScribeScraper(portal_url=settings.escribe_portal_url)
    discovered = scraper.discover_meetings()

    db = db_session_factory()
    try:
        added = 0
        for m_data in discovered:
            existing = db.query(CouncilMeeting).filter_by(escribe_id=m_data.escribe_id).first()
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
                added += 1
        db.commit()

        log_audit(db, "meetings_discovered", metadata={
            "total_discovered": len(discovered),
            "new_added": added,
            "with_video": sum(1 for m in discovered if m.video_url),
        })

        return {
            "total_discovered": len(discovered),
            "new_added": added,
            "with_video": sum(1 for m in discovered if m.video_url),
        }
    finally:
        db.close()


@admin_router.post("/meetings/process-all", dependencies=[Depends(verify_admin_key)])
async def trigger_process_all_meetings():
    from app.meeting_worker import meeting_processing_active, process_all_meetings
    from app.main import db_session_factory, vector_store

    if meeting_processing_active:
        raise HTTPException(status_code=409, detail="Meeting processing already in progress")

    settings = get_settings()
    process_all_meetings(
        db_session_factory=db_session_factory,
        vector_store=vector_store,
        whisper_model=settings.whisper_model_size,
    )
    return {"status": "started", "message": "Meeting processing started in background"}


@admin_router.post("/meetings/{meeting_id}/process", dependencies=[Depends(verify_admin_key)])
async def trigger_process_single_meeting(meeting_id: int):
    from app.meeting_worker import meeting_processing_active, process_single_meeting
    from app.main import db_session_factory, vector_store

    if meeting_processing_active:
        raise HTTPException(status_code=409, detail="Meeting processing already in progress")

    settings = get_settings()
    process_single_meeting(
        meeting_id=meeting_id,
        db_session_factory=db_session_factory,
        vector_store=vector_store,
        whisper_model=settings.whisper_model_size,
    )
    return {"status": "started", "message": f"Processing meeting {meeting_id}"}
