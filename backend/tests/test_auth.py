from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient

from app.core.config import settings


def login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_successful_login(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "operator", "password": "medha-operator-2026"},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_invalid_credentials_are_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "operator", "password": "incorrect-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid username or password"}


def test_authenticated_user_can_view_identity(client: TestClient) -> None:
    token = login(client, "reviewer", "medha-reviewer-2026")

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "reviewer"
    assert body["role"] == "reviewer"
    assert body["user_id"] == "USR-00000003"


def test_missing_token_is_rejected(client: TestClient) -> None:
    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_invalid_token_is_rejected(client: TestClient) -> None:
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid.token"})

    assert response.status_code == 401


def test_expired_token_is_rejected(client: TestClient) -> None:
    expired_token = jwt.encode(
        {
            "sub": "operator",
            "role": "operator",
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    response = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"}
    )

    assert response.status_code == 401


def test_reviewer_cannot_create_task(client: TestClient) -> None:
    token = login(client, "reviewer", "medha-reviewer-2026")

    response = client.post(
        "/api/tasks",
        json={"title": "Restricted action", "purpose": "Try creating a task"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Your role is not permitted to perform this action"}


def test_task_creation_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/tasks", json={"title": "No token", "purpose": "Try creating a task"}
    )

    assert response.status_code == 401


# --- Stage 3: ENGINEER role tests ---


def test_engineer_login(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "engineer", "password": "medha-engineer-2026"},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_engineer_can_view_identity(client: TestClient) -> None:
    token = login(client, "engineer", "medha-engineer-2026")

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "engineer"
    assert body["role"] == "engineer"
    assert body["user_id"] == "USR-00000002"


def test_engineer_can_create_task(client: TestClient) -> None:
    token = login(client, "engineer", "medha-engineer-2026")

    response = client.post(
        "/api/tasks",
        json={"title": "Engineer task", "purpose": "Design review"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    assert response.json()["role"] == "engineer"
    assert response.json()["user_id"] == "USR-00000002"


def test_admin_can_create_task(client: TestClient) -> None:
    token = login(client, "admin", "medha-admin-2026")

    response = client.post(
        "/api/tasks",
        json={"title": "Admin task", "purpose": "System config"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    assert response.json()["role"] == "admin"
    assert response.json()["user_id"] == "USR-00000004"


# --- Login identity: user_id is authoritative ---


def _me(client: TestClient, token: str) -> dict:
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    return response.json()


def test_admin_login_with_user_id_username_role_password(client: TestClient) -> None:
    """Login resolves identity via user_id + username (+ password); role is server-side."""
    response = client.post(
        "/api/auth/login",
        json={
            "user_id": "USR-00000004",
            "username": "admin",
            "password": "medha-admin-2026",
        },
    )
    assert response.status_code == 200
    body = _me(client, response.json()["access_token"])
    assert body["user_id"] == "USR-00000004"
    assert body["username"] == "admin"
    assert body["role"] == "admin"


def test_admin_login_rejects_wrong_user_id(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={
            "user_id": "USR-00000001",
            "username": "admin",
            "password": "medha-admin-2026",
        },
    )
    assert response.status_code == 401


def test_admin_username_change_preserves_login_and_tasks(client: TestClient) -> None:
    token = login(client, "admin", "medha-admin-2026")
    created = client.post(
        "/api/tasks",
        json={"title": "Before rename", "purpose": "identity continuity"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert created.status_code == 201
    task_id = created.json()["task_id"]

    rename = client.patch(
        "/api/auth/username",
        json={"username": "ali"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rename.status_code == 200
    assert rename.json()["user_id"] == "USR-00000004"
    assert rename.json()["role"] == "admin"

    # Same account logs in with the new username + existing password.
    new_token = login(client, "ali", "medha-admin-2026")
    body = _me(client, new_token)
    assert body["user_id"] == "USR-00000004"
    assert body["username"] == "ali"
    assert body["role"] == "admin"

    tasks = client.get(
        "/api/tasks", headers={"Authorization": f"Bearer {new_token}"}
    ).json()
    assert any(t["task_id"] == task_id for t in tasks)


def test_duplicate_username_accounts_stay_separate(client: TestClient) -> None:
    """Two users with the same username remain separate (user_id + role)."""
    # Register a second account, then rename it onto the demo operator's username.
    reg = client.post(
        "/api/auth/register",
        json={"username": "twin.a", "password": "twin-pass-2026", "role": "admin"},
    )
    assert reg.status_code == 201
    twin_token = reg.json()["access_token"]
    twin_before = _me(client, twin_token)
    # Role is server-controlled: self-registration is always operator.
    assert twin_before["role"] == "operator"
    assert twin_before["user_id"] != "USR-00000001"

    rename = client.patch(
        "/api/auth/username",
        json={"username": "operator"},
        headers={"Authorization": f"Bearer {twin_token}"},
    )
    assert rename.status_code == 200
    assert rename.json()["username"] == "operator"
    assert rename.json()["user_id"] == twin_before["user_id"]

    # Operator creates a task; twin creates a task.
    op_token = login(client, "operator", "medha-operator-2026")
    op_task = client.post(
        "/api/tasks",
        json={"title": "Operator task", "purpose": "must not cross"},
        headers={"Authorization": f"Bearer {op_token}"},
    )
    assert op_task.status_code == 201

    twin_login = client.post(
        "/api/auth/login",
        json={
            "user_id": twin_before["user_id"],
            "username": "operator",
            "password": "twin-pass-2026",
        },
    )
    assert twin_login.status_code == 200
    twin_body = _me(client, twin_login.json()["access_token"])
    assert twin_body["user_id"] == twin_before["user_id"]
    assert twin_body["username"] == "operator"
    assert twin_body["role"] == "operator"
    assert twin_body["user_id"] != "USR-00000001"

    twin_task = client.post(
        "/api/tasks",
        json={"title": "Twin task", "purpose": "must not cross"},
        headers={"Authorization": f"Bearer {twin_login.json()['access_token']}"},
    )
    assert twin_task.status_code == 201

    # No data crosses between the two accounts.
    op_tasks = client.get(
        "/api/tasks", headers={"Authorization": f"Bearer {op_token}"}
    ).json()
    twin_tasks = client.get(
        "/api/tasks",
        headers={"Authorization": f"Bearer {twin_login.json()['access_token']}"},
    ).json()
    op_task_ids = {t["task_id"] for t in op_tasks}
    twin_task_ids = {t["task_id"] for t in twin_tasks}
    assert op_task.json()["task_id"] in op_task_ids
    assert twin_task.json()["task_id"] in twin_task_ids
    assert op_task.json()["task_id"] not in twin_task_ids
    assert twin_task.json()["task_id"] not in op_task_ids
    assert all(t["user_id"] == "USR-00000001" for t in op_tasks)
    assert all(t["user_id"] == twin_before["user_id"] for t in twin_tasks)

    # Demo operator still logs in with username + password alone (unique password).
    op_me = _me(client, op_token)
    assert op_me["user_id"] == "USR-00000001"
    assert op_me["username"] == "operator"
