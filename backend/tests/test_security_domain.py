"""
Security Domain Isolation tests.

Tests cover:
1. Standard/Secure/Sovereign mode selection via /auth/security-mode
2. Task gets correct security_mode classification
3. Secure tasks don't appear in Standard task history
4. Secure audit doesn't appear in Standard audit
5. Standard audit doesn't leak Secure records
6. Task creation uses user's preferred mode
7. User cannot forge security mode via task creation
8. Security mode changes are audited
9. Direct API calls respect security domain
10. Cross-user secure task access denied
"""

import pytest
from fastapi.testclient import TestClient

from tests.conftest import _login


# --- Helpers ---

def _get_me(client: TestClient, token: str) -> dict:
    return client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()


def _set_user_mode(client: TestClient, token: str, mode: str):
    return client.patch(
        "/api/auth/security-mode",
        json={"security_mode": mode},
        headers={"Authorization": f"Bearer {token}"},
    )


def _get_user_mode(client: TestClient, token: str):
    return client.get(
        "/api/auth/security-mode",
        headers={"Authorization": f"Bearer {token}"},
    )


def _create_task(client: TestClient, token: str, title: str, sensitivity: str = "internal", security_mode: str = "standard"):
    return client.post(
        "/api/tasks",
        json={
            "title": title,
            "purpose": f"Test: {title}",
            "sensitivity": sensitivity,
            "security_mode": security_mode,
        },
        headers={"Authorization": f"Bearer {token}"},
    )


def _list_tasks(client: TestClient, token: str, security_mode: str | None = None):
    params = f"?security_mode={security_mode}" if security_mode else ""
    return client.get(
        f"/api/tasks{params}",
        headers={"Authorization": f"Bearer {token}"},
    )


def _get_audit_summary(client: TestClient, token: str, security_mode: str | None = None):
    params = f"?security_mode={security_mode}" if security_mode else ""
    return client.get(
        f"/api/verifier/audit{params}",
        headers={"Authorization": f"Bearer {token}"},
    )


# --- Tests ---

class TestModeSelection:
    """1-3: Mode selection works and persists."""

    def test_get_default_mode(self, client: TestClient, engineer_token: str):
        resp = _get_user_mode(client, engineer_token)
        assert resp.status_code == 200
        data = resp.json()
        assert data["security_mode"] == "standard"

    def test_set_secure_mode(self, client: TestClient, engineer_token: str):
        resp = _set_user_mode(client, engineer_token, "secure")
        assert resp.status_code == 200
        data = resp.json()
        assert data["security_mode"] == "secure"
        assert data["previous_mode"] == "standard"

    def test_set_sovereign_mode(self, client: TestClient, engineer_token: str):
        resp = _set_user_mode(client, engineer_token, "sovereign")
        assert resp.status_code == 200
        data = resp.json()
        assert data["security_mode"] == "sovereign"

    def test_invalid_mode_rejected(self, client: TestClient, engineer_token: str):
        resp = _set_user_mode(client, engineer_token, "invalid")
        assert resp.status_code == 422

    def test_mode_persists_across_requests(self, client: TestClient, engineer_token: str):
        _set_user_mode(client, engineer_token, "secure")
        resp = _get_user_mode(client, engineer_token)
        assert resp.json()["security_mode"] == "secure"


class TestTaskClassification:
    """4-6: Tasks get correct security_mode from user preference."""

    def test_task_inherits_user_preferred_mode(self, client: TestClient, engineer_token: str):
        _set_user_mode(client, engineer_token, "secure")
        resp = _create_task(client, engineer_token, "Secure Task Alpha")
        assert resp.status_code == 201
        data = resp.json()
        assert data["security_mode"] == "secure"

    def test_sovereign_sensitivity_forces_sovereign(self, client: TestClient, engineer_token: str):
        _set_user_mode(client, engineer_token, "standard")
        resp = _create_task(client, engineer_token, "Restricted Task", sensitivity="restricted")
        assert resp.status_code == 201
        assert resp.json()["security_mode"] == "sovereign"

    def test_confidential_sensitivity_forces_secure(self, client: TestClient, engineer_token: str):
        _set_user_mode(client, engineer_token, "standard")
        resp = _create_task(client, engineer_token, "Confidential Task", sensitivity="confidential")
        assert resp.status_code == 201
        assert resp.json()["security_mode"] == "secure"


class TestDomainIsolation:
    """7-9: Secure tasks don't appear in Standard history."""

    def test_standard_mode_hides_secure_tasks(self, client: TestClient, engineer_token: str):
        _set_user_mode(client, engineer_token, "standard")
        std_resp = _create_task(client, engineer_token, "Standard Task Dom")
        standard_task_id = std_resp.json()["task_id"]
        _set_user_mode(client, engineer_token, "secure")
        sec_resp = _create_task(client, engineer_token, "Secure Task Dom")
        secure_task_id = sec_resp.json()["task_id"]

        resp = _list_tasks(client, engineer_token, "standard")
        assert resp.status_code == 200
        tasks = resp.json()
        task_ids = [t["task_id"] for t in tasks]
        assert standard_task_id in task_ids
        assert secure_task_id not in task_ids

    def test_secure_mode_shows_only_secure_tasks(self, client: TestClient, engineer_token: str):
        _set_user_mode(client, engineer_token, "standard")
        std_resp = _create_task(client, engineer_token, "Standard Task Dom2")
        standard_task_id = std_resp.json()["task_id"]
        _set_user_mode(client, engineer_token, "secure")
        sec_resp = _create_task(client, engineer_token, "Secure Task Dom2")
        secure_task_id = sec_resp.json()["task_id"]

        resp = _list_tasks(client, engineer_token, "secure")
        assert resp.status_code == 200
        tasks = resp.json()
        task_ids = [t["task_id"] for t in tasks]
        assert secure_task_id in task_ids
        assert standard_task_id not in task_ids

    def test_no_filter_shows_all_tasks(self, client: TestClient, engineer_token: str):
        _set_user_mode(client, engineer_token, "standard")
        std_resp = _create_task(client, engineer_token, "Standard Task Dom3")
        standard_task_id = std_resp.json()["task_id"]
        _set_user_mode(client, engineer_token, "secure")
        sec_resp = _create_task(client, engineer_token, "Secure Task Dom3")
        secure_task_id = sec_resp.json()["task_id"]

        resp = _list_tasks(client, engineer_token)
        assert resp.status_code == 200
        tasks = resp.json()
        task_ids = [t["task_id"] for t in tasks]
        assert standard_task_id in task_ids
        assert secure_task_id in task_ids


class TestAuditIsolation:
    """10-12: Audit trail filtered by security domain."""

    def test_standard_audit_excludes_secure_tasks(self, client: TestClient, engineer_token: str):
        # Create standard task
        _set_user_mode(client, engineer_token, "standard")
        std_resp = _create_task(client, engineer_token, "Std Audit Task")
        std_id = std_resp.json()["task_id"]

        # Create secure task
        _set_user_mode(client, engineer_token, "secure")
        sec_resp = _create_task(client, engineer_token, "Sec Audit Task")
        sec_id = sec_resp.json()["task_id"]

        # Standard audit should only show standard task
        resp = _get_audit_summary(client, engineer_token, "standard")
        assert resp.status_code == 200
        tasks = resp.json()["tasks"]
        task_ids = [t["task_id"] for t in tasks]
        assert std_id in task_ids
        assert sec_id not in task_ids

    def test_secure_audit_excludes_standard_tasks(self, client: TestClient, engineer_token: str):
        _set_user_mode(client, engineer_token, "standard")
        std_resp = _create_task(client, engineer_token, "Std Audit2")
        std_id = std_resp.json()["task_id"]

        _set_user_mode(client, engineer_token, "secure")
        sec_resp = _create_task(client, engineer_token, "Sec Audit2")
        sec_id = sec_resp.json()["task_id"]

        resp = _get_audit_summary(client, engineer_token, "secure")
        assert resp.status_code == 200
        tasks = resp.json()["tasks"]
        task_ids = [t["task_id"] for t in tasks]
        assert sec_id in task_ids
        assert std_id not in task_ids


class TestModeChangeAudit:
    """13: Security mode changes are audited."""

    def test_mode_change_recorded(self, client: TestClient, engineer_token: str):
        _set_user_mode(client, engineer_token, "secure")
        from app.services.audit_service import audit_service
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            from app.models.audit import AuditEventRow
            rows = db.query(AuditEventRow).filter(
                AuditEventRow.event_type == "security_mode_changed"
            ).all()
            assert len(rows) >= 1
        finally:
            db.close()


class TestCrossUserIsolation:
    """14: Cross-user secure task access denied."""

    def test_user_b_cannot_see_user_a_secure_tasks(self, client: TestClient, engineer_token: str):
        # User A (engineer) creates secure task
        _set_user_mode(client, engineer_token, "secure")
        resp = _create_task(client, engineer_token, "User A Secure Task")
        task_id = resp.json()["task_id"]

        # User B (operator) lists tasks — should not see User A's task
        _set_user_mode(client, client.post("/api/auth/login", json={"username": "operator", "password": "medha-operator-2026"}).json()["access_token"], "secure")
        op_token = _login(client, "operator", "medha-operator-2026")
        resp = _list_tasks(client, op_token, "secure")
        assert resp.status_code == 200
        task_ids = [t["task_id"] for t in resp.json()]
        assert task_id not in task_ids


class TestFrontendCannotForge:
    """15-16: Frontend cannot forge security mode or identity."""

    def test_task_creation_uses_server_preferred_mode(self, client: TestClient, engineer_token: str):
        """Even if frontend sends security_mode=standard, the server uses the user's preferred mode."""
        _set_user_mode(client, engineer_token, "secure")
        resp = _create_task(client, engineer_token, "Forge Test", security_mode="standard")
        assert resp.status_code == 201
        assert resp.json()["security_mode"] == "secure"

    def test_unauthenticated_mode_change_rejected(self, client: TestClient):
        resp = client.patch(
            "/api/auth/security-mode",
            json={"security_mode": "secure"},
        )
        assert resp.status_code == 401


class TestPolicyEnforcement:
    """17: User cannot downgrade below sensitivity-required mode."""

    def test_cannot_create_standard_restricted_task(self, client: TestClient, engineer_token: str):
        _set_user_mode(client, engineer_token, "standard")
        resp = _create_task(client, engineer_token, "Restricted Downgrade", sensitivity="restricted")
        assert resp.status_code == 201
        # Should be upgraded to sovereign
        assert resp.json()["security_mode"] == "sovereign"


class TestDirectApiRespectsDomain:
    """19-20: Direct API calls respect security domain filtering."""

    def test_task_list_api_filters_by_mode(self, client: TestClient, engineer_token: str):
        _set_user_mode(client, engineer_token, "standard")
        _create_task(client, engineer_token, "Direct API Standard")
        _set_user_mode(client, engineer_token, "secure")
        _create_task(client, engineer_token, "Direct API Secure")

        resp_standard = client.get(
            "/api/tasks?security_mode=standard",
            headers={"Authorization": f"Bearer {engineer_token}"},
        )
        resp_secure = client.get(
            "/api/tasks?security_mode=secure",
            headers={"Authorization": f"Bearer {engineer_token}"},
        )

        std_titles = [t["title"] for t in resp_standard.json()]
        sec_titles = [t["title"] for t in resp_secure.json()]

        assert "Direct API Standard" in std_titles
        assert "Direct API Secure" not in std_titles
        assert "Direct API Secure" in sec_titles
        assert "Direct API Standard" not in sec_titles
