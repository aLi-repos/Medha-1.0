"""Tests for Chat, Conversation, and enhanced Audit Trail features."""

import io
import json

import pytest
from fastapi.testclient import TestClient


def _create_task(client: TestClient, headers: dict, title: str = "Test Task") -> dict:
    resp = client.post(
        "/api/tasks",
        json={"title": title, "purpose": "Test purpose", "sensitivity": "internal"},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()


def _authorize_task(client: TestClient, headers: dict, task_id: str) -> dict:
    resp = client.patch(
        f"/api/tasks/{task_id}/status",
        json={"new_status": "authorized", "detail": "Authorized for testing"},
        headers=headers,
    )
    assert resp.status_code == 200
    return resp.json()


def _start_execution(client: TestClient, headers: dict, task_id: str) -> dict:
    resp = client.patch(
        f"/api/tasks/{task_id}/status",
        json={"new_status": "executing", "detail": "Execution started"},
        headers=headers,
    )
    assert resp.status_code == 200
    return resp.json()


class TestConversationCreation:
    def test_create_conversation(self, client: TestClient, operator_token: str):
        headers = {"Authorization": f"Bearer {operator_token}"}
        task = _create_task(client, headers)
        _authorize_task(client, headers, task["task_id"])
        _start_execution(client, headers, task["task_id"])

        resp = client.post(
            "/api/chat/conversations",
            json={"task_id": task["task_id"], "title": "Test Conversation"},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test Conversation"
        assert data["task_id"] == task["task_id"]
        assert data["user_id"] == "USR-00000001"

    def test_create_conversation_requires_auth(self, client: TestClient):
        resp = client.post(
            "/api/chat/conversations",
            json={"task_id": "fake", "title": "Test"},
        )
        assert resp.status_code in (401, 403)

    def test_create_conversation_nonexistent_task(self, client: TestClient, operator_token: str):
        headers = {"Authorization": f"Bearer {operator_token}"}
        resp = client.post(
            "/api/chat/conversations",
            json={"task_id": "nonexistent", "title": "Test"},
            headers=headers,
        )
        assert resp.status_code == 404

    def test_create_conversation_identity_mismatch(self, client: TestClient, operator_token: str, engineer_token: str):
        headers_op = {"Authorization": f"Bearer {operator_token}"}
        headers_eng = {"Authorization": f"Bearer {engineer_token}"}
        task = _create_task(client, headers_op)

        resp = client.post(
            "/api/chat/conversations",
            json={"task_id": task["task_id"], "title": "Test"},
            headers=headers_eng,
        )
        assert resp.status_code == 403


class TestConversationListing:
    def test_list_conversations(self, client: TestClient, operator_token: str):
        headers = {"Authorization": f"Bearer {operator_token}"}
        task = _create_task(client, headers)
        _authorize_task(client, headers, task["task_id"])
        _start_execution(client, headers, task["task_id"])

        client.post(
            "/api/chat/conversations",
            json={"task_id": task["task_id"], "title": "Conv 1"},
            headers=headers,
        )
        client.post(
            "/api/chat/conversations",
            json={"task_id": task["task_id"], "title": "Conv 2"},
            headers=headers,
        )

        resp = client.get(f"/api/chat/conversations/{task['task_id']}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    def test_list_conversations_scoped_to_user(self, client: TestClient, operator_token: str, engineer_token: str):
        headers_op = {"Authorization": f"Bearer {operator_token}"}
        headers_eng = {"Authorization": f"Bearer {engineer_token}"}
        task = _create_task(client, headers_op)
        _authorize_task(client, headers_op, task["task_id"])
        _start_execution(client, headers_op, task["task_id"])

        client.post(
            "/api/chat/conversations",
            json={"task_id": task["task_id"], "title": "Op Conv"},
            headers=headers_op,
        )

        resp = client.get(f"/api/chat/conversations/{task['task_id']}", headers=headers_eng)
        assert resp.status_code == 403


class TestMessageSending:
    def test_send_message_creates_conversation(self, client: TestClient, operator_token: str):
        headers = {"Authorization": f"Bearer {operator_token}"}
        task = _create_task(client, headers)
        _authorize_task(client, headers, task["task_id"])
        _start_execution(client, headers, task["task_id"])

        resp = client.post(
            "/api/chat/send",
            json={"task_id": task["task_id"], "prompt": "Hello, what can you do?"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["response_text"]
        assert data["model_used"]
        assert data["conversation_id"]

    def test_send_message_in_existing_conversation(self, client: TestClient, operator_token: str):
        headers = {"Authorization": f"Bearer {operator_token}"}
        task = _create_task(client, headers)
        _authorize_task(client, headers, task["task_id"])
        _start_execution(client, headers, task["task_id"])

        convo_resp = client.post(
            "/api/chat/conversations",
            json={"task_id": task["task_id"], "title": "Test Conv"},
            headers=headers,
        )
        convo_id = convo_resp.json()["id"]

        resp = client.post(
            "/api/chat/send",
            json={
                "task_id": task["task_id"],
                "conversation_id": convo_id,
                "prompt": "First message",
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["conversation_id"] == convo_id

    def test_send_message_persists_history(self, client: TestClient, operator_token: str):
        headers = {"Authorization": f"Bearer {operator_token}"}
        task = _create_task(client, headers)
        _authorize_task(client, headers, task["task_id"])
        _start_execution(client, headers, task["task_id"])

        send_resp = client.post(
            "/api/chat/send",
            json={"task_id": task["task_id"], "prompt": "Test message"},
            headers=headers,
        )
        convo_id = send_resp.json()["conversation_id"]

        msg_resp = client.get(f"/api/chat/messages/{convo_id}", headers=headers)
        assert msg_resp.status_code == 200
        data = msg_resp.json()
        assert data["total"] >= 2
        roles = [m["role"] for m in data["messages"]]
        assert "user" in roles
        assert "assistant" in roles

    def test_send_message_requires_auth(self, client: TestClient):
        resp = client.post(
            "/api/chat/send",
            json={"task_id": "fake", "prompt": "test"},
        )
        assert resp.status_code in (401, 403)

    def test_send_message_nonexistent_task(self, client: TestClient, operator_token: str):
        headers = {"Authorization": f"Bearer {operator_token}"}
        resp = client.post(
            "/api/chat/send",
            json={"task_id": "nonexistent", "prompt": "test"},
            headers=headers,
        )
        assert resp.status_code == 404


class TestModelSelection:
    def test_model_selection_in_chat(self, client: TestClient, operator_token: str):
        headers = {"Authorization": f"Bearer {operator_token}"}
        task = _create_task(client, headers, title="Model Selection Task")
        _authorize_task(client, headers, task["task_id"])
        _start_execution(client, headers, task["task_id"])

        resp = client.post(
            "/api/chat/send",
            json={
                "task_id": task["task_id"],
                "prompt": "Test with specific model",
                "model": "local-qwen2",
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["model_used"] == "local-qwen2"

    def test_blocked_model_rejected(self, client: TestClient, operator_token: str):
        headers = {"Authorization": f"Bearer {operator_token}"}
        task = _create_task(client, headers, title="Block Test")
        client.patch(
            f"/api/tasks/{task['task_id']}/security-fields",
            json={"allowed_models": ["local-qwen2"]},
            headers=headers,
        )
        _authorize_task(client, headers, task["task_id"])
        _start_execution(client, headers, task["task_id"])

        resp = client.post(
            "/api/chat/send",
            json={
                "task_id": task["task_id"],
                "prompt": "Test blocked model",
                "model": "api-openai",
            },
            headers=headers,
        )
        assert resp.status_code == 403

    def test_external_model_blocked_by_network_policy(self, client: TestClient, operator_token: str):
        headers = {"Authorization": f"Bearer {operator_token}"}
        task = _create_task(client, headers, title="Network Policy Test")
        client.patch(
            f"/api/tasks/{task['task_id']}/security-fields",
            json={"allowed_models": ["api-openai"], "network_policy": "deny_external"},
            headers=headers,
        )
        _authorize_task(client, headers, task["task_id"])
        _start_execution(client, headers, task["task_id"])

        resp = client.post(
            "/api/chat/send",
            json={
                "task_id": task["task_id"],
                "prompt": "Test external model",
                "model": "api-openai",
            },
            headers=headers,
        )
        assert resp.status_code == 403
        assert "network policy" in resp.json()["detail"].lower()


class TestChatAuditEvents:
    def test_chat_generates_audit_events(self, client: TestClient, operator_token: str):
        headers = {"Authorization": f"Bearer {operator_token}"}
        task = _create_task(client, headers, title="Audit Chat Test")
        _authorize_task(client, headers, task["task_id"])
        _start_execution(client, headers, task["task_id"])

        client.post(
            "/api/chat/send",
            json={"task_id": task["task_id"], "prompt": "Audit test message"},
            headers=headers,
        )

        resp = client.get(f"/api/verifier/audit/{task['task_id']}", headers=headers)
        assert resp.status_code == 200
        events = resp.json()["events"]
        event_types = [e["event_type"] for e in events]
        assert "chat_message_sent" in event_types
        assert "model_inference" in event_types

    def test_blocked_model_generates_audit_event(self, client: TestClient, operator_token: str):
        headers = {"Authorization": f"Bearer {operator_token}"}
        task = _create_task(client, headers, title="Blocked Model Audit")
        client.patch(
            f"/api/tasks/{task['task_id']}/security-fields",
            json={"allowed_models": ["local-qwen2"]},
            headers=headers,
        )
        _authorize_task(client, headers, task["task_id"])
        _start_execution(client, headers, task["task_id"])

        client.post(
            "/api/chat/send",
            json={
                "task_id": task["task_id"],
                "prompt": "Test",
                "model": "api-openai",
            },
            headers=headers,
        )

        resp = client.get(f"/api/verifier/audit/{task['task_id']}", headers=headers)
        events = resp.json()["events"]
        event_types = [e["event_type"] for e in events]
        assert "model_blocked" in event_types


class TestAuditAutoLoad:
    def test_get_tasks_with_audit_summary(self, client: TestClient, operator_token: str):
        headers = {"Authorization": f"Bearer {operator_token}"}
        task = _create_task(client, headers, title="Summary Test")

        resp = client.get("/api/verifier/audit", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        task_ids = [t["task_id"] for t in data["tasks"]]
        assert task["task_id"] in task_ids

    def test_tasks_summary_includes_latest_event(self, client: TestClient, operator_token: str):
        headers = {"Authorization": f"Bearer {operator_token}"}
        task = _create_task(client, headers, title="Latest Event Test")
        _authorize_task(client, headers, task["task_id"])

        resp = client.get("/api/verifier/audit", headers=headers)
        data = resp.json()
        task_summary = next(t for t in data["tasks"] if t["task_id"] == task["task_id"])
        assert task_summary["latest_event_type"] == "passport_status_transition"
        assert task_summary["total_events"] >= 2

    def test_audit_summary_respects_user_scoping(self, client: TestClient, operator_token: str, engineer_token: str):
        headers_op = {"Authorization": f"Bearer {operator_token}"}
        headers_eng = {"Authorization": f"Bearer {engineer_token}"}
        _create_task(client, headers_op, title="Op Only Task")

        resp_op = client.get("/api/verifier/audit", headers=headers_op)
        resp_eng = client.get("/api/verifier/audit", headers=headers_eng)

        op_tasks = [t["title"] for t in resp_op.json()["tasks"]]
        eng_tasks = [t["title"] for t in resp_eng.json()["tasks"]]
        assert "Op Only Task" in op_tasks
        assert "Op Only Task" not in eng_tasks

    def test_audit_summary_auto_loads_without_manual_button(self, client: TestClient, operator_token: str):
        headers = {"Authorization": f"Bearer {operator_token}"}
        _create_task(client, headers, title="Auto Load Test")

        resp = client.get("/api/verifier/audit", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1


class TestTaskLifecycleCompletion:
    def test_complete_task(self, client: TestClient, operator_token: str):
        headers = {"Authorization": f"Bearer {operator_token}"}
        task = _create_task(client, headers, title="Complete Test")
        _authorize_task(client, headers, task["task_id"])
        _start_execution(client, headers, task["task_id"])

        resp = client.patch(
            f"/api/tasks/{task['task_id']}/status",
            json={"new_status": "completed", "detail": "Task completed"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_fail_task(self, client: TestClient, operator_token: str):
        headers = {"Authorization": f"Bearer {operator_token}"}
        task = _create_task(client, headers, title="Fail Test")
        _authorize_task(client, headers, task["task_id"])
        _start_execution(client, headers, task["task_id"])

        resp = client.patch(
            f"/api/tasks/{task['task_id']}/status",
            json={"new_status": "failed", "detail": "Task failed"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "failed"

    def test_completed_task_blocks_consequential_actions(self, client: TestClient, operator_token: str):
        headers = {"Authorization": f"Bearer {operator_token}"}
        task = _create_task(client, headers, title="Completed Block Test")
        _authorize_task(client, headers, task["task_id"])
        _start_execution(client, headers, task["task_id"])

        client.patch(
            f"/api/tasks/{task['task_id']}/status",
            json={"new_status": "completed"},
            headers=headers,
        )

        resp = client.post(
            "/api/chat/send",
            json={"task_id": task["task_id"], "prompt": "Should fail"},
            headers=headers,
        )
        assert resp.status_code == 403

    def test_failed_task_blocks_consequential_actions(self, client: TestClient, operator_token: str):
        headers = {"Authorization": f"Bearer {operator_token}"}
        task = _create_task(client, headers, title="Failed Block Test")
        _authorize_task(client, headers, task["task_id"])
        _start_execution(client, headers, task["task_id"])

        client.patch(
            f"/api/tasks/{task['task_id']}/status",
            json={"new_status": "failed"},
            headers=headers,
        )

        resp = client.post(
            "/api/chat/send",
            json={"task_id": task["task_id"], "prompt": "Should fail"},
            headers=headers,
        )
        assert resp.status_code == 403


class TestFileUpload:
    def test_upload_file(self, client: TestClient, operator_token: str):
        headers = {"Authorization": f"Bearer {operator_token}"}
        task = _create_task(client, headers, title="Upload Test")
        _authorize_task(client, headers, task["task_id"])
        _start_execution(client, headers, task["task_id"])

        file_content = b"Test file content for upload"
        resp = client.post(
            "/api/chat/upload",
            files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
            data={"task_id": task["task_id"]},
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["filename"] == "test.txt"
        assert data["content_type"] == "text/plain"

    def test_upload_requires_task_id(self, client: TestClient, operator_token: str):
        headers = {"Authorization": f"Bearer {operator_token}"}
        file_content = b"Test content"
        resp = client.post(
            "/api/chat/upload",
            files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
            data={"task_id": ""},
            headers=headers,
        )
        assert resp.status_code == 400

    def test_upload_generates_audit_event(self, client: TestClient, operator_token: str):
        headers = {"Authorization": f"Bearer {operator_token}"}
        task = _create_task(client, headers, title="Upload Audit Test")
        _authorize_task(client, headers, task["task_id"])
        _start_execution(client, headers, task["task_id"])

        file_content = b"Audit test content"
        client.post(
            "/api/chat/upload",
            files={"file": ("audit.txt", io.BytesIO(file_content), "text/plain")},
            data={"task_id": task["task_id"]},
            headers=headers,
        )

        resp = client.get(f"/api/verifier/audit/{task['task_id']}", headers=headers)
        events = resp.json()["events"]
        event_types = [e["event_type"] for e in events]
        assert "file_attached" in event_types
