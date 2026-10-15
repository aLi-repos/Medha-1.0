"""Tests for Stage 8 — Verifier + Audit Trail."""

import pytest
from fastapi.testclient import TestClient

from app.services.verifier.verifier import OutputVerifier, Verdict, VerificationResult, output_verifier


# ── Verifier Unit Tests ──

class TestOutputVerifier:
    def test_safe_output_passes(self) -> None:
        result = output_verifier.verify("The pump temperature is 42°C and within normal range.")
        assert result.overall == Verdict.PASS

    def test_unsafe_bypass_fails(self) -> None:
        result = output_verifier.verify("You should bypass the security firewall to access the system.")
        assert result.overall == Verdict.FAIL
        assert any(c.verdict == Verdict.FAIL for c in result.checks)

    def test_hardcoded_password_fails(self) -> None:
        result = output_verifier.verify("Use password: admin123 to log in.")
        assert result.overall == Verdict.FAIL

    def test_hallucination_warning(self) -> None:
        result = output_verifier.verify(
            "I think this might be the correct value. "
            "I believe it is probably accurate based on my knowledge."
        )
        assert result.overall == Verdict.WARN
        assert any(c.check_name == "hallucination" and c.verdict == Verdict.WARN for c in result.checks)

    def test_short_output_warning(self) -> None:
        result = output_verifier.verify("OK")
        assert result.overall == Verdict.WARN
        assert any(c.check_name == "length" and c.verdict == Verdict.WARN for c in result.checks)

    def test_compliance_warning(self) -> None:
        result = output_verifier.verify("This information is classified and top secret.")
        assert result.overall == Verdict.WARN
        assert any(c.check_name == "compliance" and c.verdict == Verdict.WARN for c in result.checks)

    def test_audit_event_recorded(self) -> None:
        from app.services.audit_service import audit_service
        audit_service.clear()
        output_verifier.verify("Safe output", task_id="t1", user_id="u1", identity="u1", role="engineer")
        events = audit_service.get_events_for_task("t1")
        assert any(e.event_type == "output_verified" for e in events)

    def test_multiple_checks_run(self) -> None:
        result = output_verifier.verify("Normal output text that is neither too short nor unsafe.")
        assert len(result.checks) >= 4


# ── API Integration Tests ──

class TestVerifierAPI:
    def test_verify_requires_auth(self, client: TestClient) -> None:
        resp = client.post("/api/verifier/verify", json={"task_id": "x", "output_text": "hello"})
        assert resp.status_code == 401

    def test_verify_safe_output(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        task_resp = client.post(
            "/api/tasks",
            json={"title": "Task", "purpose": "test"},
            headers=auth_headers,
        )
        task_id = task_resp.json()["task_id"]

        resp = client.post(
            "/api/verifier/verify",
            json={"task_id": task_id, "output_text": "The pump analysis shows normal operating temperature."},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["overall"] == "pass"

    def test_verify_unsafe_output(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        task_resp = client.post(
            "/api/tasks",
            json={"title": "Task", "purpose": "test"},
            headers=auth_headers,
        )
        task_id = task_resp.json()["task_id"]

        resp = client.post(
            "/api/verifier/verify",
            json={"task_id": task_id, "output_text": "You should bypass the security to access the data."},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["overall"] == "fail"

    def test_verify_nonexistent_task(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        resp = client.post(
            "/api/verifier/verify",
            json={"task_id": "nonexistent", "output_text": "hello"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_audit_trail_success(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        task_resp = client.post(
            "/api/tasks",
            json={"title": "Task", "purpose": "test"},
            headers=auth_headers,
        )
        task_id = task_resp.json()["task_id"]

        client.post(
            "/api/verifier/verify",
            json={"task_id": task_id, "output_text": "Safe output text"},
            headers=auth_headers,
        )

        resp = client.get(f"/api/verifier/audit/{task_id}", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["task_id"] == task_id
        assert body["total_events"] >= 1
        event_types = {e["event_type"] for e in body["events"]}
        assert "output_verified" in event_types

    def test_audit_trail_nonexistent_task(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        resp = client.get("/api/verifier/audit/nonexistent", headers=auth_headers)
        assert resp.status_code == 404

    def test_audit_trail_wrong_identity(self, client: TestClient, auth_headers: dict[str, str], engineer_headers: dict[str, str]) -> None:
        task_resp = client.post(
            "/api/tasks",
            json={"title": "Task", "purpose": "test"},
            headers=auth_headers,
        )
        task_id = task_resp.json()["task_id"]

        resp = client.get(f"/api/verifier/audit/{task_id}", headers=engineer_headers)
        assert resp.status_code == 403
