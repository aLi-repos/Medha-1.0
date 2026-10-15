"""In-memory vector store with permission-aware similarity search."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.rag.embeddings import TFIDFModel, cosine_similarity


@dataclass
class StoredChunk:
    source_name: str
    chunk_index: int
    text: str
    start_char: int
    end_char: int
    classification: str
    vector: list[float] = field(default_factory=list)


class VectorStore:
    """Stores document chunks with their embeddings for similarity search."""

    def __init__(self) -> None:
        self._chunks: list[StoredChunk] = []
        self._model = TFIDFModel()
        self._source_count: dict[str, int] = {}

    def add_chunks(self, chunks: list[dict]) -> None:
        """Add pre-chunked documents and build the TF-IDF index."""
        texts = [c["text"] for c in chunks]
        self._model.fit(texts)
        vectors = self._model.transform_batch(texts)

        for chunk_dict, vector in zip(chunks, vectors):
            stored = StoredChunk(
                source_name=chunk_dict["source_name"],
                chunk_index=chunk_dict["chunk_index"],
                text=chunk_dict["text"],
                start_char=chunk_dict["start_char"],
                end_char=chunk_dict["end_char"],
                classification=chunk_dict["classification"],
                vector=vector,
            )
            self._chunks.append(stored)
            src = stored.source_name
            self._source_count[src] = self._source_count.get(src, 0) + 1

    def search(self, query: str, top_k: int = 5) -> list[tuple[StoredChunk, float]]:
        if not self._model.fitted or not self._chunks:
            return []
        query_vec = self._model.transform(query)
        scored = [
            (chunk, cosine_similarity(query_vec, chunk.vector))
            for chunk in self._chunks
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def delete_source(self, source_name: str) -> int:
        before = len(self._chunks)
        self._chunks = [c for c in self._chunks if c.source_name != source_name]
        removed = before - len(self._chunks)
        self._source_count.pop(source_name, None)
        if self._chunks:
            texts = [c.text for c in self._chunks]
            self._model.fit(texts)
            vectors = self._model.transform_batch(texts)
            for chunk, vec in zip(self._chunks, vectors):
                chunk.vector = vec
        else:
            self._model = TFIDFModel()
        return removed

    def get_source_names(self) -> list[str]:
        return sorted(self._source_count.keys())

    def total_chunks(self) -> int:
        return len(self._chunks)

    def reset(self) -> None:
        """Clear all stored data — for testing only."""
        self._chunks.clear()
        self._source_count.clear()
        self._model = TFIDFModel()


vector_store = VectorStore()
