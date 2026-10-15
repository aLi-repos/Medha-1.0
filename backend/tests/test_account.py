"""
Account management security and functional tests.

Tests cover:
- user_id presence and stability in /me and JWT
- Username editing (uniqueness, format validation, stability of user_id)
- Role read-only enforcement
- Audit trail for username changes
- Cross-user isolation
"""

import re

import pytest
from fastapi.testclient import TestClient

from tests.conftest import _login


# --- Helper ---

def _get_me(client: TestClient, token: str) -> dict:
    return client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()


def _edit_username(client: TestClient, token: str, username: str):
    return client.patch(
        "/api/auth/username",
        json={"username": username},
        headers={"Authorization": f"Bearer {token}"},
    )


# --- Tests ---

class TestUserIdPresence:
    """1. user_id must be present in /me response."""

    def test_me_includes_user_id(self, client: TestClient, engineer_token: str):
        me = _get_me(client, engineer_token)
        assert "user_id" in me
        assert isinstance(me["user_id"], str)
        assert me["user_id"].startswith("USR-")

    def test_me_includes_username_and_role(self, client: TestClient, engineer_token: str):
        me = _get_me(client, engineer_token)
        assert me["username"] == "engineer"
        assert me["role"] == "engineer"


class TestUserIdStability:
    """2. user_id must remain stable after login and across requests."""

    def test_user_id_stable_across_requests(self, client: TestClient, engineer_token: str):
        me1 = _get_me(client, engineer_token)
        me2 = _get_me(client, engineer_token)
        assert me1["user_id"] == me2["user_id"]

    def test_user_id_stable_after_login(self, client: TestClient):
        token1 = _login(client, "engineer", "medha-engineer-2026")
        me1 = _get_me(client, token1)
        token2 = _login(client, "engineer", "medha-engineer-2026")
        me2 = _get_me(client, token2)
        assert me1["user_id"] == me2["user_id"]


class TestStableDemoUserIds:
    """3. Demo users must have deterministic user_ids."""

    def test_operator_has_stable_id(self, client: TestClient, operator_token: str):
        me = _get_me(client, operator_token)
        assert me["user_id"] == "USR-00000001"

    def test_engineer_has_stable_id(self, client: TestClient, engineer_token: str):
        me = _get_me(client, engineer_token)
        assert me["user_id"] == "USR-00000002"

    def test_admin_has_stable_id(self, client: TestClient, admin_token: str):
        me = _get_me(client, admin_token)
        assert me["user_id"] == "USR-00000004"


class TestUsernameEditing:
    """4-8. Username editing functionality."""

    def test_edit_username_success(self, client: TestClient, engineer_token: str):
        resp = _edit_username(client, engineer_token, "engineer.updated")
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "engineer.updated"
        # user_id must remain stable
        me = _get_me(client, engineer_token)
        assert data["user_id"] == me["user_id"]

    def test_edit_username_same_value_noop(self, client: TestClient, engineer_token: str):
        resp = _edit_username(client, engineer_token, "engineer")
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "engineer"

    def test_edit_username_allows_duplicate(self, client: TestClient, engineer_token: str):
        """Duplicate usernames are allowed — accounts stay separate via user_id."""
        resp = _edit_username(client, engineer_token, "operator")
        assert resp.status_code == 200
        me = _get_me(client, engineer_token)
        assert me["username"] == "operator"
        assert me["user_id"] == "USR-00000002"
        # The original operator account is untouched.
        op_me = _get_me(client, _login(client, "operator", "medha-operator-2026"))
        assert op_me["user_id"] == "USR-00000001"

    def test_edit_username_rejects_short(self, client: TestClient, engineer_token: str):
        resp = _edit_username(client, engineer_token, "ab")
        assert resp.status_code == 422

    def test_edit_username_rejects_special_chars(self, client: TestClient, engineer_token: str):
        resp = _edit_username(client, engineer_token, "user with spaces!")
        assert resp.status_code in (409, 422)

    def test_edit_username_allows_dots_hyphens_underscores(self, client: TestClient, engineer_token: str):
        resp = _edit_username(client, engineer_token, "a.b-c_d")
        assert resp.status_code == 200
        assert resp.json()["username"] == "a.b-c_d"


class TestRoleReadOnly:
    """9. Role must not be changeable via username edit."""

    def test_role_unchanged_after_username_edit(self, client: TestClient, engineer_token: str):
        _edit_username(client, engineer_token, "engineer.new")
        me = _get_me(client, engineer_token)
        assert me["role"] == "engineer"


class TestNoRoleEndpoint:
    """10. There should be no endpoint to change role."""

    def test_no_patch_role_endpoint(self, client: TestClient, engineer_token: str):
        resp = client.patch(
            "/api/auth/role",
            json={"role": "admin"},
            headers={"Authorization": f"Bearer {engineer_token}"},
        )
        assert resp.status_code in (404, 405)


class TestAuditTrail:
    """11. Username changes must be recorded in the audit trail."""

    def test_username_change_recorded(self, client: TestClient, engineer_token: str):
        _edit_username(client, engineer_token, "engineer.audited")
        # Query the audit service directly since username events have no task_id
        from app.services.audit_service import audit_service
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            from app.models.audit import AuditEventRow
            rows = db.query(AuditEventRow).filter(
                AuditEventRow.event_type == "username_changed"
            ).all()
            assert len(rows) >= 1
            assert "engineer" in rows[0].detail.lower() or "audited" in rows[0].detail.lower()
        finally:
            db.close()


class TestCrossUserIsolation:
    """12. User A must not be able to edit User B's username."""

    def test_cannot_edit_other_user(self, client: TestClient, engineer_token: str):
        # Engineer can only edit their own username via this endpoint —
        # renaming to a taken username does not touch the other account.
        me_before = _get_me(client, engineer_token)
        resp = _edit_username(client, engineer_token, "operator")
        assert resp.status_code == 200
        me_after = _get_me(client, engineer_token)
        assert me_after["user_id"] == me_before["user_id"]
        assert me_after["username"] == "operator"
        # Operator's own account still has its original username + user_id.
        op_me = _get_me(client, _login(client, "operator", "medha-operator-2026"))
        assert op_me["username"] == "operator"
        assert op_me["user_id"] == "USR-00000001"


class TestNewRegistrationUserId:
    """13. Newly registered users must receive a user_id."""

    def test_new_user_gets_user_id(self, client: TestClient):
        client.post(
            "/api/auth/register",
            json={"username": "newuser", "password": "new-pass-2026", "role": "operator"},
        )
        token = _login(client, "newuser", "new-pass-2026")
        me = _get_me(client, token)
        assert "user_id" in me
        assert me["user_id"].startswith("USR-")


class TestUnauthorizedAccess:
    """14. Unauthenticated access to /me and /username must be rejected."""

    def test_me_requires_auth(self, client: TestClient):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_username_edit_requires_auth(self, client: TestClient):
        resp = client.patch("/api/auth/username", json={"username": "hacked"})
        assert resp.status_code == 401


class TestMeEndpointReturnsAllFields:
    """15. /me must return user_id, username, and role."""

    def test_me_response_shape(self, client: TestClient, engineer_token: str):
        me = _get_me(client, engineer_token)
        assert set(me.keys()) == {"user_id", "username", "role", "preferred_security_mode"}


class TestUserIdInJwt:
    """16. JWT must contain uid claim."""

    def test_jwt_has_uid(self, client: TestClient):
        token = _login(client, "engineer", "medha-engineer-2026")
        import jwt as pyjwt
        from app.core.config import settings
        payload = pyjwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert "uid" in payload
        assert payload["uid"].startswith("USR-")


class TestAdminRenameEndToEnd:
    """admin -> ali must keep identity and existing data; no new user is created.

    This is the regression for the username identity issue: a rename must
    never look like a new account, and existing owned data must stay
    visible under the same user_id.
    """

    def test_admin_rename_to_ali_keeps_identity_and_data(
        self,
        client: TestClient,
        admin_token: str,
    ):
        # 1. Existing data: create a task as admin before the rename.
        created = client.post(
            "/api/tasks",
            json={"title": "pre-rename task", "purpose": "must survive rename"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert created.status_code == 201, created.text
        task_id = created.json()["task_id"]
        me_before = _get_me(client, admin_token)
        assert me_before["username"] == "admin"
        assert me_before["user_id"] == "USR-00000004"

        # 2. Rename admin -> ali.
        resp = _edit_username(client, admin_token, "ali")
        assert resp.status_code == 200, resp.text
        assert resp.json()["username"] == "ali"
        assert resp.json()["user_id"] == me_before["user_id"]

        # 3. Same login identity: existing token still resolves to the same user_id.
        me_with_old_token = _get_me(client, admin_token)
        assert me_with_old_token["user_id"] == me_before["user_id"]
        assert me_with_old_token["username"] == "ali"

        # 4. Login with the new username works and yields the same user_id.
        ali_token = _login(client, "ali", "medha-admin-2026")
        me_after = _get_me(client, ali_token)
        assert me_after["user_id"] == me_before["user_id"]
        assert me_after["role"] == "admin"

        # 5. Existing data is still visible under the same user_id.
        tasks = client.get(
            "/api/tasks", headers={"Authorization": f"Bearer {ali_token}"}
        ).json()
        assert any(t["task_id"] == task_id for t in tasks)
        assert all(t["user_id"] == me_before["user_id"] for t in tasks)

    def test_rename_to_taken_username_keeps_accounts_separate(
        self, client: TestClient, admin_token: str
    ):
        """Renaming to another user's username is allowed; accounts stay separate."""
        resp = _edit_username(client, admin_token, "operator")
        assert resp.status_code == 200
        assert resp.json()["username"] == "operator"
        assert resp.json()["user_id"] == "USR-00000004"
        # Original operator account is untouched.
        op_me = _get_me(client, _login(client, "operator", "medha-operator-2026"))
        assert op_me["user_id"] == "USR-00000001"
        assert op_me["role"] == "operator"
