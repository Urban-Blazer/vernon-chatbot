from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    target_url: str = "https://vernon.ca"
    chroma_path: str = "./chroma_data"

    # Database
    database_url: str = "sqlite:///./vernon_chatbot.db"

    # Crawl settings — tuned for large municipal sites
    max_crawl_pages: int = 2000
    max_crawl_depth: int = 10
    crawl_delay: float = 0.3
    crawl_concurrency: int = 10
    crawl_timeout: int = 15
    use_sitemap: bool = True

    # URL patterns to skip (regex-compatible strings)
    exclude_patterns: list[str] = [
        "/news-archive/",
        "/news-events/news-archive/",
    ]
    include_news_archive: bool = True

    # Chunking
    chunk_size: int = 400
    chunk_overlap: int = 50

    # AI
    embedding_model: str = "all-MiniLM-L6-v2"
    claude_model: str = "claude-sonnet-4-5-20250929"
    top_k_results: int = 5

    # Rate limiting
    rate_limit: str = "30/minute"
    rate_limit_chat: str = "10/minute"

    # Privacy & data retention
    data_retention_days: int = 90
    max_message_length: int = 2000

    # Bilingual
    default_language: str = "en"

    # Caching
    cache_ttl_seconds: int = 3600
    cache_max_size: int = 500

    # Scheduled recrawl
    recrawl_enabled: bool = False
    recrawl_cron_hour: int = 2
    recrawl_cron_minute: int = 0

    # Admin
    admin_api_key: str = ""

    # Confidence
    confidence_threshold: float = 0.65

    # Human handoff
    handoff_email: str = ""
    handoff_phone: str = ""
    handoff_url: str = "https://www.vernon.ca/contact-us"
    handoff_summary_enabled: bool = True

    # PDF ingestion
    ingest_pdfs: bool = True

    # Topic routing
    topic_routing_enabled: bool = True

    # Council meeting transcription
    council_meetings_enabled: bool = True
    whisper_model_size: str = "small"
    escribe_portal_url: str = "https://pub-vernon.escribemeetings.com"

    # Server
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
