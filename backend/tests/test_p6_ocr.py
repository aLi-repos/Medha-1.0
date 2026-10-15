"""P6 focused tests — ONE real local OCR path into existing RAG.

Covers:
  1. OCR accepts supported input (PNG / JPEG / PDF)
  2. OCR produces non-empty text for the synthetic P-204 document
  3. OCR failure is handled safely (clear error, no fabrication)
  4. OCR does not make external/cloud calls
  5. OCR output reaches document ingestion
  6. OCR output can reach existing RAG
  7. Source metadata is preserved
  8. Task/user authorization remains enforced
  9. Unauthorized document cannot be OCR-accessed
  10. Existing P4 RAG / P2 / P3 / auth tests remain green (regression elsewhere)
"""

from __future__ import annotations

import io
import os

import pytest
from fastapi.testclient import TestClient

from app.services.ocr.local_ocr import (
    OcreError,
    is_supported,
    run_local_ocr,
    sanitize_source_name,
)
from app.services.rag.vector_store import vector_store

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
PNG_PATH = os.path.join(FIXTURE_DIR, "Pump_P204_Scanned_Inspection.png")
PDF_PATH = os.path.join(FIXTURE_DIR, "Pump_P204_Scanned_Inspection.pdf")

DETERMINISTIC_FACT = "elevated vibration detected"
SOURCE_NAME = "Pump_P204_Scanned_Inspection.png"


@pytest.fixture(autouse=True)
def _clean_vector_store():
    vector_store.reset()
    yield
    vector_store.reset()


@pytest.fixture(scope="module", autouse=True)
def _ensure_fixtures():
    if not os.path.isfile(PNG_PATH) or not os.path.isfile(PDF_PATH):
        from tests.generate_p6_scan import generate_pdf, generate_png

        generate_png()
        generate_pdf()


def _authorize(client: TestClient, task_id: str, headers: dict[str, str]) -> None:
    client.patch(
        f"/api/tasks/{task_id}/status",
        json={"new_status": "authorized", "detail": "P6 OCR authorization"},
        headers=headers,
    )


def _create_authorized_task(
    client: TestClient,
    headers: dict[str, str],
    *,
    allowed_sources: list[str] | None = None,
    allowed_tools: list[str] | None = None,
) -> str:
    payload = {
        "title": "P6 OCR scan task",
        "purpose": "Local OCR of synthetic Pump P-204 inspection scan",
        "allowed_sources": allowed_sources if allowed_sources is not None else [SOURCE_NAME],
        "allowed_tools": allowed_tools if allowed_tools is not None else [],
    }
    resp = client.post("/api/tasks", json=payload, headers=headers)
    assert resp.status_code in (200, 201), resp.text
    task_id = resp.json()["task_id"]
    _authorize(client, task_id, headers)
    return task_id


def _ocr_request(
    client: TestClient,
    headers: dict[str, str],
    task_id: str,
    path: str,
    *,
    ingest: bool = True,
    filename: str | None = None,
    content_type: str | None = None,
):
    name = filename or os.path.basename(path)
    ctype = content_type or (
        "application/pdf" if path.lower().endswith(".pdf") else "image/png"
    )
    with open(path, "rb") as fh:
        data = fh.read()
    return client.post(
        "/api/knowledge/ocr",
        headers=headers,
        data={"task_id": task_id, "ingest": "true" if ingest else "false"},
        files={"file": (name, io.BytesIO(data), ctype)},
    )


# ── 1–2: Supported input + non-empty extraction (REAL local OCR) ──────────


class TestLocalOcrReal:
    def test_png_ocr_non_empty_with_deterministic_fact(self) -> None:
        assert os.path.isfile(PNG_PATH), "synthetic scan fixture missing"
        result = run_local_ocr(PNG_PATH, source_name=SOURCE_NAME, content_type="image/png")
        assert result.status == "completed"
        assert result.local_processing is True
        assert result.engine == "rapidocr-local"
        assert result.char_count > 0
        assert len(result.text.strip()) > 20
        # Quality check: key fields survive OCR (not hard-coded — comes from engine)
        lowered = result.text.lower()
        assert "p-204" in lowered or "p204" in lowered.replace("-", "")
        assert "vibration" in lowered
        # Deterministic finding used for E2E grounding
        assert DETERMINISTIC_FACT in lowered or "elevated vibration" in lowered

    def test_pdf_ocr_supported(self) -> None:
        assert os.path.isfile(PDF_PATH), "synthetic PDF fixture missing"
        result = run_local_ocr(PDF_PATH, source_name="scan.pdf", content_type="application/pdf")
        assert result.status == "completed"
        assert result.page_count >= 1
        assert result.char_count > 0
        assert "p-204" in result.text.lower() or "p204" in result.text.lower().replace("-", "")

    def test_is_supported_matrix(self) -> None:
        assert is_supported("x.png", "image/png")
        assert is_supported("x.jpg", "image/jpeg")
        assert is_supported("x.pdf", "application/pdf")
        assert not is_supported("x.exe", "application/octet-stream")

    def test_sanitize_source_name_strips_paths(self) -> None:
        assert sanitize_source_name("../../etc/passwd") == "passwd"
        assert sanitize_source_name("C:\\Users\\a\\scan.png") == "scan.png"
        assert sanitize_source_name("") == "scanned_document"


# ── 3: Failure is safe ────────────────────────────────────────────────────


class TestOcrFailureSafety:
    def test_missing_file_fails_clearly(self) -> None:
        with pytest.raises(OcreError, match="not found"):
            run_local_ocr(os.path.join(FIXTURE_DIR, "no_such_file.png"))

    def test_unsupported_extension_fails(self, tmp_path) -> None:
        bad = tmp_path / "evil.exe"
        bad.write_bytes(b"MZ")
        with pytest.raises(OcreError, match="Unsupported"):
            run_local_ocr(str(bad), source_name="evil.exe")

    def test_api_unsupported_rejected(self, client, auth_headers) -> None:
        task_id = _create_authorized_task(client, auth_headers)
        resp = client.post(
            "/api/knowledge/ocr",
            headers=auth_headers,
            data={"task_id": task_id, "ingest": "false"},
            files={"file": ("evil.exe", io.BytesIO(b"MZ"), "application/octet-stream")},
        )
        assert resp.status_code == 400
        assert "Unsupported" in resp.json()["detail"]


# ── 4: No external/cloud OCR calls ────────────────────────────────────────


class TestLocalOnly:
    def test_ocr_module_has_no_network_imports(self) -> None:
        import app.services.ocr.local_ocr as mod

        src = open(mod.__file__, encoding="utf-8").read()
        for banned in ("requests.", "httpx.", "urllib.request", "openai", "google.cloud", "boto3"):
            assert banned not in src, f"OCR must not use external call: {banned}"

    def test_ocr_result_marks_local_processing(self) -> None:
        result = run_local_ocr(PNG_PATH, source_name=SOURCE_NAME)
        assert result.local_processing is True
        assert result.engine in {"rapidocr-local", "pymupdf-text-layer", "rapidocr-local"}


# ── 5–7: API → ingestion → RAG, source metadata ───────────────────────────


class TestOcrToRagPipeline:
    def test_ocr_ingests_and_rag_retrieves(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        from app.services.rag.retrieval import retrieval_service

        task_id = _create_authorized_task(client, auth_headers, allowed_sources=[SOURCE_NAME])
        resp = _ocr_request(client, auth_headers, task_id, PNG_PATH, ingest=True)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "completed"
        assert body["ingested"] is True
        assert body["chunks_created"] >= 1
        assert body["source_name"] == SOURCE_NAME
        assert body["local_processing"] is True
        assert DETERMINISTIC_FACT in body["text"].lower() or "vibration" in body["text"].lower()

        # Source metadata preserved in vector store
        sources = retrieval_service.get_sources()
        assert SOURCE_NAME in sources

        # Existing RAG search path
        search = client.post(
            "/api/knowledge/search",
            json={
                "task_id": task_id,
                "query": "What was the inspection finding for Pump P-204?",
                "top_k": 5,
            },
            headers=auth_headers,
        )
        assert search.status_code == 200, search.text
        chunks = search.json()["chunks"]
        assert chunks, "RAG returned no chunks after OCR ingest"
        assert any(c["source_name"] == SOURCE_NAME for c in chunks)
        joined = " ".join(c["text"].lower() for c in chunks)
        assert "vibration" in joined
        assert "p-204" in joined or "p204" in joined.replace("-", "")

    def test_ocr_without_ingest_does_not_add_source(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        task_id = _create_authorized_task(client, auth_headers)
        resp = _ocr_request(client, auth_headers, task_id, PNG_PATH, ingest=False)
        assert resp.status_code == 200
        body = resp.json()
        assert body["ingested"] is False
        assert body["chunks_created"] == 0
        assert body["char_count"] > 0


# ── 8–9: Task/user authorization ──────────────────────────────────────────


class TestOcrSecurity:
    def test_unauthenticated_rejected(self, client: TestClient) -> None:
        resp = client.post(
            "/api/knowledge/ocr",
            data={"task_id": "x", "ingest": "false"},
            files={"file": ("a.png", io.BytesIO(b"x"), "image/png")},
        )
        assert resp.status_code == 401

    def test_cross_user_cannot_ocr(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        engineer_headers: dict[str, str],
    ) -> None:
        task_id = _create_authorized_task(client, auth_headers)
        resp = _ocr_request(client, engineer_headers, task_id, PNG_PATH, ingest=True)
        assert resp.status_code == 403
        assert "identity" in resp.json()["detail"].lower() or "mismatch" in resp.json()["detail"].lower()

    def test_nonexistent_task(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        resp = _ocr_request(client, auth_headers, "no-such-task-id", PNG_PATH)
        assert resp.status_code == 404

    def test_draft_task_blocked_by_action_gate(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        # Create but leave draft — Action Gate lifecycle should deny READ/OCR
        resp = client.post(
            "/api/tasks",
            json={
                "title": "Draft OCR",
                "purpose": "draft",
                "allowed_sources": [SOURCE_NAME],
            },
            headers=auth_headers,
        )
        task_id = resp.json()["task_id"]
        ocr = _ocr_request(client, auth_headers, task_id, PNG_PATH)
        # Either plan/read blocked (403) — draft must not silently allow OCR
        assert ocr.status_code in (403, 400, 404)
        if ocr.status_code == 403:
            assert ocr.json()["detail"]


# ── Audit trail for OCR ───────────────────────────────────────────────────


class TestOcrAudit:
    def test_ocr_events_recorded(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        from app.services.audit_service import audit_service

        audit_service.clear()
        task_id = _create_authorized_task(client, auth_headers)
        resp = _ocr_request(client, auth_headers, task_id, PNG_PATH, ingest=True)
        assert resp.status_code == 200

        events = audit_service.get_events_for_task(task_id)
        types = {e.event_type for e in events}
        assert "ocr_completed" in types
        assert "ocr_ingested" in types
        completed = [e for e in events if e.event_type == "ocr_completed"]
        assert completed[0].task_id == task_id
        assert completed[0].identity == "operator"
        assert "local" in completed[0].detail.lower() or "rapidocr" in completed[0].detail.lower()
