"""Permission filter for RAG retrieval — Task Passport → allowed document access."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.rag.vector_store import StoredChunk


@dataclass
class PermissionContext:
    allowed_sources: list[str]
    sensitivity_level: str
    network_policy: str


class PermissionFilter:
    """Filters vector store results against Task Passport constraints."""

    _SENSITIVITY_ORDER = ["public", "internal", "confidential", "restricted"]

    def filter_chunks(
        self,
        results: list[tuple[StoredChunk, float]],
        ctx: PermissionContext,
    ) -> list[tuple[StoredChunk, float]]:
        filtered: list[tuple[StoredChunk, float]] = []
        for chunk, score in results:
            if self._is_source_allowed(chunk.source_name, ctx.allowed_sources):
                if self._is_sensitivity_allowed(chunk.classification, ctx.sensitivity_level):
                    filtered.append((chunk, score))
        return filtered

    def _is_source_allowed(self, source_name: str, allowed_sources: list[str]) -> bool:
        # Fail closed: an empty allowlist authorizes NO source.
        if not allowed_sources:
            return False
        return source_name in allowed_sources

    def _is_sensitivity_allowed(self, doc_classification: str, max_sensitivity: str) -> bool:
        try:
            doc_level = self._SENSITIVITY_ORDER.index(doc_classification)
            max_level = self._SENSITIVITY_ORDER.index(max_sensitivity)
        except ValueError:
            return False
        return doc_level <= max_level


permission_filter = PermissionFilter()
