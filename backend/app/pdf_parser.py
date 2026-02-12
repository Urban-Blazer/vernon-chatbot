import hashlib
import io
import logging
from dataclasses import dataclass

from app.scraper import ScrapedPage

logger = logging.getLogger(__name__)


def parse_pdf(source: str | bytes, filename: str = "document.pdf") -> ScrapedPage | None:
    """Extract text from a PDF file or bytes, returning a ScrapedPage.

    Args:
        source: Either a file path (str) or raw PDF bytes.
        filename: Original filename (used for title fallback and URL key).

    Returns:
        A ScrapedPage with combined text from all pages, or None if extraction fails.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.error("pypdf is not installed. Add 'pypdf>=4.0' to requirements.txt.")
        return None

    try:
        if isinstance(source, bytes):
            reader = PdfReader(io.BytesIO(source))
        else:
            reader = PdfReader(source)
    except Exception as e:
        logger.warning(f"Failed to read PDF '{filename}': {e}")
        return None

    # Extract metadata title
    title = filename
    if reader.metadata and reader.metadata.title:
        title = reader.metadata.title

    # Extract text from all pages
    text_parts = []
    for i, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text()
            if page_text and page_text.strip():
                text_parts.append(page_text.strip())
        except Exception as e:
            logger.debug(f"Failed to extract text from page {i+1} of '{filename}': {e}")

    if not text_parts:
        logger.warning(f"No text extracted from PDF '{filename}'")
        return None

    content = "\n\n".join(text_parts)

    # Use pdf:// prefix for URL key to distinguish from web pages
    url = f"pdf://{filename}"
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    return ScrapedPage(
        url=url,
        title=title,
        content=content,
        content_hash=content_hash,
    )


def parse_pdf_from_url(pdf_bytes: bytes, url: str, filename: str = "") -> ScrapedPage | None:
    """Parse a PDF downloaded from a URL during crawl.

    Uses the URL as the source key instead of pdf:// prefix.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.error("pypdf is not installed.")
        return None

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except Exception as e:
        logger.warning(f"Failed to read PDF from {url}: {e}")
        return None

    title = filename or url.split("/")[-1]
    if reader.metadata and reader.metadata.title:
        title = reader.metadata.title

    text_parts = []
    for page in reader.pages:
        try:
            page_text = page.extract_text()
            if page_text and page_text.strip():
                text_parts.append(page_text.strip())
        except Exception:
            pass

    if not text_parts:
        return None

    content = "\n\n".join(text_parts)

    return ScrapedPage(
        url=url,
        title=title,
        content=content,
        content_hash=hashlib.sha256(content.encode()).hexdigest(),
    )
