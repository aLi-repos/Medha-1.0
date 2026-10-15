"""Tests for Stage 7 — Controlled Tool Execution + Sandbox."""

import pytest
from fastapi.testclient import TestClient

from app.services.sandbox.sandbox import (
    ExecutionResult,
    ExecutionStatus,
    NetworkPolicy,
    ResourceLimits,
    SandboxService,
    sandbox_service,
)


# ── Sandbox Service Unit Tests ──

class TestSandboxService:
    def test_execute_document_reader(self) -> None:
        result = sandbox_service.execute(
            tool_name="document_reader",
            action="Read pump inspection report",
            input_data={"source_count": 2},
        )
        assert result.status == ExecutionStatus.COMPLETED
        assert "DocumentReader" in result.output
        assert result.execution_id

    def test_execute_data_analyzer(self) -> None:
        result = sandbox_service.execute(
            tool_name="data_analyzer",
            action="Analyze temperature trends",
            input_data={},
        )
        assert result.status == ExecutionStatus.COMPLETED
        assert "DataAnalyzer" in result.output

    def test_execute_docx_generator(self) -> None:
        result = sandbox_service.execute(
            tool_name="docx_generator",
            action="Generate inspection report",
            input_data={},
        )
        assert result.status == ExecutionStatus.COMPLETED
        assert "DocxGenerator" in result.output

    def test_deny_external_blocks_api_caller(self) -> None:
        with pytest.raises(PermissionError, match="deny_external"):
            sandbox_service.execute(
                tool_name="api_caller",
                action="Call external API",
                input_data={},
                network_policy="deny_external",
            )

    def test_allow_internal_permits_api_caller(self) -> None:
        result = sandbox_service.execute(
            tool_name="api_caller",
            action="Call internal API",
            input_data={},
            network_policy="allow_internal",
        )
        assert result.status == ExecutionStatus.COMPLETED

    def test_rollback_completed_execution(self) -> None:
        result = sandbox_service.execute(
            tool_name="document_reader",
            action="Read document",
            input_data={},
        )
        rolled = sandbox_service.rollback(result.execution_id)
        assert rolled.status == ExecutionStatus.ROLLED_BACK

    def test_rollback_nonexistent_raises(self) -> None:
        with pytest.raises(ValueError, match="not found"):
            sandbox_service.rollback("nonexistent-id")

    def test_rollback_pending_execution_raises(self) -> None:
        result = ExecutionResult(
            execution_id="test",
            tool_name="test",
            status=ExecutionStatus.PENDING,
            output="",
        )
        sandbox_service._executions["test"] = result
        with pytest.raises(ValueError, match="Cannot rollback"):
            sandbox_service.rollback("test")

    def test_execution_audit_events(self) -> None:
        from app.services.audit_service import audit_service
        audit_service.clear()
        sandbox_service.execute(
            tool_name="document_reader",
            action="Read",
            input_data={},
            task_id="t1",
            user_id="u1",
            identity="u1",
            role="engineer",
        )
        events = audit_service.get_events_for_task("t1")
        event_types = {e.event_type for e in events}
        assert "sandbox_execution_started" in event_types
        assert "sandbox_execution_completed" in event_types

    def test_reset_clears_executions(self) -> None:
        sandbox_service.execute(tool_name="document_reader", action="Read", input_data={})
        sandbox_service.reset()
        assert len(sandbox_service._executions) == 0


# ── API Integration Tests ──


def _authorize_passport(client: TestClient, task_id: str, headers: dict[str, str]) -> None:
    """Helper: transition a passport from draft to authorized."""
    client.patch(
        f"/api/tasks/{task_id}/status",
        json={"new_status": "authorized", "detail": "Test authorization"},
        headers=headers,
    )


class TestSandboxAPI:
    def test_execute_requires_auth(self, client: TestClient) -> None:
        resp = client.post("/api/sandbox/execute", json={"task_id": "x", "tool_name": "y", "action": "z"})
        assert resp.status_code == 401

    def test_execute_success(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        task_resp = client.post(
            "/api/tasks",
            json={"title": "Task", "purpose": "test", "allowed_tools": ["document_reader"]},
            headers=auth_headers,
        )
        task_id = task_resp.json()["task_id"]
        _authorize_passport(client, task_id, auth_headers)

        resp = client.post(
            "/api/sandbox/execute",
            json={"task_id": task_id, "tool_name": "document_reader", "action": "Read report", "input_data": {}},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert body["execution_id"]

    def test_execute_nonexistent_task(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        resp = client.post(
            "/api/sandbox/execute",
            json={"task_id": "nonexistent", "tool_name": "x", "action": "y"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_execute_blocked_tool(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        task_resp = client.post(
            "/api/tasks",
            json={"title": "Task", "purpose": "test", "allowed_tools": ["document_reader"]},
            headers=auth_headers,
        )
        task_id = task_resp.json()["task_id"]
        _authorize_passport(client, task_id, auth_headers)

        resp = client.post(
            "/api/sandbox/execute",
            json={"task_id": task_id, "tool_name": "email_sender", "action": "Send email"},
            headers=auth_headers,
        )
        assert resp.status_code == 403
        assert "not in the Task Passport" in resp.json()["detail"]

    def test_execute_deny_external_blocks_api_caller(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        task_resp = client.post(
            "/api/tasks",
            json={
                "title": "Task",
                "purpose": "test",
                "allowed_tools": ["api_caller"],
                "network_policy": "deny_external",
            },
            headers=auth_headers,
        )
        task_id = task_resp.json()["task_id"]
        _authorize_passport(client, task_id, auth_headers)

        resp = client.post(
            "/api/sandbox/execute",
            json={"task_id": task_id, "tool_name": "api_caller", "action": "Call API"},
            headers=auth_headers,
        )
        assert resp.status_code == 403
        assert "deny_external" in resp.json()["detail"]

    def test_rollback_success(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        task_resp = client.post(
            "/api/tasks",
            json={"title": "Task", "purpose": "test", "allowed_tools": ["document_reader"]},
            headers=auth_headers,
        )
        task_id = task_resp.json()["task_id"]
        _authorize_passport(client, task_id, auth_headers)

        exec_resp = client.post(
            "/api/sandbox/execute",
            json={"task_id": task_id, "tool_name": "document_reader", "action": "Read"},
            headers=auth_headers,
        )
        execution_id = exec_resp.json()["execution_id"]

        rollback_resp = client.post(
            "/api/sandbox/rollback",
            json={"task_id": task_id, "execution_id": execution_id},
            headers=auth_headers,
        )
        assert rollback_resp.status_code == 200
        assert rollback_resp.json()["status"] == "rolled_back"

    def test_rollback_nonexistent_execution(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        resp = client.post(
            "/api/sandbox/rollback",
            json={"task_id": "x", "execution_id": "nonexistent"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
