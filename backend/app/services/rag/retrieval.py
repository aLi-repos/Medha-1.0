"""Retrieval orchestrator — Task Passport → ingest → search → filter → audit."""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.task import SecurityMode
from app.services.audit_service import audit_service
from app.services.rag.chunker import DocumentChunk, chunk_text
from app.services.rag.document_parser import ParsedDocument, parse_text
from app.services.rag.permission_filter import PermissionContext, permission_filter
from app.services.rag.vector_store import StoredChunk, vector_store
from app.services.security_mode import PolicyDecision, security_mode_engine


@dataclass
class SearchResult:
    chunks: list[dict]
    total_before_filter: int
    total_after_filter: int


class RetrievalService:
    """Permission-aware RAG retrieval orchestrator."""

    def __init__(self) -> None:
        self._vector_store = vector_store

    def ingest_document(
        self,
        text: str,
        source_name: str,
        classification: str = "internal",
    ) -> int:
        parsed = parse_text(text, source_name, classification)
        chunks = chunk_text(parsed.text, parsed.source_name, classification=parsed.classification)
        chunk_dicts = [
            {
                "source_name": c.source_name,
                "chunk_index": c.chunk_index,
                "text": c.text,
                "start_char": c.start_char,
                "end_char": c.end_char,
                "classification": c.classification,
            }
            for c in chunks
        ]
        self._vector_store.add_chunks(chunk_dicts)
        return len(chunks)

    def search(
        self,
        query: str,
        allowed_sources: list[str] | None = None,
        sensitivity_level: str = "internal",
        network_policy: str = "deny_external",
        top_k: int = 5,
        task_id: str | None = None,
        user_id: str = "",
        identity: str = "",
        role: str = "",
        security_mode: SecurityMode = SecurityMode.STANDARD,
    ) -> SearchResult:
        results = self._vector_store.search(query, top_k=top_k * 3)
        total_before = len(results)

        ctx = PermissionContext(
            allowed_sources=allowed_sources or [],
            sensitivity_level=sensitivity_level,
            network_policy=network_policy,
        )
        filtered = permission_filter.filter_chunks(results, ctx)

        # Security mode: filter out denied RAG sources
        security_filtered = []
        denied_count = 0
        for chunk, score in filtered:
            decision, _reason = security_mode_engine.check_rag_allowed(
                chunk.source_name, allowed_sources or [], security_mode
            )
            if decision == PolicyDecision.DENY:
                denied_count += 1
                if task_id:
                    audit_service.record(
                        event_type="rag_source_denied_by_security_mode",
                        task_id=task_id,
                        user_id=user_id,
                        identity=identity,
                        role=role,
                        security_mode=security_mode.value,
                        detail=_reason,
                    )
            else:
                security_filtered.append((chunk, score))

        limited = security_filtered[:top_k]

        if task_id:
            audit_service.record(
                event_type="rag_search",
                task_id=task_id,
                user_id=user_id,
                identity=identity,
                role=role,
                security_mode=security_mode.value,
                detail=(
                    f"query='{query}' results={total_before} "
                    f"filtered={len(limited)} security_denied={denied_count} "
                    f"mode={security_mode.value}"
                ),
            )

        return SearchResult(
            chunks=[
                {
                    "source_name": c.source_name,
                    "chunk_index": c.chunk_index,
                    "text": c.text,
                    "classification": c.classification,
                    "score": round(score, 4),
                }
                for c, score in limited
            ],
            total_before_filter=total_before,
            total_after_filter=len(limited),
        )

    def delete_source(self, source_name: str) -> int:
        return self._vector_store.delete_source(source_name)

    def get_sources(self) -> list[str]:
        return self._vector_store.get_source_names()

    def total_chunks(self) -> int:
        return self._vector_store.total_chunks()


retrieval_service = RetrievalService()
