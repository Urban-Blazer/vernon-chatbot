import hashlib
import logging
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


@dataclass
class ScrapedPage:
    url: str
    title: str
    content: str
    content_hash: str = ""

    def __post_init__(self):
        if not self.content_hash and self.content:
            self.content_hash = hashlib.sha256(self.content.encode()).hexdigest()


@dataclass
class CrawlProgress:
    total_urls: int = 0
    crawled: int = 0
    succeeded: int = 0
    skipped: int = 0
    failed: int = 0


@dataclass
class WebScraper:
    base_url: str
    max_pages: int = 2000
    max_depth: int = 10
    delay: float = 0.3
    concurrency: int = 10
    timeout: int = 15
    use_sitemap: bool = True
    ingest_pdfs: bool = True
    exclude_patterns: list[str] = field(default_factory=list)
    _session: requests.Session = field(default=None, init=False, repr=False)
    progress: CrawlProgress = field(default_factory=CrawlProgress)

    def __post_init__(self):
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "VernonChatbot/1.0 (customer-service-bot)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
        })

    def _normalize_url(self, url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")

    def _is_same_domain(self, url: str) -> bool:
        base_netloc = urlparse(self.base_url).netloc.replace("www.", "")
        url_netloc = urlparse(url).netloc.replace("www.", "")
        return base_netloc == url_netloc

    def _should_exclude(self, url: str) -> bool:
        for pattern in self.exclude_patterns:
            if re.search(pattern, url):
                return True
        return False

    def _extract_text(self, soup: BeautifulSoup) -> str:
        """Extract meaningful text content, stripping boilerplate."""
        for tag in soup(["script", "style", "nav", "footer", "header",
                         "aside", "form", "noscript", "iframe", "svg"]):
            tag.decompose()

        # Also remove common boilerplate classes/IDs
        for selector in [".breadcrumb", ".sidebar", ".menu", "#sidebar",
                         ".social-share", ".pagination", ".cookie-notice"]:
            for el in soup.select(selector):
                el.decompose()

        main_content = (
            soup.find("main")
            or soup.find("article")
            or soup.find(attrs={"role": "main"})
            or soup.find("div", class_=re.compile(r"content|main", re.I))
            or soup.find("body")
        )
        if not main_content:
            return ""

        lines = []
        for element in main_content.stripped_strings:
            line = element.strip()
            if line and len(line) > 2:
                lines.append(line)

        return "\n".join(lines)

    # --- Sitemap Discovery ---

    def _fetch_sitemap_urls(self) -> list[str]:
        """Discover all page URLs from the site's sitemap."""
        base = self._normalize_url(self.base_url)
        parsed = urlparse(base)
        sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"

        logger.info(f"Fetching sitemap: {sitemap_url}")
        urls = []

        try:
            resp = self._session.get(sitemap_url, timeout=self.timeout)
            resp.raise_for_status()
            urls = self._parse_sitemap(resp.text, depth=0)
        except requests.RequestException as e:
            logger.warning(f"Could not fetch sitemap: {e}")

        logger.info(f"Sitemap discovery found {len(urls)} URLs")
        return urls

    def _parse_sitemap(self, xml_text: str, depth: int) -> list[str]:
        """Parse a sitemap or sitemap index recursively."""
        if depth > 3:
            return []

        urls = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.warning(f"Failed to parse sitemap XML: {e}")
            return []

        # Check if this is a sitemap index
        for sitemap_el in root.findall("sm:sitemap", SITEMAP_NS):
            loc = sitemap_el.find("sm:loc", SITEMAP_NS)
            if loc is not None and loc.text:
                try:
                    resp = self._session.get(loc.text.strip(), timeout=self.timeout)
                    resp.raise_for_status()
                    urls.extend(self._parse_sitemap(resp.text, depth + 1))
                except requests.RequestException as e:
                    logger.warning(f"Failed to fetch child sitemap {loc.text}: {e}")

        # Parse URL entries
        for url_el in root.findall("sm:url", SITEMAP_NS):
            loc = url_el.find("sm:loc", SITEMAP_NS)
            if loc is not None and loc.text:
                urls.append(loc.text.strip())

        return urls

    # --- Page Fetching ---

    def _fetch_page(self, url: str) -> ScrapedPage | None:
        """Fetch and extract content from a single URL."""
        try:
            response = self._session.get(url, timeout=self.timeout)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type:
                return None

            soup = BeautifulSoup(response.text, "html.parser")
            title = soup.title.string.strip() if soup.title and soup.title.string else url
            content = self._extract_text(soup)

            if content and len(content) > 50:
                return ScrapedPage(url=url, title=title, content=content)

        except requests.RequestException as e:
            logger.debug(f"Failed to fetch {url}: {e}")
            self.progress.failed += 1

        return None

    def _fetch_pdf(self, url: str) -> ScrapedPage | None:
        """Download and parse a PDF URL."""
        try:
            from app.pdf_parser import parse_pdf_from_url
            response = self._session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return parse_pdf_from_url(response.content, url)
        except Exception as e:
            logger.debug(f"Failed to fetch PDF {url}: {e}")
            self.progress.failed += 1
            return None

    def _fetch_url(self, url: str) -> ScrapedPage | None:
        """Route to appropriate fetcher based on URL type."""
        if self.ingest_pdfs and url.lower().endswith(".pdf"):
            return self._fetch_pdf(url)
        return self._fetch_page(url)

    # --- Main Crawl Methods ---

    def crawl(self) -> list[ScrapedPage]:
        """Main entry point: uses sitemap if available, falls back to link-following."""
        if self.use_sitemap:
            sitemap_urls = self._fetch_sitemap_urls()
            if sitemap_urls:
                return self._crawl_from_urls(sitemap_urls)
            logger.info("No sitemap found, falling back to link-following crawl")

        return self._crawl_by_links()

    def _crawl_from_urls(self, urls: list[str]) -> list[ScrapedPage]:
        """Crawl a pre-discovered list of URLs concurrently."""
        # Filter and deduplicate
        filtered = []
        seen = set()
        for url in urls:
            normalized = self._normalize_url(url)
            if normalized in seen:
                continue
            seen.add(normalized)
            if self._should_exclude(url):
                self.progress.skipped += 1
                continue
            if not self._is_same_domain(url):
                continue
            filtered.append(url)

        # Respect max_pages limit
        if len(filtered) > self.max_pages:
            logger.info(f"Limiting crawl from {len(filtered)} to {self.max_pages} pages")
            filtered = filtered[:self.max_pages]

        self.progress.total_urls = len(filtered)
        logger.info(f"Crawling {len(filtered)} URLs ({self.progress.skipped} excluded) "
                     f"with concurrency={self.concurrency}")

        pages: list[ScrapedPage] = []

        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            future_to_url = {executor.submit(self._fetch_url, url): url for url in filtered}

            for future in as_completed(future_to_url):
                self.progress.crawled += 1
                page = future.result()
                if page:
                    pages.append(page)
                    self.progress.succeeded += 1

                if self.progress.crawled % 50 == 0:
                    logger.info(f"Progress: {self.progress.crawled}/{self.progress.total_urls} "
                                f"({self.progress.succeeded} succeeded, {self.progress.failed} failed)")

        logger.info(f"Crawling complete: {self.progress.succeeded} pages scraped "
                     f"from {self.progress.total_urls} URLs "
                     f"({self.progress.failed} failed, {self.progress.skipped} excluded)")

        return pages

    def _crawl_by_links(self) -> list[ScrapedPage]:
        """Fallback: BFS link-following crawler."""
        queue: list[tuple[str, int]] = [(self._normalize_url(self.base_url), 0)]
        visited: set[str] = set()
        pages: list[ScrapedPage] = []

        while queue and len(pages) < self.max_pages:
            url, depth = queue.pop(0)

            if url in visited or depth > self.max_depth:
                continue
            if self._should_exclude(url):
                continue

            visited.add(url)
            logger.info(f"Crawling: {url} (depth={depth})")

            page = self._fetch_url(url)
            if page:
                pages.append(page)

            # Discover links for BFS (skip for PDF pages)
            if url.lower().endswith(".pdf"):
                time.sleep(self.delay)
                continue

            try:
                response = self._session.get(url, timeout=self.timeout)
                if response.ok and "text/html" in response.headers.get("content-type", ""):
                    soup = BeautifulSoup(response.text, "html.parser")
                    skip_exts = (".jpg", ".png", ".gif", ".zip")
                    if not self.ingest_pdfs:
                        skip_exts = (".pdf",) + skip_exts
                    for a_tag in soup.find_all("a", href=True):
                        href = a_tag["href"]
                        full_url = self._normalize_url(urljoin(url, href))
                        if (full_url not in visited
                                and self._is_same_domain(full_url)
                                and not full_url.endswith(skip_exts)):
                            queue.append((full_url, depth + 1))
            except requests.RequestException:
                pass

            time.sleep(self.delay)

            if len(pages) % 50 == 0 and len(pages) > 0:
                logger.info(f"Progress: {len(pages)} pages scraped, {len(visited)} visited")

        logger.info(f"Link-crawl complete: {len(pages)} pages scraped")
        return pages
