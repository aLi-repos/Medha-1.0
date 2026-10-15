"""Tests for Stage 4 — Permission-Aware RAG."""

import os

import pytest
from fastapi.testclient import TestClient

from app.services.rag.chunker import DocumentChunk, chunk_text
from app.services.rag.document_parser import ParsedDocument, parse_text, parse_text_file
from app.services.rag.embeddings import TFIDFModel, cosine_similarity
from app.services.rag.permission_filter import PermissionContext, permission_filter
from app.services.rag.retrieval import retrieval_service
from app.services.rag.vector_store import VectorStore


# ── Document Parser Tests ──

class TestDocumentParser:
    def test_parse_text_returns_parsed_document(self) -> None:
        doc = parse_text("Hello world", "test.txt")
        assert isinstance(doc, ParsedDocument)
        assert doc.source_name == "test.txt"
        assert doc.text == "Hello world"
        assert doc.classification == "internal"

    def test_parse_text_file_reads_existing_file(self, tmp_path) -> None:
        f = tmp_path / "doc.txt"
        f.write_text("File content here", encoding="utf-8")
        doc = parse_text_file(str(f))
        assert doc.text == "File content here"
        assert doc.source_name == "doc.txt"

    def test_parse_text_file_raises_on_missing(self) -> None:
        with pytest.raises(FileNotFoundError):
            parse_text_file("/nonexistent/file.txt")


# ── Chunker Tests ──

class TestChunker:
    def test_short_text_single_chunk(self) -> None:
        chunks = chunk_text("Short text", "src.txt")
        assert len(chunks) == 1
        assert chunks[0].text == "Short text"
        assert chunks[0].chunk_index == 0
        assert chunks[0].source_name == "src.txt"

    def test_long_text_multiple_chunks(self) -> None:
        text = "A" * 1000
        chunks = chunk_text(text, "src.txt", chunk_size=300, overlap=50)
        assert len(chunks) > 1
        for c in chunks:
            assert c.source_name == "src.txt"
        assert chunks[0].chunk_index == 0
        assert chunks[-1].chunk_index == len(chunks) - 1

    def test_overlap_preserves_context(self) -> None:
        text = "Alpha Bravo Charlie Delta Echo Foxtrot"
        chunks = chunk_text(text, "src.txt", chunk_size=20, overlap=5)
        assert len(chunks) >= 2

    def test_empty_whitespace_chunks_excluded(self) -> None:
        text = "   \n\n   "
        chunks = chunk_text(text, "src.txt")
        assert len(chunks) == 0

    def test_invalid_chunk_size_raises(self) -> None:
        with pytest.raises(ValueError):
            chunk_text("x", "s.txt", chunk_size=0)

    def test_invalid_overlap_raises(self) -> None:
        with pytest.raises(ValueError):
            chunk_text("x", "s.txt", chunk_size=10, overlap=10)


# ── Embeddings Tests ──

class TestEmbeddings:
    def test_tfidf_fit_and_transform(self) -> None:
        model = TFIDFModel()
        model.fit(["hello world", "hello there"])
        vec = model.transform("hello world")
        assert isinstance(vec, list)
        assert all(isinstance(v, float) for v in vec)
        assert len(vec) > 0

    def test_tfidf_transform_before_fit_raises(self) -> None:
        model = TFIDFModel()
        with pytest.raises(RuntimeError):
            model.transform("hello")

    def test_cosine_similarity_identical(self) -> None:
        v = [1.0, 2.0, 3.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_cosine_similarity_orthogonal(self) -> None:
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_cosine_similarity_empty(self) -> None:
        assert cosine_similarity([], []) == 0.0

    def test_transform_batch(self) -> None:
        model = TFIDFModel()
        model.fit(["alpha bravo", "charlie delta"])
        vecs = model.transform_batch(["alpha", "charlie"])
        assert len(vecs) == 2


# ── Vector Store Tests ──

class TestVectorStore:
    def test_add_and_search(self) -> None:
        store = VectorStore()
        store.add_chunks([
            {"source_name": "a.txt", "chunk_index": 0, "text": "pump inspection report",
             "start_char": 0, "end_char": 24, "classification": "internal"},
            {"source_name": "b.txt", "chunk_index": 0, "text": "boiler standard operating procedure",
             "start_char": 0, "end_char": 34, "classification": "internal"},
        ])
        results = store.search("pump")
        assert len(results) > 0
        assert results[0][0].source_name == "a.txt"

    def test_search_empty_store(self) -> None:
        store = VectorStore()
        assert store.search("anything") == []

    def test_delete_source(self) -> None:
        store = VectorStore()
        store.add_chunks([
            {"source_name": "a.txt", "chunk_index": 0, "text": "doc one",
             "start_char": 0, "end_char": 7, "classification": "internal"},
            {"source_name": "b.txt", "chunk_index": 0, "text": "doc two",
             "start_char": 0, "end_char": 7, "classification": "internal"},
        ])
        removed = store.delete_source("a.txt")
        assert removed == 1
        assert store.get_source_names() == ["b.txt"]

    def test_total_chunks(self) -> None:
        store = VectorStore()
        store.add_chunks([
            {"source_name": "a.txt", "chunk_index": 0, "text": "hello",
             "start_char": 0, "end_char": 5, "classification": "internal"},
        ])
        assert store.total_chunks() == 1


# ── Permission Filter Tests ──

class TestPermissionFilter:
    def _chunk(self, source: str = "doc.txt", classification: str = "internal"):
        from app.services.rag.vector_store import StoredChunk
        return StoredChunk(
            source_name=source, chunk_index=0, text="x",
            start_char=0, end_char=1, classification=classification, vector=[]
        )

    def test_empty_sources_fails_closed(self) -> None:
        ctx = PermissionContext(allowed_sources=[], sensitivity_level="internal", network_policy="deny_external")
        chunks = [(self._chunk(), 0.9)]
        result = permission_filter.filter_chunks(chunks, ctx)
        assert len(result) == 0

    def test_source_not_in_allowed_is_excluded(self) -> None:
        ctx = PermissionContext(allowed_sources=["allowed.txt"], sensitivity_level="internal", network_policy="deny_external")
        chunks = [(self._chunk(source="other.txt"), 0.9)]
        result = permission_filter.filter_chunks(chunks, ctx)
        assert len(result) == 0

    def test_source_in_allowed_is_included(self) -> None:
        ctx = PermissionContext(allowed_sources=["allowed.txt"], sensitivity_level="internal", network_policy="deny_external")
        chunks = [(self._chunk(source="allowed.txt"), 0.9)]
        result = permission_filter.filter_chunks(chunks, ctx)
        assert len(result) == 1

    def test_higher_classification_excluded(self) -> None:
        ctx = PermissionContext(allowed_sources=["doc.txt"], sensitivity_level="internal", network_policy="deny_external")
        chunks = [(self._chunk(classification="restricted"), 0.9)]
        result = permission_filter.filter_chunks(chunks, ctx)
        assert len(result) == 0

    def test_same_classification_included(self) -> None:
        ctx = PermissionContext(allowed_sources=["doc.txt"], sensitivity_level="confidential", network_policy="deny_external")
        chunks = [(self._chunk(classification="confidential"), 0.9)]
        result = permission_filter.filter_chunks(chunks, ctx)
        assert len(result) == 1

    def test_lower_classification_included(self) -> None:
        ctx = PermissionContext(allowed_sources=["doc.txt"], sensitivity_level="restricted", network_policy="deny_external")
        chunks = [(self._chunk(classification="internal"), 0.9)]
        result = permission_filter.filter_chunks(chunks, ctx)
        assert len(result) == 1


# ── API Integration Tests ──

class TestKnowledgeAPI:
    def test_ingest_document(self, client: TestClient, engineer_headers: dict[str, str]) -> None:
        response = client.post(
            "/api/knowledge/documents",
            json={"text": "Test document content", "source_name": "test.txt", "classification": "internal"},
            headers=engineer_headers,
        )
        assert response.status_code == 201
        body = response.json()
        assert body["source_name"] == "test.txt"
        assert body["chunks_created"] >= 1

    def test_ingest_requires_engineer_or_admin(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        response = client.post(
            "/api/knowledge/documents",
            json={"text": "content", "source_name": "x.txt"},
            headers=auth_headers,
        )
        assert response.status_code == 403

    def test_search_requires_authentication(self, client: TestClient) -> None:
        response = client.post(
            "/api/knowledge/search",
            json={"task_id": "abc", "query": "test"},
        )
        assert response.status_code == 401

    def test_full_ingest_and_search_flow(self, client: TestClient, engineer_headers: dict[str, str], auth_headers: dict[str, str]) -> None:
        # Engineer ingests document
        ingest_resp = client.post(
            "/api/knowledge/documents",
            json={
                "text": "Pump P-101 inspection report shows bearing temperature at 42°C.",
                "source_name": "inspection.txt",
                "classification": "internal",
            },
            headers=engineer_headers,
        )
        assert ingest_resp.status_code == 201

        # Operator creates a Task Passport with allowed_sources
        task_resp = client.post(
            "/api/tasks",
            json={
                "title": "Pump analysis",
                "purpose": "Analyze pump inspection data",
                "allowed_sources": ["inspection.txt"],
            },
            headers=auth_headers,
        )
        assert task_resp.status_code == 201
        task_id = task_resp.json()["task_id"]

        # Search
        search_resp = client.post(
            "/api/knowledge/search",
            json={"task_id": task_id, "query": "pump temperature"},
            headers=auth_headers,
        )
        assert search_resp.status_code == 200
        body = search_resp.json()
        assert body["total_after_filter"] >= 1
        assert any(c["source_name"] == "inspection.txt" for c in body["chunks"])

    def test_search_excludes_unauthorized_sources(self, client: TestClient, engineer_headers: dict[str, str], auth_headers: dict[str, str]) -> None:
        # Engineer ingests two documents
        client.post(
            "/api/knowledge/documents",
            json={"text": "Public asset information.", "source_name": "public.txt", "classification": "internal"},
            headers=engineer_headers,
        )
        client.post(
            "/api/knowledge/documents",
            json={"text": "Restricted engineering drawing data.", "source_name": "drawing.txt", "classification": "restricted"},
            headers=engineer_headers,
        )

        # Task Passport only allows public.txt
        task_resp = client.post(
            "/api/tasks",
            json={
                "title": "Public query",
                "purpose": "Query public assets only",
                "allowed_sources": ["public.txt"],
            },
            headers=auth_headers,
        )
        task_id = task_resp.json()["task_id"]

        search_resp = client.post(
            "/api/knowledge/search",
            json={"task_id": task_id, "query": "engineering data"},
            headers=auth_headers,
        )
        body = search_resp.json()
        for c in body["chunks"]:
            assert c["source_name"] == "public.txt"

    def test_list_sources(self, client: TestClient, engineer_headers: dict[str, str]) -> None:
        client.post(
            "/api/knowledge/documents",
            json={"text": "content", "source_name": "s1.txt"},
            headers=engineer_headers,
        )
        resp = client.get("/api/knowledge/sources", headers=engineer_headers)
        assert resp.status_code == 200
        assert "s1.txt" in resp.json()["sources"]

    def test_delete_source(self, client: TestClient, engineer_headers: dict[str, str]) -> None:
        client.post(
            "/api/knowledge/documents",
            json={"text": "content", "source_name": "del.txt"},
            headers=engineer_headers,
        )
        resp = client.delete("/api/knowledge/sources/del.txt", headers=engineer_headers)
        assert resp.status_code == 204

    def test_delete_nonexistent_source(self, client: TestClient, engineer_headers: dict[str, str]) -> None:
        resp = client.delete("/api/knowledge/sources/nope.txt", headers=engineer_headers)
        assert resp.status_code == 404

    def test_search_with_higher_sensitivity_excludes_restricted(self, client: TestClient, engineer_headers: dict[str, str], auth_headers: dict[str, str]) -> None:
        client.post(
            "/api/knowledge/documents",
            json={"text": "Restricted content here.", "source_name": "r.txt", "classification": "restricted"},
            headers=engineer_headers,
        )
        task_resp = client.post(
            "/api/tasks",
            json={"title": "Internal task", "purpose": "test", "sensitivity": "internal"},
            headers=auth_headers,
        )
        task_id = task_resp.json()["task_id"]
        search_resp = client.post(
            "/api/knowledge/search",
            json={"task_id": task_id, "query": "restricted content"},
            headers=auth_headers,
        )
        body = search_resp.json()
        assert body["total_after_filter"] == 0
