import json
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from app.database import AnalyticsEvent, ChatSession, ConversationMessage, Feedback

logger = logging.getLogger(__name__)


class AnalyticsService:
    def __init__(self, db: DBSession):
        self.db = db

    def get_summary(self, days: int = 30) -> dict:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        total_sessions = (
            self.db.query(func.count(ChatSession.id))
            .filter(ChatSession.created_at >= cutoff)
            .scalar() or 0
        )
        total_messages = (
            self.db.query(func.count(ConversationMessage.id))
            .filter(
                ConversationMessage.created_at >= cutoff,
                ConversationMessage.role == "user",
            )
            .scalar() or 0
        )
        avg_response_time = (
            self.db.query(func.avg(ConversationMessage.response_time_ms))
            .filter(
                ConversationMessage.created_at >= cutoff,
                ConversationMessage.role == "assistant",
                ConversationMessage.response_time_ms.isnot(None),
            )
            .scalar()
        )
        avg_confidence = (
            self.db.query(func.avg(ConversationMessage.confidence))
            .filter(
                ConversationMessage.created_at >= cutoff,
                ConversationMessage.role == "assistant",
                ConversationMessage.confidence.isnot(None),
            )
            .scalar()
        )

        # Feedback stats
        positive = (
            self.db.query(func.count(Feedback.id))
            .filter(Feedback.created_at >= cutoff, Feedback.rating == 1)
            .scalar() or 0
        )
        negative = (
            self.db.query(func.count(Feedback.id))
            .filter(Feedback.created_at >= cutoff, Feedback.rating == -1)
            .scalar() or 0
        )
        total_feedback = positive + negative
        satisfaction_rate = round(positive / total_feedback * 100, 1) if total_feedback > 0 else None

        # Handoff count
        handoff_count = (
            self.db.query(func.count(AnalyticsEvent.id))
            .filter(
                AnalyticsEvent.created_at >= cutoff,
                AnalyticsEvent.event_type == "chat",
            )
            .scalar() or 0
        )

        return {
            "period_days": days,
            "total_sessions": total_sessions,
            "total_questions": total_messages,
            "avg_response_time_ms": round(avg_response_time) if avg_response_time else None,
            "avg_confidence": round(avg_confidence, 2) if avg_confidence else None,
            "feedback_positive": positive,
            "feedback_negative": negative,
            "satisfaction_rate": satisfaction_rate,
        }

    def get_top_questions(self, limit: int = 10, days: int = 30) -> list[dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        results = (
            self.db.query(
                ConversationMessage.content,
                func.count(ConversationMessage.id).label("count"),
            )
            .filter(
                ConversationMessage.created_at >= cutoff,
                ConversationMessage.role == "user",
            )
            .group_by(ConversationMessage.content)
            .order_by(func.count(ConversationMessage.id).desc())
            .limit(limit)
            .all()
        )

        return [{"question": r[0], "count": r[1]} for r in results]

    def get_unanswered_questions(self, confidence_threshold: float = 0.65, days: int = 30) -> list[dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # Find assistant messages with low confidence
        low_conf_msgs = (
            self.db.query(ConversationMessage)
            .filter(
                ConversationMessage.created_at >= cutoff,
                ConversationMessage.role == "assistant",
                ConversationMessage.confidence < confidence_threshold,
                ConversationMessage.confidence.isnot(None),
            )
            .order_by(ConversationMessage.created_at.desc())
            .limit(50)
            .all()
        )

        results = []
        for msg in low_conf_msgs:
            # Find the preceding user message
            user_msg = (
                self.db.query(ConversationMessage)
                .filter(
                    ConversationMessage.session_id == msg.session_id,
                    ConversationMessage.role == "user",
                    ConversationMessage.created_at < msg.created_at,
                )
                .order_by(ConversationMessage.created_at.desc())
                .first()
            )
            if user_msg:
                results.append({
                    "question": user_msg.content,
                    "confidence": msg.confidence,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                    "session_id": msg.session_id,
                })

        return results

    def get_feedback_details(self, days: int = 30) -> list[dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        results = (
            self.db.query(Feedback, ConversationMessage)
            .join(ConversationMessage, Feedback.message_id == ConversationMessage.id)
            .filter(Feedback.created_at >= cutoff)
            .order_by(Feedback.created_at.desc())
            .limit(50)
            .all()
        )

        return [
            {
                "rating": fb.rating,
                "comment": fb.comment,
                "answer": msg.content[:200],
                "confidence": msg.confidence,
                "created_at": fb.created_at.isoformat() if fb.created_at else None,
                "session_id": msg.session_id,
            }
            for fb, msg in results
        ]

    def get_hourly_distribution(self, days: int = 7) -> list[dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        results = (
            self.db.query(
                func.strftime("%H", ConversationMessage.created_at).label("hour"),
                func.count(ConversationMessage.id).label("count"),
            )
            .filter(
                ConversationMessage.created_at >= cutoff,
                ConversationMessage.role == "user",
            )
            .group_by("hour")
            .order_by("hour")
            .all()
        )

        # Fill in all 24 hours
        hour_map = {r[0]: r[1] for r in results}
        return [
            {"hour": f"{h:02d}:00", "count": hour_map.get(f"{h:02d}", 0)}
            for h in range(24)
        ]
