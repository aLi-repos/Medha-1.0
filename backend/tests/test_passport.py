"""Stage 3 Task Passport tests: lifecycle, immutability, identity, audit."""

from fastapi.testclient import TestClient


# --- Helpers ---


def _create_passport(client: TestClient, headers: dict[str, str], **overrides) -> dict:
    body = {
        "title": "Test passport",
        "purpose": "Verify lifecycle",
        "sensitivity": "internal",
        "allowed_sources": ["doc1.pdf"],
        "allowed_tools": ["calculator"],
        "allowed_models": ["text-model"],
        "network_policy": "deny_external",
    }
    body.update(overrides)
    response = client.post("/api/tasks", json=body, headers=headers)
    assert response.status_code == 201
    return response.json()


# --- Lifecycle tests ---


def test_lifecycle_draft_to_authorized_to_executing_to_completed(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    passport = _create_passport(client, auth_headers)
    task_id = passport["task_id"]

    # draft -> authorized
    resp = client.patch(
        f"/api/tasks/{task_id}/status",
        json={"new_status": "authorized"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "authorized"

    # authorized -> executing
    resp = client.patch(
        f"/api/tasks/{task_id}/status",
        json={"new_status": "executing"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "executing"

    # executing -> completed
    resp = client.patch(
        f"/api/tasks/{task_id}/status",
        json={"new_status": "completed"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


def test_lifecycle_draft_to_denied(client: TestClient, auth_headers: dict[str, str]) -> None:
    passport = _create_passport(client, auth_headers)
    task_id = passport["task_id"]

    resp = client.patch(
        f"/api/tasks/{task_id}/status",
        json={"new_status": "denied", "detail": "Policy violation"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "denied"


def test_lifecycle_draft_to_authorized_to_denied(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    passport = _create_passport(client, auth_headers)
    task_id = passport["task_id"]

    # draft -> authorized
    client.patch(
        f"/api/tasks/{task_id}/status",
        json={"new_status": "authorized"},
        headers=auth_headers,
    )

    # authorized -> denied
    resp = client.patch(
        f"/api/tasks/{task_id}/status",
        json={"new_status": "denied"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "denied"


def test_lifecycle_executing_to_failed(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    passport = _create_passport(client, auth_headers)
    task_id = passport["task_id"]

    # draft -> authorized -> executing -> failed
    client.patch(
        f"/api/tasks/{task_id}/status",
        json={"new_status": "authorized"},
        headers=auth_headers,
    )
    client.patch(
        f"/api/tasks/{task_id}/status",
        json={"new_status": "executing"},
        headers=auth_headers,
    )
    resp = client.patch(
        f"/api/tasks/{task_id}/status",
        json={"new_status": "failed", "detail": "Sandbox error"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "failed"


def test_invalid_transition_is_rejected(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    passport = _create_passport(client, auth_headers)
    task_id = passport["task_id"]

    # draft -> completed is NOT allowed
    resp = client.patch(
        f"/api/tasks/{task_id}/status",
        json={"new_status": "completed"},
        headers=auth_headers,
    )
    assert resp.status_code == 409
    assert "Cannot transition" in resp.json()["detail"]


def test_cannot_transition_from_completed(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    passport = _create_passport(client, auth_headers)
    task_id = passport["task_id"]

    # Complete the passport
    for status in ["authorized", "executing", "completed"]:
        client.patch(
            f"/api/tasks/{task_id}/status",
            json={"new_status": status},
            headers=auth_headers,
        )

    # Try to transition from completed
    resp = client.patch(
        f"/api/tasks/{task_id}/status",
        json={"new_status": "executing"},
        headers=auth_headers,
    )
    assert resp.status_code == 409


def test_failed_can_be_reauthorized(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    passport = _create_passport(client, auth_headers)
    task_id = passport["task_id"]

    # draft -> authorized -> executing -> failed -> authorized
    for status in ["authorized", "executing", "failed"]:
        client.patch(
            f"/api/tasks/{task_id}/status",
            json={"new_status": status},
            headers=auth_headers,
        )

    resp = client.patch(
        f"/api/tasks/{task_id}/status",
        json={"new_status": "authorized", "detail": "Retrying after fix"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "authorized"


# --- Immutability tests ---


def test_security_critical_fields_immutable_after_execution(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    passport = _create_passport(client, auth_headers, sensitivity="confidential")
    task_id = passport["task_id"]

    # Move to authorized (leaves draft)
    client.patch(
        f"/api/tasks/{task_id}/status",
        json={"new_status": "authorized"},
        headers=auth_headers,
    )

    # Try to update security fields — should fail
    resp = client.patch(
        f"/api/tasks/{task_id}/security-fields",
        json={"allowed_sources": ["new_doc.pdf"]},
        headers=auth_headers,
    )
    assert resp.status_code == 409
    assert "cannot be modified" in resp.json()["detail"]


def test_security_fields_updatable_in_draft(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    passport = _create_passport(client, auth_headers)
    task_id = passport["task_id"]

    resp = client.patch(
        f"/api/tasks/{task_id}/security-fields",
        json={
            "allowed_sources": ["new_doc.pdf", "another.pdf"],
            "allowed_tools": ["calculator", "docx_generator"],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["allowed_sources"] == ["new_doc.pdf", "another.pdf"]
    assert resp.json()["allowed_tools"] == ["calculator", "docx_generator"]


# --- Identity match tests ---


def test_user_must_match_passport_identity(
    client: TestClient, auth_headers: dict[str, str], engineer_headers: dict[str, str]
) -> None:
    passport = _create_passport(client, auth_headers)
    task_id = passport["task_id"]

    # Engineer tries to access operator's passport
    resp = client.get(f"/api/tasks/{task_id}", headers=engineer_headers)
    assert resp.status_code == 403
    assert "does not match" in resp.json()["detail"]


def test_owner_can_access_own_passport(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    passport = _create_passport(client, auth_headers)
    task_id = passport["task_id"]

    resp = client.get(f"/api/tasks/{task_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["task_id"] == task_id


# --- RBAC tests ---


def test_reviewer_cannot_create_passport(
    client: TestClient, reviewer_headers: dict[str, str]
) -> None:
    resp = client.post(
        "/api/tasks",
        json={"title": "Reviewer task", "purpose": "Not allowed"},
        headers=reviewer_headers,
    )
    assert resp.status_code == 403


def test_engineer_can_create_passport(
    client: TestClient, engineer_headers: dict[str, str]
) -> None:
    resp = client.post(
        "/api/tasks",
        json={"title": "Engineer passport", "purpose": "Design work"},
        headers=engineer_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["user_id"] == "USR-00000002"
    assert resp.json()["role"] == "engineer"


def test_admin_can_create_passport(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    resp = client.post(
        "/api/tasks",
        json={"title": "Admin passport", "purpose": "System admin"},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["user_id"] == "USR-00000004"
    assert resp.json()["role"] == "admin"


# --- Audit event tests ---


def test_audit_event_emitted_on_creation(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    from app.services.audit_service import audit_service

    passport = _create_passport(client, auth_headers)
    events = audit_service.get_events_for_task(passport["task_id"])

    assert len(events) == 1
    assert events[0].event_type == "passport_created"
    assert events[0].user_id == "USR-00000001"
    assert events[0].new_status == "draft"


def test_audit_event_emitted_on_status_transition(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    from app.services.audit_service import audit_service

    passport = _create_passport(client, auth_headers)
    task_id = passport["task_id"]

    client.patch(
        f"/api/tasks/{task_id}/status",
        json={"new_status": "authorized"},
        headers=auth_headers,
    )

    events = audit_service.get_events_for_task(task_id)
    assert len(events) == 2
    assert events[1].event_type == "passport_status_transition"
    assert events[1].previous_status == "draft"
    assert events[1].new_status == "authorized"


def test_audit_event_emitted_on_security_fields_update(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    from app.services.audit_service import audit_service

    passport = _create_passport(client, auth_headers)
    task_id = passport["task_id"]

    client.patch(
        f"/api/tasks/{task_id}/security-fields",
        json={"allowed_sources": ["updated.pdf"]},
        headers=auth_headers,
    )

    events = audit_service.get_events_for_task(task_id)
    assert len(events) == 2
    assert events[1].event_type == "passport_security_fields_updated"


def test_full_audit_trace_reconstruction(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    from app.services.audit_service import audit_service

    passport = _create_passport(client, auth_headers)
    task_id = passport["task_id"]

    # Perform a full lifecycle: create -> authorize -> execute -> complete
    client.patch(
        f"/api/tasks/{task_id}/status",
        json={"new_status": "authorized"},
        headers=auth_headers,
    )
    client.patch(
        f"/api/tasks/{task_id}/status",
        json={"new_status": "executing"},
        headers=auth_headers,
    )
    client.patch(
        f"/api/tasks/{task_id}/status",
        json={"new_status": "completed"},
        headers=auth_headers,
    )

    events = audit_service.get_events_for_task(task_id)
    event_types = [e.event_type for e in events]

    assert event_types == [
        "passport_created",
        "passport_status_transition",
        "passport_status_transition",
        "passport_status_transition",
    ]
    # Verify the full chain can be reconstructed
    assert events[0].new_status == "draft"
    assert events[1].previous_status == "draft"
    assert events[1].new_status == "authorized"
    assert events[2].previous_status == "authorized"
    assert events[2].new_status == "executing"
    assert events[3].previous_status == "executing"
    assert events[3].new_status == "completed"
