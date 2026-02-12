import logging
import re
from dataclasses import dataclass, field
from collections.abc import AsyncGenerator

import anthropic
from app.vectorstore import VectorStore

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a helpful customer service assistant for the City of Vernon. Your job is to answer questions based ONLY on the provided context from our website.

Rules:
1. Only answer based on the context provided below. Do not make up information.
2. If the context doesn't contain enough information to answer the question, say you don't have enough information and offer to connect them with a person. End your response with [HANDOFF_NEEDED].
3. Be friendly, concise, and professional.
4. When relevant, mention the source page where the information was found.
5. If the user greets you, respond warmly and ask how you can help.
6. Respond in {language_name}. All text in your response must be in {language_name}.
7. At the very end of your response, on a new line, output your confidence level as: [CONFIDENCE:X.XX] where X.XX is a number between 0.00 and 1.00 representing how confident you are that the context fully answers the question.

Context from our website:
{context}"""

LANGUAGE_NAMES = {
    "en": "English",
    "fr": "French",
}


@dataclass
class ChatResponse:
    answer: str
    sources: list[dict]
    confidence: float = 0.5
    handoff_needed: bool = False


def extract_confidence(text: str) -> tuple[str, float]:
    """Extract and strip [CONFIDENCE:X.XX] from response text."""
    match = re.search(r"\[CONFIDENCE:([\d.]+)\]", text)
    if match:
        confidence = float(match.group(1))
        clean_text = text[: match.start()].rstrip()
        return clean_text, min(max(confidence, 0.0), 1.0)
    return text, 0.5


def extract_handoff(text: str) -> tuple[str, bool]:
    """Extract and strip [HANDOFF_NEEDED] from response text."""
    if "[HANDOFF_NEEDED]" in text:
        return text.replace("[HANDOFF_NEEDED]", "").rstrip(), True
    return text, False


def retrieval_confidence(matches: list[dict]) -> float:
    """Convert cosine distances to a 0-1 confidence score."""
    if not matches:
        return 0.0
    distances = [m.get("distance", 1.0) for m in matches]
    avg_distance = sum(distances) / len(distances)
    # ChromaDB cosine distance: 0 = identical, 2 = opposite
    return max(0.0, 1.0 - (avg_distance / 2.0))


def _deduplicate_sources(matches: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for m in matches:
        url = m.get("source_url") or m.get("url", "")
        title = m.get("title", "")
        if url not in seen:
            seen.add(url)
            unique.append({"url": url, "title": title})
    return unique


class RAGPipeline:
    def __init__(self, vector_store: VectorStore, api_key: str, model: str = "claude-sonnet-4-5-20250929"):
        self.vector_store = vector_store
        self.client = anthropic.Anthropic(api_key=api_key)
        self.async_client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    def _build_context(self, matches: list[dict]) -> str:
        if not matches:
            return "No relevant information found in the knowledge base."

        context_parts = []
        for i, match in enumerate(matches, 1):
            context_parts.append(
                f"[Source {i}: {match['title']}]\n"
                f"URL: {match['source_url']}\n"
                f"{match['text']}\n"
            )
        return "\n---\n".join(context_parts)

    def _build_system_prompt(self, context: str, language: str = "en", topic: str = "general") -> str:
        language_name = LANGUAGE_NAMES.get(language, "English")
        prompt = SYSTEM_PROMPT.format(
            context=context,
            language_name=language_name,
        )
        # Append topic-specific guidance
        if topic and topic != "general":
            from app.topic_router import get_prompt_addition
            addition = get_prompt_addition(topic)
            if addition:
                prompt += f"\n\n{addition}"
        return prompt

    def query(self, question: str, top_k: int = 5, language: str = "en", topic: str = "general") -> ChatResponse:
        """Synchronous RAG query."""
        matches = self.vector_store.query(question, top_k=top_k)
        context = self._build_context(matches)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=self._build_system_prompt(context, language, topic),
            messages=[{"role": "user", "content": question}],
        )

        raw_text = response.content[0].text
        text, confidence = extract_confidence(raw_text)
        text, handoff_needed = extract_handoff(text)

        # Blend LLM confidence with retrieval confidence
        ret_conf = retrieval_confidence(matches)
        final_confidence = (confidence * 0.6) + (ret_conf * 0.4)

        return ChatResponse(
            answer=text,
            sources=_deduplicate_sources(matches),
            confidence=round(final_confidence, 2),
            handoff_needed=handoff_needed,
        )

    async def stream(
        self, question: str, top_k: int = 5, language: str = "en", topic: str = "general"
    ) -> AsyncGenerator[str, None]:
        """Stream RAG response via SSE-compatible generator."""
        matches = self.vector_store.query(question, top_k=top_k)
        context = self._build_context(matches)

        async with self.async_client.messages.stream(
            model=self.model,
            max_tokens=1024,
            system=self._build_system_prompt(context, language, topic),
            messages=[{"role": "user", "content": question}],
        ) as stream:
            async for text in stream.text_stream:
                yield text

    def get_sources(self, question: str, top_k: int = 5) -> list[dict]:
        """Get deduplicated sources for a question without calling the LLM."""
        matches = self.vector_store.query(question, top_k=top_k)
        return _deduplicate_sources(matches)

    def get_retrieval_confidence(self, question: str, top_k: int = 5) -> float:
        """Get retrieval confidence for a question."""
        matches = self.vector_store.query(question, top_k=top_k)
        return retrieval_confidence(matches)

    def summarize_conversation(self, messages: list[dict]) -> str:
        """Generate a summary of a conversation for staff handoff."""
        conversation_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in messages
        )
        response = self.client.messages.create(
            model=self.model,
            max_tokens=300,
            system=(
                "Summarize this customer service conversation in 2-3 sentences for a staff member. "
                "Include the customer's main question and the resolution status. "
                "Be concise and factual."
            ),
            messages=[{"role": "user", "content": conversation_text}],
        )
        return response.content[0].text.strip()
