import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.config import get_settings
from app.scraper import WebScraper
from app.chunker import chunk_text
from app.vectorstore import VectorStore
from app.rag import RAGPipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state
vector_store: VectorStore | None = None
rag_pipeline: RAGPipeline | None = None
last_crawl_time: str | None = None
crawl_in_progress = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global vector_store, rag_pipeline
    settings = get_settings()

    vector_store = VectorStore(
        persist_dir=settings.chroma_path,
        embedding_model=settings.embedding_model,
    )

    if settings.anthropic_api_key:
        rag_pipeline = RAGPipeline(
            vector_store=vector_store,
            api_key=settings.anthropic_api_key,
            model=settings.claude_model,
        )

    logger.info("Vernon Chatbot backend started")
    yield
    logger.info("Vernon Chatbot backend shutting down")


app = FastAPI(title="Vernon Chatbot API", version="1.0.0", lifespan=lifespan)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request/Response Models ---

class ChatRequest(BaseModel):
    message: str
    stream: bool = True


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]


class IngestRequest(BaseModel):
    url: str | None = None


class IngestResponse(BaseModel):
    pages_crawled: int
    chunks_stored: int
    message: str


# --- Endpoints ---

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "vernon-chatbot"}


@app.get("/api/status")
async def status():
    return {
        "knowledge_base_chunks": vector_store.count() if vector_store else 0,
        "last_crawl_time": last_crawl_time,
        "crawl_in_progress": crawl_in_progress,
        "llm_configured": rag_pipeline is not None,
    }


@app.post("/api/ingest", response_model=IngestResponse)
async def ingest(request: IngestRequest | None = None):
    global last_crawl_time, crawl_in_progress

    if crawl_in_progress:
        raise HTTPException(status_code=409, detail="A crawl is already in progress")

    settings = get_settings()
    target_url = (request.url if request and request.url else None) or settings.target_url

    if not target_url:
        raise HTTPException(
            status_code=400,
            detail="No target URL provided. Set TARGET_URL env var or pass url in request body.",
        )

    crawl_in_progress = True
    try:
        # Clear existing data
        vector_store.clear()

        # Crawl website
        scraper = WebScraper(
            base_url=target_url,
            max_pages=settings.max_crawl_pages,
            max_depth=settings.max_crawl_depth,
        )
        pages = scraper.crawl()

        if not pages:
            raise HTTPException(status_code=400, detail=f"No content found at {target_url}")

        # Chunk and ingest
        all_chunks = []
        for page in pages:
            chunks = chunk_text(
                text=page.content,
                source_url=page.url,
                title=page.title,
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
            )
            all_chunks.extend(chunks)

        num_stored = vector_store.ingest(all_chunks)
        last_crawl_time = datetime.now(timezone.utc).isoformat()

        return IngestResponse(
            pages_crawled=len(pages),
            chunks_stored=num_stored,
            message=f"Successfully ingested {len(pages)} pages ({num_stored} chunks) from {target_url}",
        )
    finally:
        crawl_in_progress = False


@app.post("/api/chat")
async def chat(request: ChatRequest):
    if not rag_pipeline:
        raise HTTPException(
            status_code=503,
            detail="LLM not configured. Set ANTHROPIC_API_KEY environment variable.",
        )

    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    if request.stream:
        return EventSourceResponse(stream_chat(request.message))

    result = rag_pipeline.query(request.message, top_k=get_settings().top_k_results)
    return ChatResponse(answer=result.answer, sources=result.sources)


async def stream_chat(message: str):
    """Generator for SSE streaming responses."""
    settings = get_settings()
    sources = []

    # Get sources first
    matches = rag_pipeline.vector_store.query(message, top_k=settings.top_k_results)
    seen = set()
    for m in matches:
        if m["source_url"] not in seen:
            seen.add(m["source_url"])
            sources.append({"url": m["source_url"], "title": m["title"]})

    # Stream the answer
    async for token in rag_pipeline.stream(message, top_k=settings.top_k_results):
        yield {"event": "token", "data": json.dumps({"token": token})}

    # Send sources at the end
    yield {"event": "sources", "data": json.dumps({"sources": sources})}
    yield {"event": "done", "data": json.dumps({"status": "complete"})}
