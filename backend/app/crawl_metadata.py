"""Persists URL → content_hash mappings between crawls for incremental updates."""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

METADATA_FILENAME = "crawl_metadata.json"


@dataclass
class CrawlRecord:
    content_hash: str
    title: str
    last_crawled: str


@dataclass
class CrawlMetadataStore:
    storage_dir: str
    records: dict[str, CrawlRecord] = field(default_factory=dict)  # url → CrawlRecord

    def __post_init__(self):
        self._load()

    @property
    def _filepath(self) -> str:
        return os.path.join(self.storage_dir, METADATA_FILENAME)

    def _load(self):
        """Load metadata from disk."""
        if not os.path.exists(self._filepath):
            self.records = {}
            return

        try:
            with open(self._filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.records = {
                url: CrawlRecord(**rec) for url, rec in data.items()
            }
            logger.info(f"Loaded crawl metadata for {len(self.records)} URLs")
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load crawl metadata, starting fresh: {e}")
            self.records = {}

    def save(self):
        """Persist metadata to disk."""
        os.makedirs(self.storage_dir, exist_ok=True)
        data = {
            url: {
                "content_hash": rec.content_hash,
                "title": rec.title,
                "last_crawled": rec.last_crawled,
            }
            for url, rec in self.records.items()
        }
        with open(self._filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved crawl metadata for {len(self.records)} URLs")

    def get_hash(self, url: str) -> str | None:
        """Get the stored content hash for a URL, or None if never crawled."""
        rec = self.records.get(url)
        return rec.content_hash if rec else None

    def update(self, url: str, content_hash: str, title: str):
        """Update the stored record for a URL."""
        self.records[url] = CrawlRecord(
            content_hash=content_hash,
            title=title,
            last_crawled=datetime.now(timezone.utc).isoformat(),
        )

    def remove(self, url: str):
        """Remove a URL from the metadata."""
        self.records.pop(url, None)

    def get_all_urls(self) -> set[str]:
        """Get all URLs currently tracked."""
        return set(self.records.keys())

    def clear(self):
        """Remove all metadata."""
        self.records = {}
        if os.path.exists(self._filepath):
            os.remove(self._filepath)
        logger.info("Crawl metadata cleared")
