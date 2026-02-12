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
