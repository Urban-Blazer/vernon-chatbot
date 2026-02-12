import json
import logging
from datetime import datetime, timezone

from sqlalchemy import (
    Column, DateTime, Float, ForeignKey, Integer, String, Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

logger = logging.getLogger(__name__)

Base = declarative_base()


class ChatSession(Base):
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_active = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    language = Column(String(5), default="en")
    messages = relationship(
        "ConversationMessage", back_populates="session", cascade="all, delete-orphan"
    )


class ConversationMessage(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("sessions.id"), index=True)
    role = Column(String(10))  # "user" or "assistant"
    content = Column(Text)
    sources_json = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    session = relationship("ChatSession", back_populates="messages")
    feedback = relationship("Feedback", back_populates="message", uselist=False)


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, ForeignKey("messages.id"), unique=True)
    rating = Column(Integer)  # 1 = thumbs up, -1 = thumbs down
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    message = relationship("ConversationMessage", back_populates="feedback")


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(50), index=True)
    session_id = Column(String(36), nullable=True)
    data_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    action = Column(String(50), index=True)
    session_id = Column(String(36), nullable=True)
    user_input = Column(Text, nullable=True)
    retrieved_chunks = Column(Text, nullable=True)  # JSON array
    response_preview = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    topic = Column(String(50), nullable=True)
    metadata_json = Column(Text, nullable=True)


class CouncilMeeting(Base):
    __tablename__ = "council_meetings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    escribe_id = Column(String(100), unique=True, index=True)
    title = Column(String(500))
    meeting_type = Column(String(100))
    meeting_date = Column(DateTime, index=True)
    video_url = Column(Text, nullable=True)
    agenda_url = Column(Text, nullable=True)
    minutes_url = Column(Text, nullable=True)
    transcription = Column(Text, nullable=True)
    agenda_text = Column(Text, nullable=True)
    minutes_text = Column(Text, nullable=True)
    executive_summary = Column(Text, nullable=True)
    action_items_json = Column(Text, nullable=True)
    status = Column(String(20), default="pending", index=True)
    error_message = Column(Text, nullable=True)
    processing_started_at = Column(DateTime, nullable=True)
    processing_completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def init_db(database_url: str):
    """Create engine, tables, and return a session factory."""
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False} if "sqlite" in database_url else {},
    )
    Base.metadata.create_all(engine)
    logger.info("Database initialized")
    return sessionmaker(bind=engine)
