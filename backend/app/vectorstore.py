import logging

import chromadb
from chromadb.utils import embedding_functions
from app.chunker import TextChunk

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self, persist_dir: str = "./chroma_data", embedding_model: str = "all-MiniLM-L6-v2"):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embedding_model
        )
        self.collection = self.client.get_or_create_collection(
            name="website_content",
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def ingest(self, chunks: list[TextChunk]) -> int:
        """Store text chunks with their embeddings."""
        if not chunks:
            return 0

        ids = [f"chunk_{chunk.source_url}_{chunk.chunk_index}" for chunk in chunks]
        documents = [chunk.text for chunk in chunks]
        metadatas = [
            {"source_url": chunk.source_url, "title": chunk.title, "chunk_index": chunk.chunk_index}
            for chunk in chunks
        ]

        # Upsert in batches of 100
        batch_size = 100
        for i in range(0, len(ids), batch_size):
            self.collection.upsert(
                ids=ids[i : i + batch_size],
                documents=documents[i : i + batch_size],
                metadatas=metadatas[i : i + batch_size],
            )

        logger.info(f"Ingested {len(chunks)} chunks into vector store")
        return len(chunks)

    def query(self, question: str, top_k: int = 5) -> list[dict]:
        """Find the most relevant chunks for a question."""
        if self.collection.count() == 0:
            return []

        results = self.collection.query(
            query_texts=[question],
            n_results=min(top_k, self.collection.count()),
        )

        matches = []
        for i in range(len(results["documents"][0])):
            matches.append({
                "text": results["documents"][0][i],
                "source_url": results["metadatas"][0][i]["source_url"],
                "title": results["metadatas"][0][i]["title"],
                "distance": results["distances"][0][i] if results.get("distances") else None,
            })

        return matches

    def delete_by_url(self, source_url: str) -> int:
        """Delete all chunks associated with a specific source URL."""
        # ChromaDB supports filtering by metadata
        results = self.collection.get(
            where={"source_url": source_url},
        )
        if results["ids"]:
            self.collection.delete(ids=results["ids"])
            logger.info(f"Deleted {len(results['ids'])} chunks for {source_url}")
            return len(results["ids"])
        return 0

    def delete_by_urls(self, source_urls: list[str]) -> int:
        """Delete all chunks for multiple source URLs."""
        total = 0
        for url in source_urls:
            total += self.delete_by_url(url)
        return total

    def clear(self):
        """Delete all data from the collection."""
        self.client.delete_collection("website_content")
        self.collection = self.client.get_or_create_collection(
            name="website_content",
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("Vector store cleared")

    def count(self) -> int:
        return self.collection.count()
