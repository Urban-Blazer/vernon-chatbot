import logging
from dataclasses import dataclass
from collections.abc import AsyncGenerator

import anthropic
from app.vectorstore import VectorStore

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a helpful customer service assistant. Your job is to answer questions based ONLY on the provided context from our website.

Rules:
1. Only answer based on the context provided below. Do not make up information.
2. If the context doesn't contain enough information to answer the question, say: "I don't have enough information to answer that question. Would you like me to connect you with a human agent?"
3. Be friendly, concise, and professional.
4. When relevant, mention the source page where the information was found.
5. If the user greets you, respond warmly and ask how you can help.

Context from our website:
{context}"""


@dataclass
class ChatResponse:
    answer: str
    sources: list[dict]


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

    def query(self, question: str, top_k: int = 5) -> ChatResponse:
        """Synchronous RAG query."""
        matches = self.vector_store.query(question, top_k=top_k)
        context = self._build_context(matches)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=SYSTEM_PROMPT.format(context=context),
            messages=[{"role": "user", "content": question}],
        )

        sources = [{"url": m["source_url"], "title": m["title"]} for m in matches]
        # Deduplicate sources by URL
        seen = set()
        unique_sources = []
        for s in sources:
            if s["url"] not in seen:
                seen.add(s["url"])
                unique_sources.append(s)

        return ChatResponse(
            answer=response.content[0].text,
            sources=unique_sources,
        )

    async def stream(self, question: str, top_k: int = 5) -> AsyncGenerator[str, None]:
        """Stream RAG response via SSE-compatible generator."""
        matches = self.vector_store.query(question, top_k=top_k)
        context = self._build_context(matches)

        # Deduplicate sources
        seen = set()
        unique_sources = []
        for m in matches:
            if m["source_url"] not in seen:
                seen.add(m["source_url"])
                unique_sources.append({"url": m["source_url"], "title": m["title"]})

        async with self.async_client.messages.stream(
            model=self.model,
            max_tokens=1024,
            system=SYSTEM_PROMPT.format(context=context),
            messages=[{"role": "user", "content": question}],
        ) as stream:
            async for text in stream.text_stream:
                yield text
