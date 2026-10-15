"""P4 focused tests — evidence metadata, source-aware chat, security.

Covers:
  1. RAG returns authorized source metadata (name/snippet/score/classification)
  2. RAG returns relevant snippets
  3. Unauthorized sources excluded
  4. Sensitivity filtering still works
  5. Empty authorization fails closed
  6. Cross-user/task evidence cannot leak via allowed_sources
  7. Chat response includes sources when RAG retrieves evidence
  8. Chat response empty sources when no evidence
  9. Retrieved evidence passed to local model prompt (grounding)
 10. General Chat sources=[] (unchanged behavior)
 11. Task Chat sources shape unchanged when no RAG
 12. Demo documents are synthetic and labeled
 13. P3 demo page isolation (no /api/demo endpoints)
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.services.model_router.model_adapter import ModelAdapterFactory, ModelResponse
from app.services.rag.demo_documents import DEMO_DOCUMENTS, get_demo_documents
from app.services.rag.permission_filter import PermissionContext, permission_filter
from app.services.rag.retrieval import retrieval_service
from app.services.rag.vector_store import vector_store
from app.api.routes.chat import _extract_sources


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def captured_model_inputs(monkeypatch):
    captured: list[str] = []

    class _SpyAdapter:
        name = "local-qwen2"

        def generate(self, prompt: str, max_tokens: int = 512) -> ModelResponse:
            captured.append(prompt)
            return ModelResponse(
                model_name=self.name,
                text="ok",
                tokens_used=1,
                latency_ms=1.0,
            )

    monkeypatch.setattr(
        ModelAdapterFactory,
        "get",
        classmethod(lambda cls, name: _SpyAdapter()),
    )
    return captured


@pytest.fixture(autouse=True)
def clean_vector_store():
    """Isolate vector store between tests."""
    vector_store.reset()
    yield
    vector_store.reset()


def _login(client: TestClient, username: str, password: str) -> dict:
    resp = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ── 1–2: RAG source metadata + snippets ──────────────────────────────────


class TestRagSourceMetadata:
    def test_search_returns_source_name_snippet_score_classification(self):
        retrieval_service.ingest_document(
            text="Pump P-204 bearing temperature is 62 degrees Celsius during inspection.",
            source_name="Pump_P204_Inspection_Report",
            classification="internal",
        )
        result = retrieval_service.search(
            query="pump bearing temperature",
            allowed_sources=["Pump_P204_Inspection_Report"],
            sensitivity_level="internal",
            top_k=5,
        )
        assert len(result.chunks) >= 1
        chunk = result.chunks[0]
        assert chunk["source_name"] == "Pump_P204_Inspection_Report"
        assert isinstance(chunk["score"], float)
        assert chunk["classification"] == "internal"
        assert "bearing temperature" in chunk["text"].lower() or "62" in chunk["text"]

    def test_snippet_is_relevant_text_from_document(self):
        retrieval_service.ingest_document(
            text="Isolation lockout procedure requires zero energy verification at coupling.",
            source_name="Pump_P204_Maintenance_SOP",
            classification="internal",
        )
        result = retrieval_service.search(
            query="isolation lockout zero energy",
            allowed_sources=["Pump_P204_Maintenance_SOP"],
            sensitivity_level="internal",
            top_k=3,
        )
        assert result.chunks
        assert "lockout" in result.chunks[0]["text"].lower()


# ── 3–5: Security — unauthorized, sensitivity, empty allowlist ───────────


class TestRagSecurity:
    def test_unauthorized_source_excluded(self):
        vector_store.add_chunks([
            {"source_name": "allowed.txt", "chunk_index": 0, "text": "allowed content pump",
             "start_char": 0, "end_char": 20, "classification": "internal"},
            {"source_name": "secret.txt", "chunk_index": 0, "text": "secret content pump",
             "start_char": 0, "end_char": 19, "classification": "internal"},
        ])
        result = retrieval_service.search(
            query="pump",
            allowed_sources=["allowed.txt"],
            sensitivity_level="internal",
            top_k=10,
        )
        assert all(c["source_name"] == "allowed.txt" for c in result.chunks)
        assert not any(c["source_name"] == "secret.txt" for c in result.chunks)

    def test_sensitivity_filtering_excludes_restricted(self):
        vector_store.add_chunks([
            {"source_name": "ok.txt", "chunk_index": 0, "text": "internal pump data",
             "start_char": 0, "end_char": 17, "classification": "internal"},
            {"source_name": "ok.txt", "chunk_index": 1, "text": "restricted pump data",
             "start_char": 0, "end_char": 19, "classification": "restricted"},
        ])
        result = retrieval_service.search(
            query="pump data",
            allowed_sources=["ok.txt"],
            sensitivity_level="internal",
            top_k=10,
        )
        assert all(c["classification"] == "internal" for c in result.chunks)
        assert not any(c["classification"] == "restricted" for c in result.chunks)

    def test_empty_allowlist_fails_closed(self):
        from app.services.rag.vector_store import StoredChunk

        chunk = StoredChunk(
            source_name="any.txt", chunk_index=0, text="x",
            start_char=0, end_char=1, classification="internal", vector=[],
        )
        ctx = PermissionContext(
            allowed_sources=[],
            sensitivity_level="restricted",
            network_policy="deny_external",
        )
        assert permission_filter.filter_chunks([(chunk, 0.99)], ctx) == []

    def test_empty_allowlist_search_returns_nothing(self):
        retrieval_service.ingest_document(
            text="pump data",
            source_name="doc.txt",
            classification="internal",
        )
        result = retrieval_service.search(
            query="pump",
            allowed_sources=[],
            sensitivity_level="restricted",
            top_k=5,
        )
        assert result.chunks == []

    def test_cross_user_task_cannot_leak_unauthorized_source(
        self, client: TestClient, engineer_headers: dict, auth_headers: dict
    ):
        """User B task with different allowed_sources cannot see User A doc."""
        # Engineer ingests two docs
        client.post(
            "/api/knowledge/documents",
            json={"text": "Alpha secret pump bearing data.", "source_name": "alpha.txt",
                  "classification": "internal"},
            headers=engineer_headers,
        )
        client.post(
            "/api/knowledge/documents",
            json={"text": "Beta public pump summary.", "source_name": "beta.txt",
                  "classification": "internal"},
            headers=engineer_headers,
        )

        # Task allows only beta.txt
        task_resp = client.post(
            "/api/tasks",
            json={"title": "Isolation", "purpose": "check", "allowed_sources": ["beta.txt"]},
            headers=auth_headers,
        )
        assert task_resp.status_code == 201
        task_id = task_resp.json()["task_id"]

        search = client.post(
            "/api/knowledge/search",
            json={"task_id": task_id, "query": "pump bearing secret"},
            headers=auth_headers,
        )
        assert search.status_code == 200
        names = {c["source_name"] for c in search.json()["chunks"]}
        assert "alpha.txt" not in names
        assert names <= {"beta.txt"}


# ── 6: ChatResponse sources wiring ───────────────────────────────────────


class TestExtractSources:
    def test_dedupes_by_name_and_keeps_first_snippet(self):
        chunks = [
            {"source_name": "a.pdf", "text": "first snippet about bearings"},
            {"source_name": "a.pdf", "text": "duplicate"},
            {"source_name": "b.pdf", "text": "second snippet about seals"},
        ]
        sources = _extract_sources(chunks)
        assert len(sources) == 2
        assert sources[0].name == "a.pdf"
        assert sources[0].snippet == "first snippet about bearings"
        assert sources[1].name == "b.pdf"

    def test_empty_chunks_returns_empty_list(self):
        assert _extract_sources([]) == []

    def test_skips_blank_source_names(self):
        assert _extract_sources([{"source_name": "", "text": "x"}]) == []


class TestChatSources:
    @staticmethod
    def _authorize_task(client, headers, task_id):
        for status in ("authorized", "executing"):
            resp = client.patch(
                f"/api/tasks/{task_id}/status",
                json={"new_status": status, "detail": "p4 test"},
                headers=headers,
            )
            assert resp.status_code == 200, f"{status}: {resp.text}"

    def test_chat_returns_sources_when_rag_retrieves(
        self, client, engineer_headers, auth_headers, captured_model_inputs
    ):
        client.post(
            "/api/knowledge/documents",
            json={
                "text": "Pump P-204 bearing temperature measured at 62 C.",
                "source_name": "Pump_P204_Inspection_Report",
                "classification": "internal",
            },
            headers=engineer_headers,
        )
        task_resp = client.post(
            "/api/tasks",
            json={
                "title": "Pump P-204 inspection",
                "purpose": "Analyze pump inspection data",
                "allowed_sources": ["Pump_P204_Inspection_Report"],
                "sensitivity": "internal",
            },
            headers=auth_headers,
        )
        assert task_resp.status_code == 201
        task_id = task_resp.json()["task_id"]
        self._authorize_task(client, auth_headers, task_id)

        send = client.post(
            "/api/chat/send",
            json={
                "task_id": task_id,
                "prompt": "What is the bearing temperature of pump P-204 according to inspection?",
                "max_tokens": 64,
            },
            headers=auth_headers,
        )
        assert send.status_code == 200, send.text
        body = send.json()
        assert "sources" in body
        assert isinstance(body["sources"], list)
        assert len(body["sources"]) >= 1
        assert body["sources"][0]["name"] == "Pump_P204_Inspection_Report"
        assert body["sources"][0]["snippet"]

        # 9: evidence actually in model prompt
        assert captured_model_inputs, "model was not invoked"
        model_prompt = captured_model_inputs[-1]
        assert "Pump_P204_Inspection_Report" in model_prompt
        assert "INTERNAL EVIDENCE" in model_prompt

    def test_chat_empty_sources_when_no_evidence(
        self, client, auth_headers, captured_model_inputs
    ):
        task_resp = client.post(
            "/api/tasks",
            json={
                "title": "No docs task",
                "purpose": "purpose without any documents",
                "allowed_sources": [],
                "sensitivity": "internal",
            },
            headers=auth_headers,
        )
        assert task_resp.status_code == 201
        task_id = task_resp.json()["task_id"]
        self._authorize_task(client, auth_headers, task_id)

        send = client.post(
            "/api/chat/send",
            json={
                "task_id": task_id,
                "prompt": "Summarize the status of this task and list next steps for the team.",
                "max_tokens": 64,
            },
            headers=auth_headers,
        )
        assert send.status_code == 200, send.text
        body = send.json()
        assert body["sources"] == []

    def test_general_chat_sources_always_empty(
        self, client, auth_headers, captured_model_inputs
    ):
        send = client.post(
            "/api/chat/send",
            json={"prompt": "Hello, what can you help me with today?", "max_tokens": 32},
            headers=auth_headers,
        )
        assert send.status_code == 200, send.text
        assert send.json()["sources"] == []
        # General Chat still uses local path (regression)
        assert captured_model_inputs


# ── 12–13: Demo documents + demo isolation ───────────────────────────────


class TestDemoDocumentsAndIsolation:
    def test_demo_documents_are_synthetic_and_labeled(self):
        docs = get_demo_documents()
        assert len(docs) == 3
        names = {d["source_name"] for d in docs}
        assert names == {
            "Pump_P204_Inspection_Report",
            "Pump_P204_Maintenance_SOP",
            "Pump_P204_Equipment_Reference",
        }
        for d in docs:
            assert "DEMONSTRATION" in d["text"].upper() or "demonstration" in d["text"]
            assert d["classification"] == "internal"

    def test_demo_module_has_no_real_mrpl_claims(self):
        for d in DEMO_DOCUMENTS:
            assert "real MRPL" not in d["text"]
            assert "synthetic" in d["text"].lower() or "demonstration" in d["text"].lower()

    def test_no_demo_backend_endpoints(self, client):
        """P3 isolation: no /api/demo* surface."""
        for path in ("/api/demo", "/api/demo/start", "/api/demo/rag", "/api/demo/documents"):
            resp = client.get(path)
            assert resp.status_code == 404, path

    def test_protected_routes_still_401(self, client):
        for path in (
            "/api/tasks",
            "/api/chat/conversations-all",
            "/api/auth/me",
            "/api/knowledge/search",
        ):
            resp = client.post(path, json={}) if path == "/api/knowledge/search" else client.get(path)
            assert resp.status_code == 401, path


# ── Evidence unit: assess_evidence known list feeds model ────────────────


class TestEvidenceGrounding:
    def test_assess_evidence_known_contains_source_name(self):
        from app.services.ai_pipeline.evidence import assess_evidence
        from app.services.ai_pipeline.intent import ChatIntent
        from app.services.ai_pipeline.resource_planner import ResourcePlan

        intent = ChatIntent(
            objective="answer",
            category="investigation",
            answer_type="factual",
            information_need="bearing temperature",
            required_information=["authorized local source documents"],
            evidence_required=True,
            public_research_useful=False,
            task_id="t1",
            conversation_turns=1,
            follow_up=False,
        )
        plan = ResourcePlan(
            task_id="t1",
            use_conversation=True,
            rag_enabled=True,
            rag_query="bearing temperature",
            authorized_sources=["doc.txt"],
            authorized_tools=[],
            external_research_candidate=False,
            restrictions=[],
        )
        chunks = [{"source_name": "doc.txt", "text": "bearing temperature is 62C"}]
        report = assess_evidence(intent, plan, chunks, attempted_rag=True)
        assert report.enough
        assert any("doc.txt" in k for k in report.known)
        assert report.chunk_count == 1
