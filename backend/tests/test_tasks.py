"""Tests for Task Passport creation and retrieval (Stages 1-3)."""

from fastapi.testclient import TestClient


def test_create_task(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/api/tasks",
        json={
            "title": "Inspect pump P-101",
            "purpose": "Prepare a draft inspection analysis",
            "sensitivity": "confidential",
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Inspect pump P-101"
    assert body["purpose"] == "Prepare a draft inspection analysis"
    assert body["sensitivity"] == "confidential"
    assert body["status"] == "draft"
    assert body["task_id"]
    assert body["created_at"]
    assert body["user_id"] == "USR-00000001"
    assert body["identity"] == "operator"
    assert body["role"] == "operator"


def test_create_task_with_all_passport_fields(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/tasks",
        json={
            "title": "Full passport task",
            "purpose": "Test all passport fields",
            "sensitivity": "restricted",
            "requested_operation": "Analyze inspection report and generate approval note",
            "allowed_sources": ["inspection_report.pdf", "sop_manual.pdf"],
            "allowed_tools": ["document_reader", "docx_generator"],
            "allowed_models": ["reasoning-model"],
            "approval_requirement": "reviewer",
            "network_policy": "deny_external",
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["sensitivity"] == "restricted"
    assert body["requested_operation"] == "Analyze inspection report and generate approval note"
    assert body["allowed_sources"] == ["inspection_report.pdf", "sop_manual.pdf"]
    assert body["allowed_tools"] == ["document_reader", "docx_generator"]
    assert body["allowed_models"] == ["reasoning-model"]
    assert body["approval_requirement"] == "reviewer"
    assert body["network_policy"] == "deny_external"
    assert body["status"] == "draft"


def test_get_task(client: TestClient, auth_headers: dict[str, str]) -> None:
    created = client.post(
        "/api/tasks",
        json={"title": "Review inspection", "purpose": "Prepare a draft"},
        headers=auth_headers,
    ).json()

    response = client.get(f"/api/tasks/{created['task_id']}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["task_id"] == created["task_id"]
    assert response.json()["title"] == "Review inspection"


def test_get_missing_task_returns_not_found(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/api/tasks/not-a-task", headers=auth_headers)

    assert response.status_code == 404
    assert response.json() == {"detail": "Task passport not found"}


def test_unauthenticated_user_cannot_get_task(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    created = client.post(
        "/api/tasks",
        json={"title": "Protected task", "purpose": "Needs auth"},
        headers=auth_headers,
    ).json()

    response = client.get(f"/api/tasks/{created['task_id']}")
    assert response.status_code == 401
