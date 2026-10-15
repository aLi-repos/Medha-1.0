"""Supervisory trace oversight + provisioned demo users."""

from fastapi.testclient import TestClient

from app.core.config import security_mode_for_role
from app.services.user_service import user_service
from app.core.database import SessionLocal
from app.schemas.auth import Role


def _login(client: TestClient, username: str, password: str) -> str:
    resp = client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _me(client: TestClient, token: str) -> dict:
    return client.get("/api/auth/me", headers=_h(token)).json()


def _create_task(client: TestClient, token: str, title: str) -> dict:
    resp = client.post(
        "/api/tasks",
        json={"title": title, "purpose": "oversight test"},
        headers=_h(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestSeededDemoUsers:
    def test_six_org_users_login_with_correct_roles(self, client: TestClient) -> None:
        cases = [
            ("nagarjuna", "medha-nagarjuna-2026", "SE00503", "senior_engineer"),
            ("lokesh", "medha-lokesh-2026", "AD00637", "admin"),
            ("Ali", "medha-ali-2026", "MD00574", "manager"),
            ("Balaji", "medha-balaji-2026", "OP00303", "operator"),
            ("keerthi", "medha-keerthi-2026", "JE00589", "junior_engineer"),
            ("saniya", "medha-saniya-2026", "MO00579", "monitor"),
        ]
        for username, password, uid, role in cases:
            token = _login(client, username, password)
            me = _me(client, token)
            assert me["user_id"] == uid
            assert me["role"] == role

    def test_seed_is_idempotent(self, client: TestClient) -> None:
        db = SessionLocal()
        try:
            before = db.query(__import__("app.models.user", fromlist=["UserRow"]).UserRow).count()
            user_service.seed_demo_users(db)
            after = db.query(__import__("app.models.user", fromlist=["UserRow"]).UserRow).count()
            assert before == after
        finally:
            db.close()

    def test_security_mode_mapping(self) -> None:
        assert security_mode_for_role("operator") == "standard"
        assert security_mode_for_role("junior_engineer") == "standard"
        assert security_mode_for_role("senior_engineer") == "sovereign"
        assert security_mode_for_role("manager") == "sovereign"
        assert security_mode_for_role("admin") == "sovereign"
        assert security_mode_for_role("monitor") == "secure"


class TestSignupUidRoleValidation:
    def test_wrong_uid_role_rejected(self, client: TestClient) -> None:
        resp = client.post(
            "/api/auth/register",
            json={
                "username": "spoof1",
                "password": "pass-12345",
                "user_id": "SE00503",
                "role": "admin",
            },
        )
        assert resp.status_code == 403

    def test_unknown_uid_rejected(self, client: TestClient) -> None:
        resp = client.post(
            "/api/auth/register",
            json={
                "username": "spoof2",
                "password": "pass-12345",
                "user_id": "XX99999",
                "role": "admin",
            },
        )
        assert resp.status_code == 403


class TestSupervisoryTraceAccess:
    def test_manager_can_view_worker_task_and_trace(self, client: TestClient) -> None:
        balaji = _login(client, "Balaji", "medha-balaji-2026")
        task = _create_task(client, balaji, "OP-TASK-001")

        ali = _login(client, "Ali", "medha-ali-2026")
        get_resp = client.get(f"/api/tasks/{task['task_id']}", headers=_h(ali))
        assert get_resp.status_code == 200
        assert get_resp.json()["task_id"] == task["task_id"]

        audit_resp = client.get(
            f"/api/verifier/audit/{task['task_id']}", headers=_h(ali)
        )
        assert audit_resp.status_code == 200
        types = [e["event_type"] for e in audit_resp.json()["events"]]
        assert "MANAGER_VIEW_TASK" in types
        assert "MANAGER_VIEW_TRACE" in types

    def test_admin_oversight_is_audited(self, client: TestClient) -> None:
        balaji = _login(client, "Balaji", "medha-balaji-2026")
        task = _create_task(client, balaji, "OP-TASK-ADMIN")

        lokesh = _login(client, "lokesh", "medha-lokesh-2026")
        assert (
            client.get(f"/api/tasks/{task['task_id']}", headers=_h(lokesh)).status_code
            == 200
        )
        audit_resp = client.get(
            f"/api/verifier/audit/{task['task_id']}", headers=_h(lokesh)
        )
        assert audit_resp.status_code == 200
        types = [e["event_type"] for e in audit_resp.json()["events"]]
        assert "ADMIN_VIEW_TASK" in types
        assert "ADMIN_VIEW_TRACE" in types
        view_events = [
            e for e in audit_resp.json()["events"] if e["event_type"] == "ADMIN_VIEW_TASK"
        ]
        assert view_events
        assert "target_user_id=OP00303" in view_events[-1]["detail"]

    def test_operator_cannot_view_managers_task(self, client: TestClient) -> None:
        ali = _login(client, "Ali", "medha-ali-2026")
        # Manager cannot create tasks (RBAC); use admin-created private task.
        lokesh = _login(client, "lokesh", "medha-lokesh-2026")
        task = _create_task(client, lokesh, "ADMIN-PRIVATE")

        balaji = _login(client, "Balaji", "medha-balaji-2026")
        resp = client.get(f"/api/tasks/{task['task_id']}", headers=_h(balaji))
        assert resp.status_code == 403
        resp2 = client.get(
            f"/api/verifier/audit/{task['task_id']}", headers=_h(balaji)
        )
        assert resp2.status_code == 403
        _ = ali

    def test_task_id_tampering_denied_for_operator(self, client: TestClient) -> None:
        eng_login = client.post(
            "/api/auth/login",
            json={"username": "engineer", "password": "medha-engineer-2026"},
        )
        task = _create_task(client, eng_login.json()["access_token"], "Eng private")
        other = _login(client, "keerthi", "medha-keerthi-2026")
        resp = client.get(f"/api/tasks/{task['task_id']}", headers=_h(other))
        assert resp.status_code == 403

    def test_manager_cannot_modify_others_task(self, client: TestClient) -> None:
        balaji = _login(client, "Balaji", "medha-balaji-2026")
        task = _create_task(client, balaji, "OP-NOMOD")
        ali = _login(client, "Ali", "medha-ali-2026")
        resp = client.patch(
            f"/api/tasks/{task['task_id']}/status",
            json={"new_status": "authorized"},
            headers=_h(ali),
        )
        assert resp.status_code == 403

    def test_monitor_is_read_only(self, client: TestClient) -> None:
        balaji = _login(client, "Balaji", "medha-balaji-2026")
        task = _create_task(client, balaji, "OP-MONITOR")
        saniya = _login(client, "saniya", "medha-saniya-2026")
        assert (
            client.get(f"/api/tasks/{task['task_id']}", headers=_h(saniya)).status_code
            == 200
        )
        resp = client.patch(
            f"/api/tasks/{task['task_id']}/status",
            json={"new_status": "authorized"},
            headers=_h(saniya),
        )
        assert resp.status_code == 403

    def test_frontend_cannot_forge_role(self, client: TestClient) -> None:
        balaji = _login(client, "Balaji", "medha-balaji-2026")
        me_before = _me(client, balaji)
        assert me_before["role"] == "operator"
        # No endpoint accepts a role change; /auth/role does not exist.
        resp = client.patch(
            "/api/auth/role",
            json={"role": "admin"},
            headers=_h(balaji),
        )
        assert resp.status_code in (404, 405)
        assert _me(client, balaji)["role"] == "operator"


class TestIdentityContinuity:
    def test_username_change_preserves_user_id_and_tasks(
        self, client: TestClient
    ) -> None:
        balaji = _login(client, "Balaji", "medha-balaji-2026")
        task = _create_task(client, balaji, "Before rename")
        rename = client.patch(
            "/api/auth/username",
            json={"username": "balaji.renamed"},
            headers=_h(balaji),
        )
        assert rename.status_code == 200
        assert rename.json()["user_id"] == "OP00303"

        new_token = _login(client, "balaji.renamed", "medha-balaji-2026")
        me = _me(client, new_token)
        assert me["user_id"] == "OP00303"
        tasks = client.get("/api/tasks", headers=_h(new_token)).json()
        assert any(t["task_id"] == task["task_id"] for t in tasks)

    def test_duplicate_usernames_remain_separate(self, client: TestClient) -> None:
        reg = client.post(
            "/api/auth/register",
            json={"username": "Balaji", "password": "other-balaji-1", "role": "operator"},
        )
        assert reg.status_code == 201
        twin = _me(client, reg.json()["access_token"])
        assert twin["user_id"] != "OP00303"
        assert twin["role"] == "operator"


class TestExistingAuthStillWorks:
    def test_legacy_demo_login(self, client: TestClient) -> None:
        token = _login(client, "operator", "medha-operator-2026")
        assert _me(client, token)["user_id"] == "USR-00000001"

    def test_existing_seed_users_preserved(self, client: TestClient) -> None:
        token = _login(client, "admin", "medha-admin-2026")
        assert _me(client, token)["user_id"] == "USR-00000004"
