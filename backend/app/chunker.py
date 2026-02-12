from dataclasses import dataclass


@dataclass
class TextChunk:
    text: str
    source_url: str
    title: str
    chunk_index: int


def chunk_text(
    text: str,
    source_url: str,
    title: str,
    chunk_size: int = 400,
    chunk_overlap: int = 50,
) -> list[TextChunk]:
    """Split text into overlapping chunks, respecting paragraph boundaries."""
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    chunks: list[TextChunk] = []
    current_words: list[str] = []
    chunk_index = 0

    for paragraph in paragraphs:
        words = paragraph.split()

        # If adding this paragraph exceeds chunk_size, finalize current chunk
        if current_words and len(current_words) + len(words) > chunk_size:
            chunk_text_str = " ".join(current_words)
            chunks.append(TextChunk(
                text=chunk_text_str,
                source_url=source_url,
                title=title,
                chunk_index=chunk_index,
            ))
            chunk_index += 1

            # Keep overlap from the end of the current chunk
            overlap_words = current_words[-chunk_overlap:] if chunk_overlap > 0 else []
            current_words = overlap_words

        current_words.extend(words)

    # Don't forget the last chunk
    if current_words:
        chunk_text_str = " ".join(current_words)
        chunks.append(TextChunk(
            text=chunk_text_str,
            source_url=source_url,
            title=title,
            chunk_index=chunk_index,
        ))

    return chunks
