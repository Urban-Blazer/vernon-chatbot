import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import delete
from app.database import ChatSession

logger = logging.getLogger(__name__)


def purge_old_sessions(session_factory, retention_days: int):
    """Delete sessions and their messages older than retention_days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    db = session_factory()
    try:
        result = db.execute(
            delete(ChatSession).where(ChatSession.last_active < cutoff)
        )
        db.commit()
        count = result.rowcount
        if count > 0:
            logger.info(f"Purged {count} sessions older than {retention_days} days")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to purge old sessions: {e}")
    finally:
        db.close()
