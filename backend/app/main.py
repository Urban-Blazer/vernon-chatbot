import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.config import get_settings
from app.crawl_metadata import CrawlMetadataStore
from app.scraper import WebScraper
from app.chunker import chunk_text
from app.vectorstore import VectorStore
from app.rag import RAGPipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state
vector_store: VectorStore | None = None
rag_pipeline: RAGPipeline | None = None
crawl_metadata: CrawlMetadataStore | None = None
last_crawl_time: str | None = None
crawl_in_progress = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global vector_store, rag_pipeline, crawl_metadata
    settings = get_settings()

    vector_store = VectorStore(
        persist_dir=settings.chroma_path,
        embedding_model=settings.embedding_model,
    )

    crawl_metadata = CrawlMetadataStore(storage_dir=settings.chroma_path)

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
    full: bool = False  # True = full re-crawl, False = incremental


class IngestResponse(BaseModel):
    pages_crawled: int
    chunks_stored: int
    pages_added: int
    pages_updated: int
    pages_removed: int
    pages_unchanged: int
    message: str


# --- Helpers ---

def _build_scraper(target_url: str) -> WebScraper:
    settings = get_settings()
    exclude = settings.exclude_patterns if not settings.include_news_archive else []
    return WebScraper(
        base_url=target_url,
        max_pages=settings.max_crawl_pages,
        max_depth=settings.max_crawl_depth,
        delay=settings.crawl_delay,
        concurrency=settings.crawl_concurrency,
        timeout=settings.crawl_timeout,
        use_sitemap=settings.use_sitemap,
        exclude_patterns=exclude,
    )


def _chunk_and_ingest(pages, settings) -> int:
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
    return vector_store.ingest(all_chunks) if all_chunks else 0


# --- Endpoints ---

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "vernon-chatbot"}


@app.get("/api/status")
async def status():
    return {
        "knowledge_base_chunks": vector_store.count() if vector_store else 0,
        "tracked_pages": len(crawl_metadata.records) if crawl_metadata else 0,
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

    is_full = request.full if request else False
    # If no metadata exists yet, force a full crawl
    if not crawl_metadata.records:
        is_full = True

    crawl_in_progress = True
    try:
        scraper = _build_scraper(target_url)
        pages = scraper.crawl()

        if not pages:
            raise HTTPException(status_code=400, detail=f"No content found at {target_url}")

        if is_full:
            return _full_ingest(pages, settings, target_url)
        else:
            return _incremental_ingest(pages, settings, target_url)
    finally:
        crawl_in_progress = False


def _full_ingest(pages, settings, target_url: str) -> IngestResponse:
    """Clear everything and re-ingest from scratch."""
    global last_crawl_time

    vector_store.clear()
    crawl_metadata.clear()

    num_stored = _chunk_and_ingest(pages, settings)

    # Update metadata for all pages
    for page in pages:
        crawl_metadata.update(page.url, page.content_hash, page.title)
    crawl_metadata.save()

    last_crawl_time = datetime.now(timezone.utc).isoformat()

    return IngestResponse(
        pages_crawled=len(pages),
        chunks_stored=num_stored,
        pages_added=len(pages),
        pages_updated=0,
        pages_removed=0,
        pages_unchanged=0,
        message=f"Full ingest: {len(pages)} pages ({num_stored} chunks) from {target_url}",
    )


def _incremental_ingest(pages, settings, target_url: str) -> IngestResponse:
    """Only update pages that changed, add new ones, remove deleted ones."""
    global last_crawl_time

    crawled_urls = {page.url for page in pages}
    previously_known = crawl_metadata.get_all_urls()

    added = []
    updated = []
    unchanged = []

    for page in pages:
        old_hash = crawl_metadata.get_hash(page.url)

        if old_hash is None:
            # New page
            added.append(page)
        elif old_hash != page.content_hash:
            # Content changed
            updated.append(page)
        else:
            # No change
            unchanged.append(page)

    # Pages that were in the DB but are no longer on the site
    removed_urls = previously_known - crawled_urls

    # 1. Remove deleted pages from vector store + metadata
    if removed_urls:
        vector_store.delete_by_urls(list(removed_urls))
        for url in removed_urls:
            crawl_metadata.remove(url)
        logger.info(f"Removed {len(removed_urls)} deleted pages")

    # 2. Remove old chunks for updated pages, then re-ingest
    if updated:
        vector_store.delete_by_urls([p.url for p in updated])
        _chunk_and_ingest(updated, settings)
        for page in updated:
            crawl_metadata.update(page.url, page.content_hash, page.title)
        logger.info(f"Updated {len(updated)} changed pages")

    # 3. Ingest new pages
    if added:
        _chunk_and_ingest(added, settings)
        for page in added:
            crawl_metadata.update(page.url, page.content_hash, page.title)
        logger.info(f"Added {len(added)} new pages")

    crawl_metadata.save()
    last_crawl_time = datetime.now(timezone.utc).isoformat()

    total_modified = len(added) + len(updated)
    chunks_stored = vector_store.count()

    return IngestResponse(
        pages_crawled=len(pages),
        chunks_stored=chunks_stored,
        pages_added=len(added),
        pages_updated=len(updated),
        pages_removed=len(removed_urls),
        pages_unchanged=len(unchanged),
        message=(
            f"Incremental update: {len(added)} added, {len(updated)} updated, "
            f"{len(removed_urls)} removed, {len(unchanged)} unchanged. "
            f"Total chunks: {chunks_stored}"
        ),
    )


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
