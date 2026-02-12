from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    target_url: str = "https://vernon.ca"
    chroma_path: str = "./chroma_data"

    # Crawl settings — tuned for large municipal sites
    max_crawl_pages: int = 2000
    max_crawl_depth: int = 10
    crawl_delay: float = 0.3
    crawl_concurrency: int = 10
    crawl_timeout: int = 15
    use_sitemap: bool = True

    # URL patterns to skip (regex-compatible strings)
    # News archive is bulk content with low customer-service value
    exclude_patterns: list[str] = [
        "/news-archive/",
        "/news-events/news-archive/",
    ]
    # Set to True to include news archive pages (adds ~1100 pages)
    include_news_archive: bool = False

    # Chunking
    chunk_size: int = 400
    chunk_overlap: int = 50

    # AI
    embedding_model: str = "all-MiniLM-L6-v2"
    claude_model: str = "claude-sonnet-4-5-20250929"
    top_k_results: int = 5

    # Server
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
