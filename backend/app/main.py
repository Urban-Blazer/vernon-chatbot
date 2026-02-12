import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sse_starlette.sse import EventSourceResponse

from fastapi import Depends, File, Header, UploadFile

from app.audit import log_audit
from app.cache import ResponseCache
from app.config import get_settings
from app.crawl_metadata import CrawlMetadataStore
from app.database import (
    AuditLog, AnalyticsEvent, ChatSession, CouncilMeeting, ConversationMessage, Feedback, init_db,
)
from app.chunker import chunk_text
from app.pdf_parser import parse_pdf
from app.rag import (
    RAGPipeline, extract_confidence, extract_handoff, retrieval_confidence,
    _deduplicate_sources,
)
from app.retention import purge_old_sessions
from app.sanitizer import sanitize_input
from app.scraper import WebScraper
from app.topic_router import classify_topic, get_prompt_addition
from app.vectorstore import VectorStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Global state ---
vector_store: VectorStore | None = None
rag_pipeline: RAGPipeline | None = None
crawl_metadata: CrawlMetadataStore | None = None
response_cache: ResponseCache | None = None
db_session_factory = None
scheduler: BackgroundScheduler | None = None
last_crawl_time: str | None = None
crawl_in_progress = False


# --- Lifespan ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    global vector_store, rag_pipeline, crawl_metadata, response_cache
    global db_session_factory, scheduler
    settings = get_settings()

    # Vector store
    vector_store = VectorStore(
        persist_dir=settings.chroma_path,
        embedding_model=settings.embedding_model,
    )

    # Crawl metadata
    crawl_metadata = CrawlMetadataStore(storage_dir=settings.chroma_path)

    # Database
    db_session_factory = init_db(settings.database_url)

    # Response cache
    response_cache = ResponseCache(
        maxsize=settings.cache_max_size,
        ttl=settings.cache_ttl_seconds,
    )

    # RAG pipeline
    if settings.anthropic_api_key:
        rag_pipeline = RAGPipeline(
            vector_store=vector_store,
            api_key=settings.anthropic_api_key,
            model=settings.claude_model,
        )

    # Scheduler
    scheduler = BackgroundScheduler()

    # Auto-recrawl
    if settings.recrawl_enabled and settings.target_url:
        scheduler.add_job(
            _scheduled_recrawl,
            CronTrigger(hour=settings.recrawl_cron_hour, minute=settings.recrawl_cron_minute),
            id="auto_recrawl",
            replace_existing=True,
        )
        logger.info(f"Auto-recrawl scheduled at {settings.recrawl_cron_hour:02d}:{settings.recrawl_cron_minute:02d}")

    # Data retention purge (daily at 3 AM)
    scheduler.add_job(
        purge_old_sessions,
        CronTrigger(hour=3, minute=0),
        args=[db_session_factory, settings.data_retention_days],
        id="data_retention",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Vernon Chatbot backend started")
    yield

    scheduler.shutdown(wait=False)
    logger.info("Vernon Chatbot backend shutting down")


# --- App setup ---

app = FastAPI(title="Vernon Chatbot API", version="2.0.0", lifespan=lifespan)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Admin router
from app.admin import admin_router
app.include_router(admin_router)


# --- Request/Response Models ---

class ChatRequest(BaseModel):
    message: str
    stream: bool = True
    session_id: str | None = None
    language: str = "en"


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]
    session_id: str
    message_id: int | None = None
    confidence: float = 0.5
    handoff_needed: bool = False


class IngestRequest(BaseModel):
    url: str | None = None
    full: bool = False


class IngestResponse(BaseModel):
    pages_crawled: int
    chunks_stored: int
    pages_added: int
    pages_updated: int
    pages_removed: int
    pages_unchanged: int
    message: str


class FeedbackRequest(BaseModel):
    message_id: int
    rating: int  # 1 or -1
    comment: str | None = None


class SessionMessagesResponse(BaseModel):
    session_id: str
    messages: list[dict]


# --- Helpers ---

def _build_scraper(target_url: str) -> WebScraper:
    s = get_settings()
    exclude = s.exclude_patterns if not s.include_news_archive else []
    return WebScraper(
        base_url=target_url,
        max_pages=s.max_crawl_pages,
        max_depth=s.max_crawl_depth,
        delay=s.crawl_delay,
        concurrency=s.crawl_concurrency,
        timeout=s.crawl_timeout,
        use_sitemap=s.use_sitemap,
        ingest_pdfs=s.ingest_pdfs,
        exclude_patterns=exclude,
    )


def _chunk_and_ingest(pages, s) -> int:
    all_chunks = []
    for page in pages:
        chunks = chunk_text(
            text=page.content,
            source_url=page.url,
            title=page.title,
            chunk_size=s.chunk_size,
            chunk_overlap=s.chunk_overlap,
        )
        all_chunks.extend(chunks)
    return vector_store.ingest(all_chunks) if all_chunks else 0


def _get_or_create_session(session_id: str | None, language: str) -> str:
    """Return existing session ID or create a new one."""
    db = db_session_factory()
    try:
        if session_id:
            existing = db.query(ChatSession).filter_by(id=session_id).first()
            if existing:
                existing.last_active = datetime.now(timezone.utc)
                existing.language = language
                db.commit()
                return session_id

        new_id = str(uuid.uuid4())
        session = ChatSession(id=new_id, language=language)
        db.add(session)
        db.commit()
        return new_id
    finally:
        db.close()


def _save_message(session_id: str, role: str, content: str,
                   sources: list[dict] | None = None, confidence: float | None = None,
                   response_time_ms: int | None = None) -> int:
    """Save a message to the database, return its ID."""
    db = db_session_factory()
    try:
        msg = ConversationMessage(
            session_id=session_id,
            role=role,
            content=content,
            sources_json=json.dumps(sources) if sources else None,
            confidence=confidence,
            response_time_ms=response_time_ms,
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        return msg.id
    finally:
        db.close()


def _log_analytics(event_type: str, session_id: str | None = None, data: dict | None = None):
    """Log an analytics event."""
    db = db_session_factory()
    try:
        event = AnalyticsEvent(
            event_type=event_type,
            session_id=session_id,
            data_json=json.dumps(data) if data else None,
        )
        db.add(event)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"Failed to log analytics: {e}")
    finally:
        db.close()


def _scheduled_recrawl():
    """Background job: incremental recrawl."""
    global last_crawl_time, crawl_in_progress
    if crawl_in_progress:
        logger.info("Skipping scheduled recrawl — already in progress")
        return

    crawl_in_progress = True
    try:
        s = get_settings()
        scraper = _build_scraper(s.target_url)
        pages = scraper.crawl()
        if pages:
            _incremental_ingest(pages, s, s.target_url)
            response_cache.invalidate()
        logger.info(f"Scheduled recrawl complete: {len(pages)} pages")
    except Exception as e:
        logger.error(f"Scheduled recrawl failed: {e}")
    finally:
        crawl_in_progress = False


# --- SUGGESTIONS ---

SUGGESTIONS = {
    "en": [
        {"text": "Pay property taxes", "query": "How do I pay my property taxes?"},
        {"text": "Recreation programs", "query": "What recreation programs are available?"},
        {"text": "Report a concern", "query": "How do I report a concern or issue?"},
        {"text": "Waste collection", "query": "What is the waste collection schedule?"},
        {"text": "Building permits", "query": "How do I apply for a building permit?"},
        {"text": "Water & utilities", "query": "How do I set up water and utility services?"},
    ],
    "fr": [
        {"text": "Payer les taxes", "query": "Comment payer mes taxes fonci\u00e8res ?"},
        {"text": "Programmes de loisirs", "query": "Quels programmes de loisirs sont disponibles ?"},
        {"text": "Signaler un probl\u00e8me", "query": "Comment signaler un probl\u00e8me ?"},
        {"text": "Collecte des d\u00e9chets", "query": "Quel est le calendrier de collecte des d\u00e9chets ?"},
        {"text": "Permis de construire", "query": "Comment demander un permis de construire ?"},
        {"text": "Eau et services", "query": "Comment configurer les services d'eau et de services publics ?"},
    ],
}


# --- Endpoints ---

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "vernon-chatbot", "version": "2.0.0"}


@app.get("/api/status")
async def status():
    return {
        "knowledge_base_chunks": vector_store.count() if vector_store else 0,
        "tracked_pages": len(crawl_metadata.records) if crawl_metadata else 0,
        "cache_size": response_cache.size if response_cache else 0,
        "last_crawl_time": last_crawl_time,
        "crawl_in_progress": crawl_in_progress,
        "llm_configured": rag_pipeline is not None,
    }


@app.get("/api/suggestions")
async def get_suggestions(language: str = "en"):
    return SUGGESTIONS.get(language, SUGGESTIONS["en"])


@app.post("/api/sessions")
@limiter.limit("30/minute")
async def create_session(request: Request, language: str = "en"):
    session_id = _get_or_create_session(None, language)
    return {"session_id": session_id}


@app.get("/api/sessions/{session_id}/messages")
@limiter.limit("30/minute")
async def get_session_messages(request: Request, session_id: str):
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
            "session_id": session_id,
            "messages": [
                {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "sources": json.loads(msg.sources_json) if msg.sources_json else None,
                    "confidence": msg.confidence,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                }
                for msg in messages
            ],
        }
    finally:
        db.close()


@app.post("/api/feedback")
@limiter.limit("30/minute")
async def submit_feedback(request: Request, req: FeedbackRequest):
    if req.rating not in (1, -1):
        raise HTTPException(status_code=400, detail="Rating must be 1 or -1")

    db = db_session_factory()
    try:
        msg = db.query(ConversationMessage).filter_by(id=req.message_id).first()
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")

        existing = db.query(Feedback).filter_by(message_id=req.message_id).first()
        if existing:
            existing.rating = req.rating
            existing.comment = req.comment
        else:
            fb = Feedback(
                message_id=req.message_id,
                rating=req.rating,
                comment=req.comment,
            )
            db.add(fb)

        db.commit()

        _log_analytics("feedback", msg.session_id, {
            "message_id": req.message_id,
            "rating": req.rating,
        })

        return {"status": "ok"}
    finally:
        db.close()


@app.post("/api/chat")
@limiter.limit(settings.rate_limit_chat)
async def chat(request: Request, chat_req: ChatRequest):
    if not rag_pipeline:
        raise HTTPException(
            status_code=503,
            detail="LLM not configured. Set ANTHROPIC_API_KEY environment variable.",
        )

    # Sanitize input
    cleaned, was_filtered = sanitize_input(chat_req.message, settings.max_message_length)
    if was_filtered:
        raise HTTPException(status_code=400, detail="Message was filtered for safety. Please rephrase your question.")

    # Topic routing
    s = get_settings()
    topic = classify_topic(cleaned) if s.topic_routing_enabled else "general"

    # Get or create session
    session_id = _get_or_create_session(chat_req.session_id, chat_req.language)

    # Save user message
    _save_message(session_id, "user", cleaned)

    # Check cache
    cached = response_cache.get(cleaned) if response_cache else None
    if cached and not chat_req.stream:
        msg_id = _save_message(
            session_id, "assistant", cached["answer"],
            sources=cached["sources"], confidence=cached["confidence"],
        )
        return ChatResponse(
            answer=cached["answer"],
            sources=cached["sources"],
            session_id=session_id,
            message_id=msg_id,
            confidence=cached["confidence"],
        )

    if chat_req.stream:
        return EventSourceResponse(
            stream_chat(cleaned, session_id, chat_req.language, topic)
        )

    # Non-streaming
    start = time.time()
    result = rag_pipeline.query(cleaned, top_k=s.top_k_results, language=chat_req.language, topic=topic)
    elapsed_ms = int((time.time() - start) * 1000)

    msg_id = _save_message(
        session_id, "assistant", result.answer,
        sources=result.sources, confidence=result.confidence,
        response_time_ms=elapsed_ms,
    )

    # Cache the response
    if response_cache:
        response_cache.put(cleaned, result.answer, result.sources, result.confidence)

    _log_analytics("chat", session_id, {
        "confidence": result.confidence,
        "response_time_ms": elapsed_ms,
        "handoff": result.handoff_needed,
        "topic": topic,
    })

    # Audit log
    db = db_session_factory()
    try:
        matches = rag_pipeline.vector_store.query(cleaned, top_k=s.top_k_results)
        log_audit(db, "chat_query", session_id=session_id, user_input=cleaned,
                  retrieved_chunks=[{"title": m.get("title",""), "url": m.get("source_url",""), "distance": m.get("distance",0)} for m in matches],
                  response_preview=result.answer[:200], confidence=result.confidence, topic=topic)
    finally:
        db.close()

    return ChatResponse(
        answer=result.answer,
        sources=result.sources,
        session_id=session_id,
        message_id=msg_id,
        confidence=result.confidence,
        handoff_needed=result.handoff_needed,
    )


async def stream_chat(message: str, session_id: str, language: str, topic: str = "general"):
    """Generator for SSE streaming responses."""
    s = get_settings()
    accumulated = ""

    # Get matches for sources, confidence, and audit
    matches = rag_pipeline.vector_store.query(message, top_k=s.top_k_results)
    sources = _deduplicate_sources(matches)
    ret_conf = retrieval_confidence(matches)

    start = time.time()

    # Stream the answer
    async for token in rag_pipeline.stream(message, top_k=s.top_k_results, language=language, topic=topic):
        accumulated += token
        yield {"event": "token", "data": json.dumps({"token": token})}

    elapsed_ms = int((time.time() - start) * 1000)

    # Process markers from accumulated text
    clean_text, confidence = extract_confidence(accumulated)
    clean_text, handoff_needed = extract_handoff(clean_text)
    final_confidence = round((confidence * 0.6) + (ret_conf * 0.4), 2)

    # Save to database
    msg_id = _save_message(
        session_id, "assistant", clean_text,
        sources=sources, confidence=final_confidence,
        response_time_ms=elapsed_ms,
    )

    # Cache
    if response_cache:
        response_cache.put(message, clean_text, sources, final_confidence)

    # Log analytics
    _log_analytics("chat", session_id, {
        "confidence": final_confidence,
        "response_time_ms": elapsed_ms,
        "handoff": handoff_needed,
        "topic": topic,
    })

    # Audit log
    db = db_session_factory()
    try:
        log_audit(db, "chat_query", session_id=session_id, user_input=message,
                  retrieved_chunks=[{"title": m.get("title",""), "url": m.get("source_url",""), "distance": m.get("distance",0)} for m in matches],
                  response_preview=clean_text[:200], confidence=final_confidence, topic=topic)
    finally:
        db.close()

    # Emit metadata events
    yield {"event": "sources", "data": json.dumps({"sources": sources})}
    yield {"event": "confidence", "data": json.dumps({"confidence": final_confidence})}

    need_handoff = handoff_needed or final_confidence < s.confidence_threshold
    if need_handoff:
        handoff_data = {
            "email": s.handoff_email,
            "phone": s.handoff_phone,
            "url": s.handoff_url,
        }
        # Generate conversation summary for staff
        if s.handoff_summary_enabled:
            try:
                db = db_session_factory()
                try:
                    msgs = (
                        db.query(ConversationMessage)
                        .filter_by(session_id=session_id)
                        .order_by(ConversationMessage.created_at)
                        .all()
                    )
                    msg_list = [{"role": m.role, "content": m.content} for m in msgs]
                    summary = rag_pipeline.summarize_conversation(msg_list)
                    handoff_data["summary"] = summary
                finally:
                    db.close()
            except Exception as e:
                logger.warning(f"Failed to generate handoff summary: {e}")

        yield {"event": "handoff", "data": json.dumps(handoff_data)}

    yield {"event": "done", "data": json.dumps({
        "status": "complete",
        "session_id": session_id,
        "message_id": msg_id,
        "topic": topic,
    })}


# --- Document upload ---

async def _verify_admin_key(x_admin_key: str = Header(...)):
    s = get_settings()
    if not s.admin_api_key or x_admin_key != s.admin_api_key:
        raise HTTPException(status_code=403, detail="Invalid admin key")


@app.post("/api/ingest/documents")
@limiter.limit("5/hour")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    x_admin_key: str = Header(...),
):
    await _verify_admin_key(x_admin_key)

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    contents = await file.read()
    if len(contents) > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")

    page = parse_pdf(contents, filename=file.filename)
    if not page:
        raise HTTPException(status_code=400, detail="Could not extract text from PDF")

    s = get_settings()
    chunks = chunk_text(
        text=page.content,
        source_url=page.url,
        title=page.title,
        chunk_size=s.chunk_size,
        chunk_overlap=s.chunk_overlap,
    )
    num_stored = vector_store.ingest(chunks) if chunks else 0

    # Track in metadata
    crawl_metadata.update(page.url, page.content_hash, page.title)
    crawl_metadata.save()

    # Invalidate cache
    if response_cache:
        response_cache.invalidate()

    # Audit log
    db = db_session_factory()
    try:
        log_audit(db, "document_uploaded", metadata={
            "filename": file.filename,
            "title": page.title,
            "chunks_stored": num_stored,
            "content_length": len(page.content),
        })
    finally:
        db.close()

    return {
        "status": "ok",
        "filename": file.filename,
        "title": page.title,
        "chunks_stored": num_stored,
        "content_length": len(page.content),
    }


# --- Ingest endpoints ---

@app.post("/api/ingest", response_model=IngestResponse)
@limiter.limit("2/hour")
async def ingest(request: Request, ingest_req: IngestRequest | None = None):
    global last_crawl_time, crawl_in_progress

    if crawl_in_progress:
        raise HTTPException(status_code=409, detail="A crawl is already in progress")

    s = get_settings()
    target_url = (ingest_req.url if ingest_req and ingest_req.url else None) or s.target_url

    if not target_url:
        raise HTTPException(status_code=400, detail="No target URL provided.")

    is_full = ingest_req.full if ingest_req else False
    if not crawl_metadata.records:
        is_full = True

    crawl_in_progress = True
    try:
        scraper = _build_scraper(target_url)
        pages = scraper.crawl()

        if not pages:
            raise HTTPException(status_code=400, detail=f"No content found at {target_url}")

        if is_full:
            result = _full_ingest(pages, s, target_url)
        else:
            result = _incremental_ingest(pages, s, target_url)

        # Invalidate response cache after ingest
        if response_cache:
            response_cache.invalidate()

        return result
    finally:
        crawl_in_progress = False


def _full_ingest(pages, s, target_url: str) -> IngestResponse:
    global last_crawl_time
    vector_store.clear()
    crawl_metadata.clear()

    num_stored = _chunk_and_ingest(pages, s)

    for page in pages:
        crawl_metadata.update(page.url, page.content_hash, page.title)
    crawl_metadata.save()

    last_crawl_time = datetime.now(timezone.utc).isoformat()

    return IngestResponse(
        pages_crawled=len(pages), chunks_stored=num_stored,
        pages_added=len(pages), pages_updated=0, pages_removed=0, pages_unchanged=0,
        message=f"Full ingest: {len(pages)} pages ({num_stored} chunks) from {target_url}",
    )


def _incremental_ingest(pages, s, target_url: str) -> IngestResponse:
    global last_crawl_time
    crawled_urls = {page.url for page in pages}
    previously_known = crawl_metadata.get_all_urls()

    added, updated, unchanged = [], [], []
    for page in pages:
        old_hash = crawl_metadata.get_hash(page.url)
        if old_hash is None:
            added.append(page)
        elif old_hash != page.content_hash:
            updated.append(page)
        else:
            unchanged.append(page)

    removed_urls = previously_known - crawled_urls

    if removed_urls:
        vector_store.delete_by_urls(list(removed_urls))
        for url in removed_urls:
            crawl_metadata.remove(url)

    if updated:
        vector_store.delete_by_urls([p.url for p in updated])
        _chunk_and_ingest(updated, s)
        for page in updated:
            crawl_metadata.update(page.url, page.content_hash, page.title)

    if added:
        _chunk_and_ingest(added, s)
        for page in added:
            crawl_metadata.update(page.url, page.content_hash, page.title)

    crawl_metadata.save()
    last_crawl_time = datetime.now(timezone.utc).isoformat()

    return IngestResponse(
        pages_crawled=len(pages), chunks_stored=vector_store.count(),
        pages_added=len(added), pages_updated=len(updated),
        pages_removed=len(removed_urls), pages_unchanged=len(unchanged),
        message=(
            f"Incremental: {len(added)} added, {len(updated)} updated, "
            f"{len(removed_urls)} removed, {len(unchanged)} unchanged"
        ),
    )
