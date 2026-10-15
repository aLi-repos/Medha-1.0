"""Tests for Stage 6 — Controlled Agent Planner + Tool Registry."""

import pytest
from fastapi.testclient import TestClient

from app.services.agent.planner import AgentPlanner, ExecutionPlan, PlanStatus, StepStatus
from app.services.agent.service import AgentService
from app.services.agent.tool_registry import ToolDefinition, ToolRegistry, ToolRisk, tool_registry


# ── Tool Registry Tests ──

class TestToolRegistry:
    def test_list_all_tools(self) -> None:
        tools = tool_registry.list_all()
        assert len(tools) >= 5
        names = {t.name for t in tools}
        assert "document_reader" in names
        assert "data_analyzer" in names
        assert "email_sender" in names

    def test_get_tool_by_name(self) -> None:
        tool = tool_registry.get("document_reader")
        assert tool is not None
        assert tool.name == "document_reader"
        assert tool.risk == ToolRisk.LOW

    def test_get_nonexistent_tool(self) -> None:
        assert tool_registry.get("nonexistent") is None

    def test_is_tool_allowed_empty_list(self) -> None:
        assert tool_registry.is_tool_allowed("document_reader", [])

    def test_is_tool_allowed_in_list(self) -> None:
        assert tool_registry.is_tool_allowed("document_reader", ["document_reader", "data_analyzer"])

    def test_is_tool_allowed_not_in_list(self) -> None:
        assert not tool_registry.is_tool_allowed("email_sender", ["document_reader"])

    def test_get_allowed_tools_filters(self) -> None:
        allowed = tool_registry.get_allowed_tools(["document_reader", "data_analyzer"])
        assert len(allowed) == 2
        names = {t.name for t in allowed}
        assert "document_reader" in names
        assert "email_sender" not in names

    def test_email_sender_requires_approval(self) -> None:
        tool = tool_registry.get("email_sender")
        assert tool is not None
        assert tool.requires_approval is True
        assert tool.risk == ToolRisk.HIGH


# ── Planner Tests ──

class TestAgentPlanner:
    def test_create_plan_with_steps(self) -> None:
        planner = AgentPlanner()
        plan = planner.create_plan("Read the inspection report and analyze the data", "task-1")
        assert isinstance(plan, ExecutionPlan)
        assert len(plan.steps) >= 2
        assert plan.task_id == "task-1"

    def test_plan_respects_allowed_tools(self) -> None:
        planner = AgentPlanner()
        plan = planner.create_plan(
            "Read the report and send email",
            "task-1",
            allowed_tools=["document_reader"],
        )
        tool_names = {s.tool_name for s in plan.steps}
        assert "document_reader" in tool_names
        assert "email_sender" not in tool_names

    def test_plan_default_step(self) -> None:
        planner = AgentPlanner()
        plan = planner.create_plan("Do something random", "task-1")
        assert len(plan.steps) >= 1

    def test_plan_generates_audit_events(self) -> None:
        from app.services.audit_service import audit_service
        audit_service.clear()
        planner = AgentPlanner()
        plan = planner.create_plan("Read and analyze", "task-1", user_id="u1", identity="u1", role="engineer")
        events = audit_service.get_events_for_task("task-1")
        assert len(events) >= 1


# ── Agent Service Tests ──

class TestAgentService:
    def test_create_and_get_plan(self) -> None:
        svc = AgentService()
        plan = svc.create_plan("Read the report", "task-1")
        retrieved = svc.get_plan(plan.plan_id)
        assert retrieved is not None
        assert retrieved.plan_id == plan.plan_id

    def test_approve_step(self) -> None:
        svc = AgentService()
        plan = svc.create_plan("Send email notification", "task-1")
        approval_steps = [s for s in plan.steps if s.requires_approval]
        if approval_steps:
            step = svc.approve_step(plan.plan_id, approval_steps[0].step_id, user_id="u1", identity="u1", role="admin")
            assert step.status == StepStatus.APPROVED

    def test_execute_step_without_approval(self) -> None:
        svc = AgentService()
        plan = svc.create_plan("Read the document", "task-1")
        non_approval_steps = [s for s in plan.steps if not s.requires_approval]
        if non_approval_steps:
            result = svc.execute_step(plan.plan_id, non_approval_steps[0].step_id, user_id="u1", identity="u1", role="engineer")
            assert result["success"] is True

    def test_execute_approval_required_step_without_approval_fails(self) -> None:
        svc = AgentService()
        plan = svc.create_plan("Send email notification", "task-1")
        approval_steps = [s for s in plan.steps if s.requires_approval]
        if approval_steps:
            with pytest.raises(ValueError, match="requires approval"):
                svc.execute_step(plan.plan_id, approval_steps[0].step_id, user_id="u1", identity="u1", role="engineer")

    def test_plan_not_found_returns_none(self) -> None:
        svc = AgentService()
        assert svc.get_plan("nonexistent") is None

    def test_reset_clears_plans(self) -> None:
        svc = AgentService()
        svc.create_plan("Read", "task-1")
        svc.reset()
        assert len(svc._plans) == 0


# ── API Integration Tests ──


def _authorize_passport(client: TestClient, task_id: str, headers: dict[str, str]) -> None:
    """Helper: transition a passport from draft to authorized."""
    client.patch(
        f"/api/tasks/{task_id}/status",
        json={"new_status": "authorized", "detail": "Test authorization"},
        headers=headers,
    )


class TestAgentAPI:
    def test_create_plan(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        task_resp = client.post(
            "/api/tasks",
            json={"title": "Analyze data", "purpose": "Test agent planning"},
            headers=auth_headers,
        )
        task_id = task_resp.json()["task_id"]
        _authorize_passport(client, task_id, auth_headers)

        resp = client.post(
            "/api/agent/plan",
            json={"task_id": task_id, "query": "Read the inspection report and generate a summary"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["plan_id"]
        assert len(body["steps"]) >= 1
        assert body["status"] == "created"

    def test_create_plan_requires_auth(self, client: TestClient) -> None:
        resp = client.post("/api/agent/plan", json={"task_id": "x", "query": "hello"})
        assert resp.status_code == 401

    def test_create_plan_nonexistent_task(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        resp = client.post(
            "/api/agent/plan",
            json={"task_id": "nonexistent", "query": "hello"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_list_tools(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        resp = client.get("/api/agent/tools", headers=auth_headers)
        assert resp.status_code == 200
        tools = resp.json()["tools"]
        assert len(tools) >= 5
        tool_names = {t["name"] for t in tools}
        assert "document_reader" in tool_names

    def test_execute_step_flow(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        task_resp = client.post(
            "/api/tasks",
            json={"title": "Task", "purpose": "test", "allowed_tools": ["document_reader"]},
            headers=auth_headers,
        )
        task_id = task_resp.json()["task_id"]
        _authorize_passport(client, task_id, auth_headers)

        plan_resp = client.post(
            "/api/agent/plan",
            json={"task_id": task_id, "query": "Read the inspection document"},
            headers=auth_headers,
        )
        plan = plan_resp.json()
        step = plan["steps"][0]

        exec_resp = client.post(
            "/api/agent/plan/execute-step",
            json={"plan_id": plan["plan_id"], "step_id": step["step_id"]},
            headers=auth_headers,
        )
        assert exec_resp.status_code == 200
        assert exec_resp.json()["success"] is True

    def test_plan_respects_allowed_tools(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        task_resp = client.post(
            "/api/tasks",
            json={
                "title": "Restricted task",
                "purpose": "test",
                "allowed_tools": ["document_reader"],
            },
            headers=auth_headers,
        )
        task_id = task_resp.json()["task_id"]
        _authorize_passport(client, task_id, auth_headers)

        plan_resp = client.post(
            "/api/agent/plan",
            json={"task_id": task_id, "query": "Read report and send email notification"},
            headers=auth_headers,
        )
        plan = plan_resp.json()
        tool_names = {s["tool_name"] for s in plan["steps"]}
        assert "document_reader" in tool_names
        assert "email_sender" not in tool_names
