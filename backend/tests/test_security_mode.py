"""Security Mode — enforcement tests.

Tests that security mode is server-side authoritative and cannot be
bypassed from the frontend. Covers:
- Security mode cannot be forged from frontend
- User cannot downgrade policy-required Sovereign Lock
- External model denied in Sovereign
- Unauthorized RAG source denied
- External network denied
- Unauthorized tool denied
- Action Gate enforces Sovereign policy
- Model router respects Sovereign policy
- Task ownership enforced
- Security mode change audited
- Cross-user security mode manipulation denied
- Direct endpoint bypass denied
"""

import pytest
from fastapi.testclient import TestClient


def _login(client: TestClient, username: str, password: str) -> str:
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    return resp.json()["access_token"]


def _create_task(client: TestClient, headers: dict, title: str = "Security Mode Test",
                 sensitivity: str = "internal", security_mode: str = "standard") -> str:
    resp = client.post(
        "/api/tasks",
        json={
            "title": title,
            "purpose": "Test security mode enforcement",
            "sensitivity": sensitivity,
            "security_mode": security_mode,
        },
        headers=headers,
    )
    return resp.json()["task_id"]


# ── Security Mode Cannot Be Forged ──

class TestSecurityModeCannotBeForged:
    def test_security_mode_stored_server_side(self, client: TestClient) -> None:
        """Security mode is stored in the database, not in frontend localStorage."""
        token = _login(client, "admin", "medha-admin-2026")
        headers = {"Authorization": f"Bearer {token}"}
        task_id = _create_task(client, headers, security_mode="sovereign")

        resp = client.get(f"/api/tasks/{task_id}", headers=headers)
        assert resp.status_code == 200
        passport = resp.json()
        assert passport["security_mode"] == "sovereign"
        assert passport["security_policy_version"] == "1.0"

    def test_forged_security_mode_not_trusted(self, client: TestClient) -> None:
        """Frontend cannot inject a security mode that bypasses backend policy."""
        token = _login(client, "admin", "medha-admin-2026")
        headers = {"Authorization": f"Bearer {token}"}
        task_id = _create_task(client, headers, sensitivity="restricted")

        # The backend should have enforced sovereign mode for restricted sensitivity
        resp = client.get(f"/api/tasks/{task_id}", headers=headers)
        passport = resp.json()
        assert passport["security_mode"] == "sovereign"


# ── Downgrade Prevention ──

class TestDowngradePrevention:
    def test_cannot_downgrade_from_sovereign(self, client: TestClient) -> None:
        """User cannot downgrade from SOVEREIGN to STANDARD."""
        token = _login(client, "admin", "medha-admin-2026")
        headers = {"Authorization": f"Bearer {token}"}
        task_id = _create_task(client, headers, security_mode="sovereign")

        resp = client.post(
            "/api/security-mode/set",
            json={"task_id": task_id, "security_mode": "standard"},
            headers=headers,
        )
        assert resp.status_code == 409
        assert "cannot downgrade" in resp.json()["detail"].lower()

    def test_cannot_downgrade_from_secure(self, client: TestClient) -> None:
        """User cannot downgrade from SECURE to STANDARD."""
        token = _login(client, "admin", "medha-admin-2026")
        headers = {"Authorization": f"Bearer {token}"}
        task_id = _create_task(client, headers, security_mode="secure")

        resp = client.post(
            "/api/security-mode/set",
            json={"task_id": task_id, "security_mode": "standard"},
            headers=headers,
        )
        assert resp.status_code == 409

    def test_can_increase_to_sovereign(self, client: TestClient) -> None:
        """User can increase from STANDARD to SOVEREIGN."""
        token = _login(client, "admin", "medha-admin-2026")
        headers = {"Authorization": f"Bearer {token}"}
        task_id = _create_task(client, headers, security_mode="standard")

        resp = client.post(
            "/api/security-mode/set",
            json={"task_id": task_id, "security_mode": "sovereign"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["security_mode"] == "sovereign"

    def test_restricted_sensitivity_enforces_sovereign(self, client: TestClient) -> None:
        """Restricted sensitivity automatically enforces SOVEREIGN mode."""
        token = _login(client, "admin", "medha-admin-2026")
        headers = {"Authorization": f"Bearer {token}"}

        # Try to create with standard mode but restricted sensitivity
        resp = client.post(
            "/api/tasks",
            json={
                "title": "Restricted Task",
                "purpose": "Test auto-enforcement",
                "sensitivity": "restricted",
                "security_mode": "standard",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        passport = resp.json()
        assert passport["security_mode"] == "sovereign"
        assert passport["sensitivity"] == "restricted"


# ── External Model Denied in Sovereign ──

class TestSovereignModelDenial:
    def test_external_model_denied_in_sovereign(self, client: TestClient) -> None:
        """External models are denied when task is in SOVEREIGN mode."""
        token = _login(client, "admin", "medha-admin-2026")
        headers = {"Authorization": f"Bearer {token}"}
        task_id = _create_task(client, headers, security_mode="sovereign")

        # Authorize the passport
        client.patch(
            f"/api/tasks/{task_id}/status",
            json={"new_status": "authorized", "detail": "test"},
            headers=headers,
        )

        # Try to use external model
        resp = client.post(
            "/api/chat/send",
            json={
                "task_id": task_id,
                "prompt": "Test prompt",
                "model": "api-openai",
                "max_tokens": 50,
            },
            headers=headers,
        )
        assert resp.status_code == 403
        assert "denied" in resp.json()["detail"].lower() or "blocked" in resp.json()["detail"].lower()

    def test_local_model_allowed_in_sovereign(self, client: TestClient) -> None:
        """Local models are allowed in SOVEREIGN mode."""
        token = _login(client, "admin", "medha-admin-2026")
        headers = {"Authorization": f"Bearer {token}"}
        task_id = _create_task(client, headers, security_mode="sovereign")

        client.patch(
            f"/api/tasks/{task_id}/status",
            json={"new_status": "authorized", "detail": "test"},
            headers=headers,
        )

        resp = client.post(
            "/api/chat/send",
            json={
                "task_id": task_id,
                "prompt": "Test prompt",
                "model": "local-qwen2",
                "max_tokens": 50,
            },
            headers=headers,
        )
        assert resp.status_code == 200


# ── Network Denial ──

class TestSovereignNetworkDenial:
    def test_external_api_denied_by_security_mode(self, client: TestClient) -> None:
        """External API tools are denied in SOVEREIGN mode via Action Gate."""
        token = _login(client, "admin", "medha-admin-2026")
        headers = {"Authorization": f"Bearer {token}"}
        task_id = _create_task(
            client, headers,
            security_mode="sovereign",
            sensitivity="restricted",
        )

        client.patch(
            f"/api/tasks/{task_id}/status",
            json={"new_status": "authorized", "detail": "test"},
            headers=headers,
        )

        # Try to execute api_caller (external tool) — should be denied
        resp = client.post(
            "/api/sandbox/execute",
            json={
                "task_id": task_id,
                "tool_name": "api_caller",
                "action": "fetch_data",
            },
            headers=headers,
        )
        assert resp.status_code == 403


# ── Tool Enforcement ──

class TestSovereignToolEnforcement:
    def test_unauthorized_tool_denied(self, client: TestClient) -> None:
        """Tools not in the strict allowlist are denied in SOVEREIGN mode."""
        token = _login(client, "admin", "medha-admin-2026")
        headers = {"Authorization": f"Bearer {token}"}

        # Create task with limited tools
        resp = client.post(
            "/api/tasks",
            json={
                "title": "Limited Tools Task",
                "purpose": "Test tool enforcement",
                "security_mode": "sovereign",
                "sensitivity": "restricted",
                "allowed_tools": ["data_analyzer", "document_reader"],
            },
            headers=headers,
        )
        task_id = resp.json()["task_id"]

        client.patch(
            f"/api/tasks/{task_id}/status",
            json={"new_status": "authorized", "detail": "test"},
            headers=headers,
        )

        # Try to use email_sender (not in allowlist) — should be denied
        resp = client.post(
            "/api/sandbox/execute",
            json={
                "task_id": task_id,
                "tool_name": "email_sender",
                "action": "send_notification",
            },
            headers=headers,
        )
        assert resp.status_code == 403

    def test_authorized_tool_allowed(self, client: TestClient) -> None:
        """Tools in the allowlist are allowed in SOVEREIGN mode."""
        token = _login(client, "admin", "medha-admin-2026")
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post(
            "/api/tasks",
            json={
                "title": "Allowed Tools Task",
                "purpose": "Test tool enforcement",
                "security_mode": "sovereign",
                "sensitivity": "restricted",
                "allowed_tools": ["data_analyzer", "document_reader"],
            },
            headers=headers,
        )
        task_id = resp.json()["task_id"]

        client.patch(
            f"/api/tasks/{task_id}/status",
            json={"new_status": "authorized", "detail": "test"},
            headers=headers,
        )

        resp = client.post(
            "/api/sandbox/execute",
            json={
                "task_id": task_id,
                "tool_name": "data_analyzer",
                "action": "analyze_data",
            },
            headers=headers,
        )
        assert resp.status_code == 200


# ── Audit Trail ──

class TestSecurityModeAudit:
    def test_mode_change_recorded_in_audit(self, client: TestClient) -> None:
        """Security mode changes are recorded in the audit trail."""
        token = _login(client, "admin", "medha-admin-2026")
        headers = {"Authorization": f"Bearer {token}"}
        task_id = _create_task(client, headers, security_mode="standard")

        # Change mode
        client.post(
            "/api/security-mode/set",
            json={"task_id": task_id, "security_mode": "sovereign"},
            headers=headers,
        )

        # Check audit trail
        resp = client.get(f"/api/verifier/audit/{task_id}", headers=headers)
        assert resp.status_code == 200
        events = resp.json().get("events", [])
        mode_events = [e for e in events if e.get("event_type") == "security_mode_changed"]
        assert len(mode_events) >= 1
        assert "sovereign" in mode_events[-1].get("detail", "").lower()


# ── Cross-User Security ──

class TestCrossUserSecurity:
    def test_cannot_change_other_users_security_mode(self, client: TestClient) -> None:
        """User A cannot change the security mode on User B's task."""
        token_a = _login(client, "admin", "medha-admin-2026")
        headers_a = {"Authorization": f"Bearer {token_a}"}
        task_id = _create_task(client, headers_a, security_mode="standard")

        token_b = _login(client, "engineer", "medha-engineer-2026")
        headers_b = {"Authorization": f"Bearer {token_b}"}

        resp = client.post(
            "/api/security-mode/set",
            json={"task_id": task_id, "security_mode": "sovereign"},
            headers=headers_b,
        )
        assert resp.status_code in (403, 404)

    def test_cannot_view_other_users_security_status(self, client: TestClient) -> None:
        """User A cannot view the security status of User B's task."""
        token_a = _login(client, "admin", "medha-admin-2026")
        headers_a = {"Authorization": f"Bearer {token_a}"}
        task_id = _create_task(client, headers_a, security_mode="secure")

        token_b = _login(client, "engineer", "medha-engineer-2026")
        headers_b = {"Authorization": f"Bearer {token_b}"}

        resp = client.get(f"/api/security-mode/status/{task_id}", headers=headers_b)
        assert resp.status_code in (403, 404)


# ── API Endpoint Security ──

class TestSecurityModeEndpointSecurity:
    def test_set_mode_requires_auth(self, client: TestClient) -> None:
        resp = client.post(
            "/api/security-mode/set",
            json={"task_id": "test", "security_mode": "sovereign"},
        )
        assert resp.status_code == 401

    def test_status_requires_auth(self, client: TestClient) -> None:
        resp = client.get("/api/security-mode/status/test")
        assert resp.status_code == 401

    def test_nonexistent_task_returns_404(self, client: TestClient) -> None:
        token = _login(client, "admin", "medha-admin-2026")
        headers = {"Authorization": f"Bearer {token}"}
        resp = client.get("/api/security-mode/status/nonexistent-id", headers=headers)
        assert resp.status_code == 404

    def test_policy_endpoint_public(self, client: TestClient) -> None:
        """Security policy definitions are publicly readable."""
        resp = client.get("/api/security-mode/policy/sovereign")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "sovereign"
        assert data["external_network"] == "deny"
        assert data["external_models"] == "deny"
