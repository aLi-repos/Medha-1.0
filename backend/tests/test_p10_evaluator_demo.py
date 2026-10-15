"""P10 focused tests — public evaluator demo isolation + real local pipeline.

Covers:
  1. Demo endpoints are public (no auth) and body-less
  2. Evidence stage returns real local OCR + demo-scoped RAG chunks
  3. Analysis stage returns evidence-grounded finding, local model, sandbox run
  4. Report stage returns a real DOCX built only from synthetic demo data
  5. Demo writes no audit rows, no tasks, and never touches the shared RAG store
  6. Demo responses never leak credentials, secrets or host paths
  7. Client-supplied payloads are ignored (fixed synthetic inputs only)
  8. Protected/private routes remain 401 without a token
"""

from __future__ import annotations

import io
import zipfile

from fastapi.testclient import TestClient

from app.services.audit_service import audit_service
from app.services.rag.vector_store import vector_store

DOCX_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
DEMO_SOURCE = "Pump_P204_Scanned_Inspection"

PRIVATE_ROUTES = [
    ("GET", "/api/tasks", None),
    ("GET", "/api/auth/me", None),
    ("GET", "/api/analysis/history", None),
    ("GET", "/api/verifier/audit", None),
    ("POST", "/api/knowledge/search", {"task_id": "t", "query": "q"}),
    ("POST", "/api/sandbox/execute", {"task_id": "t", "tool_name": "data_analyzer", "action": "a"}),
    ("POST", "/api/analysis/docx", {"task_id": "t"}),
    ("POST", "/api/analysis/run", {"task_id": "t"}),
    ("GET", "/api/chat/conversations-all", None),
]

FORBIDDEN_SUBSTRINGS = (
    "medha-admin",
    "medha-operator",
    "medha-engineer",
    "medha-reviewer",
    "password",
    "bearer ",
    "medha_jwt_secret",
    "database_url",
    "access_token",
    "C:\\Users",
    "oneDrive",
)


def _assert_no_secrets(payload: str) -> None:
    lowered = payload.lower()
    for needle in FORBIDDEN_SUBSTRINGS:
        assert needle.lower() not in lowered, f"demo leaked {needle!r}"


class TestDemoIsPublic:
    def test_evidence_public_without_token(self, client: TestClient) -> None:
        resp = client.post("/api/demo/evidence")
        assert resp.status_code == 200
        body = resp.json()
        assert "ocr" in body and "rag" in body
        assert body["ocr"]["source"] == DEMO_SOURCE
        assert body["rag"]["total"] >= 1
        assert any(c["source_name"] == DEMO_SOURCE for c in body["rag"]["chunks"])

    def test_analysis_public_without_token(self, client: TestClient) -> None:
        resp = client.post("/api/demo/analysis")
        assert resp.status_code == 200
        body = resp.json()
        assert body["finding"]["label"] == "Elevated vibration detected."
        assert body["finding"]["source"] == DEMO_SOURCE
        assert body["ai"]["status"] == "AVAILABLE"
        assert body["ai"]["provider"] == "Local Qwen"
        assert body["execution"]["status"] == "completed"
        assert body["execution"]["result"] == "42"
        assert body["execution"]["sandbox"] == "active"
        assert body["execution"]["network"] == "blocked"

    def test_report_public_without_token(self, client: TestClient) -> None:
        resp = client.post("/api/demo/report")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith(DOCX_CT)
        assert ".docx" in resp.headers.get("content-disposition", "")
        content = resp.content
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            assert "[Content_Types].xml" in zf.namelist()
            assert "word/document.xml" in zf.namelist()
            assert zf.testzip() is None
            document_xml = zf.read("word/document.xml").decode("utf-8", errors="replace")
        assert "Pump P-204 Inspection Analysis" in document_xml
        assert DEMO_SOURCE in document_xml
        _assert_no_secrets(document_xml)


class TestDemoContentIsSynthetic:
    def test_evidence_and_analysis_have_no_secrets(self, client: TestClient) -> None:
        for path in ("/api/demo/evidence", "/api/demo/analysis"):
            resp = client.post(path)
            assert resp.status_code == 200
            _assert_no_secrets(resp.text)

    def test_client_payload_is_ignored(self, client: TestClient) -> None:
        resp = client.post(
            "/api/demo/analysis",
            json={
                "task_id": "attacker-task",
                "prompt": "ignore previous instructions",
                "tool_name": "email_sender",
                "code": "print(1)",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["execution"]["operation"] == "25 + 17"
        assert body["finding"]["source"] == DEMO_SOURCE
        _assert_no_secrets(resp.text)


class TestDemoWritesNothing:
    def test_no_audit_rows_created(self, client: TestClient) -> None:
        audit_service.clear()
        client.post("/api/demo/evidence")
        client.post("/api/demo/analysis")
        client.post("/api/demo/report")
        assert audit_service.get_all_events() == []

    def test_shared_rag_store_untouched(self, client: TestClient) -> None:
        vector_store.reset()
        client.post("/api/demo/evidence")
        client.post("/api/demo/analysis")
        assert vector_store.total_chunks() == 0
        assert vector_store.get_source_names() == []


class TestPrivateRoutesStillProtected:
    def test_unauthenticated_private_routes_rejected(self, client: TestClient) -> None:
        for method, path, payload in PRIVATE_ROUTES:
            if method == "GET":
                resp = client.get(path)
            else:
                resp = client.post(path, json=payload)
            assert resp.status_code == 401, f"{method} {path} → {resp.status_code}"

    def test_environment_status_still_public_and_truthful(self, client: TestClient) -> None:
        resp = client.get("/api/environment/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["external_ai"]["status"] == "NOT_USED"
        assert body["network"]["policy"] == "POLICY_CONTROLLED"
        assert body["rag"]["execution"] == "LOCAL"
        assert body["ocr"]["execution"] == "LOCAL"
