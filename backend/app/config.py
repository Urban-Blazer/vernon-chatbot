from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    target_url: str = ""
    chroma_path: str = "./chroma_data"
    max_crawl_pages: int = 50
    max_crawl_depth: int = 3
    chunk_size: int = 400
    chunk_overlap: int = 50
    embedding_model: str = "all-MiniLM-L6-v2"
    claude_model: str = "claude-sonnet-4-5-20250929"
    top_k_results: int = 5
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
