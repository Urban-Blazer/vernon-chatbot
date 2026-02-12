import logging
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class ScrapedPage:
    url: str
    title: str
    content: str


@dataclass
class WebScraper:
    base_url: str
    max_pages: int = 50
    max_depth: int = 3
    delay: float = 1.0
    visited: set = field(default_factory=set)
    pages: list[ScrapedPage] = field(default_factory=list)

    def _is_same_domain(self, url: str) -> bool:
        return urlparse(url).netloc == urlparse(self.base_url).netloc

    def _normalize_url(self, url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")

    def _extract_text(self, soup: BeautifulSoup) -> str:
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]):
            tag.decompose()

        main_content = soup.find("main") or soup.find("article") or soup.find("body")
        if not main_content:
            return ""

        lines = []
        for element in main_content.stripped_strings:
            line = element.strip()
            if line:
                lines.append(line)

        return "\n".join(lines)

    def _extract_links(self, soup: BeautifulSoup, current_url: str) -> list[str]:
        links = []
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            full_url = urljoin(current_url, href)
            full_url = self._normalize_url(full_url)

            if not full_url.startswith(("http://", "https://")):
                continue
            if not self._is_same_domain(full_url):
                continue
            if full_url.endswith((".pdf", ".jpg", ".png", ".gif", ".zip", ".mp4", ".mp3")):
                continue
            if "#" in full_url:
                full_url = full_url.split("#")[0]

            links.append(full_url)
        return links

    def crawl(self) -> list[ScrapedPage]:
        queue: list[tuple[str, int]] = [(self._normalize_url(self.base_url), 0)]
        self.visited = set()
        self.pages = []

        while queue and len(self.pages) < self.max_pages:
            url, depth = queue.pop(0)

            if url in self.visited or depth > self.max_depth:
                continue

            self.visited.add(url)
            logger.info(f"Crawling: {url} (depth={depth})")

            try:
                response = requests.get(
                    url,
                    timeout=10,
                    headers={"User-Agent": "VernonChatbot/1.0 (customer-service-bot)"},
                )
                response.raise_for_status()

                if "text/html" not in response.headers.get("content-type", ""):
                    continue

                soup = BeautifulSoup(response.text, "html.parser")
                title = soup.title.string.strip() if soup.title and soup.title.string else url
                content = self._extract_text(soup)

                if content and len(content) > 50:
                    self.pages.append(ScrapedPage(url=url, title=title, content=content))
                    logger.info(f"  Extracted {len(content)} chars from {url}")

                if depth < self.max_depth:
                    links = self._extract_links(soup, url)
                    for link in links:
                        if link not in self.visited:
                            queue.append((link, depth + 1))

                time.sleep(self.delay)

            except requests.RequestException as e:
                logger.warning(f"  Failed to crawl {url}: {e}")
                continue

        logger.info(f"Crawling complete. Scraped {len(self.pages)} pages.")
        return self.pages
