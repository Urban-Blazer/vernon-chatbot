import hashlib
import logging

from cachetools import TTLCache

logger = logging.getLogger(__name__)


class ResponseCache:
    def __init__(self, maxsize: int = 500, ttl: int = 3600):
        self._cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)

    def _key(self, question: str) -> str:
        normalized = question.strip().lower()
        return hashlib.md5(normalized.encode()).hexdigest()

    def get(self, question: str) -> dict | None:
        result = self._cache.get(self._key(question))
        if result:
            logger.debug(f"Cache hit for: {question[:50]}...")
        return result

    def put(self, question: str, answer: str, sources: list[dict], confidence: float):
        self._cache[self._key(question)] = {
            "answer": answer,
            "sources": sources,
            "confidence": confidence,
        }

    def invalidate(self):
        self._cache.clear()
        logger.info("Response cache invalidated")

    @property
    def size(self) -> int:
        return len(self._cache)
