"""Audit logging service for government accountability."""

import json
import logging
from datetime import datetime, timezone

from app.database import AuditLog

logger = logging.getLogger(__name__)


def log_audit(
    db,
    action: str,
    session_id: str | None = None,
    user_input: str | None = None,
    retrieved_chunks: list[dict] | None = None,
    response_preview: str | None = None,
    confidence: float | None = None,
    topic: str | None = None,
    metadata: dict | None = None,
):
    """Write an audit log entry.

    Actions: chat_query, crawl_started, crawl_completed, document_uploaded,
             admin_action, feedback_received, cache_cleared
    """
    try:
        entry = AuditLog(
            action=action,
            session_id=session_id,
            user_input=user_input,
            retrieved_chunks=json.dumps(retrieved_chunks) if retrieved_chunks else None,
            response_preview=response_preview[:500] if response_preview else None,
            confidence=confidence,
            topic=topic,
            metadata_json=json.dumps(metadata) if metadata else None,
        )
        db.add(entry)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"Failed to write audit log: {e}")
