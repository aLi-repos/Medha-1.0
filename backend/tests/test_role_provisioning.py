"""
Role provisioning and automatic security-mode tests.

Mapping (configurable via app.core.config.DEFAULT_ROLE_SECURITY_MODES /
MEDHA_ROLE_SECURITY_MODES):
    operator        -> standard
    engineer        -> standard
    senior_engineer -> sovereign
    manager         -> sovereign
    admin           -> sovereign
    hr              -> secure
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import security_mode_for_role
from app.schemas.auth import Role
from app.services.user_service import user_service
from app.core.database import SessionLocal
from tests.conftest import _login


def _me(client: TestClient, token: str) -> dict:
    return client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()


def _get_mode(client: TestClient, token: str) -> dict:
    return client.get(
        "/api/auth/security-mode", headers={"Authorization": f"Bearer {token}"}
    ).json()


def _set_mode(client: TestClient, token: str, mode: str):
    return client.patch(
        "/api/auth/security-mode",
        json={"security_mode": mode},
        headers={"Authorization": f"Bearer {token}"},
    )


def _provision(user_id: str, username: str, password: str, role: Role) -> None:
    db = SessionLocal()
    try:
        if user_service.get_by_user_id(db, user_id) is None:
            user_service.register(db, username, password, role, user_id=user_id)
    finally:
        db.close()


@pytest.fixture()
def provisioned_users(client: TestClient) -> None:
    """Create the four required org-provisioned test accounts."""
    _provision("USR-001", "org.operator", "pass-operator-1", Role.OPERATOR)
    _provision("USR-002", "org.senior", "pass-senior-2", Role.SENIOR_ENGINEER)
    _provision("USR-003", "org.manager", "pass-manager-3", Role.MANAGER)
    _provision("USR-004", "org.admin", "pass-admin-4", Role.ADMIN)


class TestRoleSecurityMapping:
    def test_configured_mapping(self):
        assert security_mode_for_role("operator") == "standard"
        assert security_mode_for_role("engineer") == "standard"
        assert security_mode_for_role("senior_engineer") == "sovereign"
        assert security_mode_for_role("manager") == "sovereign"
        assert security_mode_for_role("admin") == "sovereign"
        assert security_mode_for_role("hr") == "secure"

    @pytest.mark.parametrize(
        "user_id,username,password,role,expected_mode",
        [
            ("USR-001", "org.operator", "pass-operator-1", "operator", "standard"),
            ("USR-002", "org.senior", "pass-senior-2", "senior_engineer", "sovereign"),
            ("USR-003", "org.manager", "pass-manager-3", "manager", "sovereign"),
            ("USR-004", "org.admin", "pass-admin-4", "admin", "sovereign"),
        ],
    )
    def test_login_effective_security_mode(
        self, client, provisioned_users, user_id, username, password, role, expected_mode
    ):
        token = _login(client, username, password)
        me = _me(client, token)
        assert me["user_id"] == user_id
        assert me["role"] == role
        assert me["preferred_security_mode"] == expected_mode
        mode_data = _get_mode(client, token)
        assert mode_data["security_mode"] == expected_mode
        assert mode_data["role_floor"] == expected_mode


class TestRoleAndUserIdReadonly:
    def test_role_cannot_be_edited_by_user(self, client, provisioned_users):
        token = _login(client, "org.admin", "pass-admin-4")
        resp = client.patch(
            "/api/auth/role",
            json={"role": "operator"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (404, 405)
        assert _me(client, token)["role"] == "admin"

    def test_user_id_cannot_be_edited(self, client, provisioned_users):
        token = _login(client, "org.operator", "pass-operator-1")
        # No endpoint accepts a user_id change; /username only changes username.
        resp = client.patch(
            "/api/auth/username",
            json={"username": "org.operator.renamed"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "USR-001"
        assert resp.json()["role"] == "operator"

    def test_register_rejects_unauthorized_user_id(self, client):
        resp = client.post(
            "/api/auth/register",
            json={
                "username": "role.spoof",
                "password": "spoof-pass-1",
                "role": "admin",
                "user_id": "USR-009",
            },
        )
        assert resp.status_code == 403

    def test_register_rejects_wrong_uid_role_combination(self, client):
        resp = client.post(
            "/api/auth/register",
            json={
                "username": "nagarjuna",
                "password": "se-pass-2026",
                "role": "admin",
                "user_id": "SE00503",
            },
        )
        assert resp.status_code == 403

    def test_register_provisions_authorized_org_record(self, client):
        resp = client.post(
            "/api/auth/register",
            json={
                "username": "nagarjuna",
                "password": "se-pass-2026",
                "role": "senior_engineer",
                "user_id": "SE00503",
            },
        )
        # SE00503 is seeded at startup, so a fresh register is a conflict;
        # the seeded account must already exist with the correct role.
        if resp.status_code == 201:
            me = _me(client, resp.json()["access_token"])
            assert me["user_id"] == "SE00503"
            assert me["role"] == "senior_engineer"
        else:
            assert resp.status_code == 409
            token = _login(client, "nagarjuna", "medha-nagarjuna-2026")
            me = _me(client, token)
            assert me["user_id"] == "SE00503"
            assert me["role"] == "senior_engineer"


class TestUsernameAndPasswordEdits:
    def test_username_edit_preserves_identity_and_data(
        self, client, provisioned_users
    ):
        token = _login(client, "org.operator", "pass-operator-1")
        task = client.post(
            "/api/tasks",
            json={"title": "Before account edit", "purpose": "identity continuity"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert task.status_code == 201
        task_id = task.json()["task_id"]

        rename = client.patch(
            "/api/auth/username",
            json={"username": "org.operator.v2"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert rename.status_code == 200
        assert rename.json()["user_id"] == "USR-001"
        assert rename.json()["role"] == "operator"

        new_token = _login(client, "org.operator.v2", "pass-operator-1")
        me = _me(client, new_token)
        assert me["user_id"] == "USR-001"
        assert me["role"] == "operator"
        assert me["preferred_security_mode"] == "standard"

        tasks = client.get(
            "/api/tasks", headers={"Authorization": f"Bearer {new_token}"}
        ).json()
        assert any(t["task_id"] == task_id for t in tasks)

    def test_password_change_preserves_identity_and_allows_new_login(
        self, client, provisioned_users
    ):
        token = _login(client, "org.manager", "pass-manager-3")
        me_before = _me(client, token)
        assert me_before["user_id"] == "USR-003"
        assert me_before["role"] == "manager"

        # Wrong current password rejected.
        bad = client.patch(
            "/api/auth/password",
            json={"current_password": "wrong-pass", "new_password": "new-pass-333"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert bad.status_code == 409

        ok = client.patch(
            "/api/auth/password",
            json={"current_password": "pass-manager-3", "new_password": "new-pass-333"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert ok.status_code == 200
        assert ok.json()["user_id"] == "USR-003"
        assert ok.json()["role"] == "manager"

        # Old password no longer works; new password does; identity unchanged.
        old_resp = client.post(
            "/api/auth/login",
            json={"username": "org.manager", "password": "pass-manager-3"},
        )
        assert old_resp.status_code == 401

        new_token = _login(client, "org.manager", "new-pass-333")
        me_after = _me(client, new_token)
        assert me_after["user_id"] == "USR-003"
        assert me_after["role"] == "manager"
        assert me_after["username"] == "org.manager"
        assert me_after["preferred_security_mode"] == "sovereign"


class TestSecurityModeFloor:
    def test_user_cannot_lower_below_role_floor(self, client, provisioned_users):
        token = _login(client, "org.admin", "pass-admin-4")
        resp = _set_mode(client, token, "standard")
        assert resp.status_code == 422
        assert "role" in resp.json()["detail"].lower()
        assert _get_mode(client, token)["security_mode"] == "sovereign"

    def test_hr_cannot_lower_to_standard(self, client):
        _provision("USR-010", "org.hr", "pass-hr-10", Role.HR)
        token = _login(client, "org.hr", "pass-hr-10")
        assert _me(client, token)["preferred_security_mode"] == "secure"
        resp = _set_mode(client, token, "standard")
        assert resp.status_code == 422

    def test_user_may_increase_above_role_floor(self, client, provisioned_users):
        token = _login(client, "org.operator", "pass-operator-1")
        resp = _set_mode(client, token, "sovereign")
        assert resp.status_code == 200
        assert resp.json()["security_mode"] == "sovereign"

    def test_frontend_cannot_force_lower_mode(self, client, provisioned_users):
        """Server ignores client-supplied lower mode for a sovereign-floor role."""
        token = _login(client, "org.senior", "pass-senior-2")
        # Client tries to send security_mode=standard at PATCH — rejected.
        resp = _set_mode(client, token, "standard")
        assert resp.status_code == 422
        # Task creation with security_mode=standard still resolves to role floor.
        task = client.post(
            "/api/tasks",
            json={
                "title": "Forged standard task",
                "purpose": "try to escape sovereign floor",
                "security_mode": "standard",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        # Senior engineer is not in the create-task RBAC list (operator/engineer/admin);
        # either 403 or a passport whose mode is not below the role floor is acceptable.
        if task.status_code == 201:
            assert task.json()["security_mode"] in ("secure", "sovereign")
        else:
            assert task.status_code == 403

    def test_task_sensitivity_still_requires_higher_than_user_default(
        self, client, provisioned_users
    ):
        """Operator default is standard; restricted sensitivity forces sovereign."""
        token = _login(client, "org.operator", "pass-operator-1")
        assert _get_mode(client, token)["security_mode"] == "standard"
        task = client.post(
            "/api/tasks",
            json={
                "title": "Restricted by sensitivity",
                "purpose": "task-level floor above user default",
                "sensitivity": "restricted",
                "security_mode": "standard",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert task.status_code == 201
        assert task.json()["security_mode"] == "sovereign"


class TestExistingDemoUsersPreserved:
    def test_demo_users_and_data_still_work(self, client):
        token = _login(client, "operator", "medha-operator-2026")
        me = _me(client, token)
        assert me["user_id"] == "USR-00000001"
        assert me["role"] == "operator"
        assert me["preferred_security_mode"] == "standard"

        admin_token = _login(client, "admin", "medha-admin-2026")
        admin_me = _me(client, admin_token)
        assert admin_me["user_id"] == "USR-00000004"
        assert admin_me["role"] == "admin"
        assert admin_me["preferred_security_mode"] == "sovereign"
