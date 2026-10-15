"""P5 focused tests — ONE real tool execution (data_analyzer) through the agent pipeline.

Covers:
  1. Planner deterministically selects data_analyzer for analysis queries
  2. Real statistics computed (not hard-coded / not [Simulated])
  3. Demo-safe synthetic Pump P-204 dataset used when no input
  4. Action Gate blocks unauthorized tool
  5. Action Gate blocks non-authorized task lifecycle
  6. Action Gate blocks empty allowlist (fail-closed)
  7. Cross-user cannot execute another's plan step
  8. Path-like / malformed input rejected (fail closed, no execution)
  9. Unexpected tool name does not execute data_analyzer path
 10. Audit records actor/task/tool/result
 11. Unauthenticated cannot execute
 Happy path: full API chain plan → execute-step with real output
 Regression: other tools remain simulated (unchanged)
 MOCKED vs REAL: pytest transport-mocks LLM only; data_analyzer is unmocked real code
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.services.agent.service import agent_service
from app.services.agent.tools.data_analyzer import (
    DEMO_PUMP_P204_MEASUREMENTS,
    DataAnalyzerError,
    analyze,
    compute_stats,
)
from app.services.audit_service import audit_service


def _authorize_passport(client: TestClient, task_id: str, headers: dict[str, str]) -> None:
    client.patch(
        f"/api/tasks/{task_id}/status",
        json={"new_status": "authorized", "detail": "P5 test authorization"},
        headers=headers,
    )


def _create_authorized_task(
    client: TestClient,
    headers: dict[str, str],
    allowed_tools: list[str] | None = None,
) -> str:
    payload = {
        "title": "Pump P-204 analysis",
        "purpose": "Calculate basic statistics on inspection measurements",
        "allowed_tools": allowed_tools if allowed_tools is not None else ["data_analyzer"],
    }
    resp = client.post("/api/tasks", json=payload, headers=headers)
    assert resp.status_code in (200, 201), resp.text
    task_id = resp.json()["task_id"]
    _authorize_passport(client, task_id, headers)
    return task_id


# ── Analyzer unit (REAL computation, no mocks) ──────────────────────────────


class TestDataAnalyzerReal:
    def test_real_stats_on_known_values(self) -> None:
        out = analyze("Compute mean", {"measurements": [1.0, 2.0, 3.0, 4.0]})
        assert "[DataAnalyzer]" in out
        assert "mean=2.5000" in out
        assert "[Simulated]" not in out

    def test_demo_dataset_when_empty_input(self) -> None:
        out = analyze("Analyze Pump P-204", {})
        assert "temperature_c" in out
        assert "demo-safe synthetic Pump P-204" in out
        assert "n=8" in out

    def test_compute_stats_fields(self) -> None:
        s = compute_stats([10.0, 20.0, 30.0])
        assert s["count"] == 3
        assert s["mean"] == 20.0
        assert s["min"] == 10.0
        assert s["max"] == 30.0

    def test_path_like_key_rejected(self) -> None:
        with pytest.raises(DataAnalyzerError):
            analyze("x", {"series": {"../../etc/passwd": [1.0, 2.0]}})

    def test_non_numeric_rejected(self) -> None:
        with pytest.raises(DataAnalyzerError):
            analyze("x", {"measurements": [1.0, "evil", 3.0]})

    def test_oversized_series_rejected(self) -> None:
        with pytest.raises(DataAnalyzerError):
            analyze("x", {"measurements": [1.0] * 5001})

    def test_demo_measurements_are_synthetic_labeled(self) -> None:
        assert DEMO_PUMP_P204_MEASUREMENTS["temperature_c"][0] == 58.2
        assert len(DEMO_PUMP_P204_MEASUREMENTS) >= 3


# ── Security / Action Gate (API) ────────────────────────────────────────────


class TestP5Security:
    def test_unauthenticated_cannot_execute(self, client: TestClient) -> None:
        resp = client.post(
            "/api/agent/plan/execute-step",
            json={"plan_id": "x", "step_id": "y"},
        )
        assert resp.status_code == 401

    def test_planner_selects_data_analyzer(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        task_id = _create_authorized_task(client, auth_headers)
        resp = client.post(
            "/api/agent/plan",
            json={
                "task_id": task_id,
                "query": "Analyze the Pump P-204 inspection measurements and calculate statistics",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        tools = [s["tool_name"] for s in resp.json()["steps"]]
        assert "data_analyzer" in tools

    def test_blocked_tool_not_in_allowlist(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        task_id = _create_authorized_task(client, auth_headers, allowed_tools=["document_reader"])
        plan_resp = client.post(
            "/api/agent/plan",
            json={"task_id": task_id, "query": "Analyze data and calculate statistics"},
            headers=auth_headers,
        )
        # planner respects allowlist — data_analyzer not planned
        tools = [s["tool_name"] for s in plan_resp.json()["steps"]]
        assert "data_analyzer" not in tools

    def test_empty_allowlist_blocks_execution(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        task_id = _create_authorized_task(client, auth_headers, allowed_tools=[])
        # Force-create a plan via service then try execute — Action Gate must fail closed.
        # With empty allowlist, planner may default to document_reader; instead craft plan
        # by temporarily using a task with data_analyzer then switching is hard.
        # Direct: plan with query that yields no allowed tools → empty steps → no execute.
        plan_resp = client.post(
            "/api/agent/plan",
            json={"task_id": task_id, "query": "analyze data"},
            headers=auth_headers,
        )
        steps = plan_resp.json()["steps"]
        # empty allowlist → is_tool_allowed returns True for empty in registry,
        # but Action Gate fail-closed on execute. Force a plan step by service:
        # If steps empty, create via agent_service directly with allowed_tools=[]
        if not steps:
            # registry allows empty → planner adds document_reader default; but
            # with data_analyzer query and empty list, is_tool_allowed(name, []) is True
            # so data_analyzer may be planned. Either way execute must be blocked by Action Gate.
            pass
        # Build a plan that includes data_analyzer by using service with empty allowlist
        plan = agent_service.create_plan(
            query="analyze data",
            task_id=task_id,
            allowed_tools=[],
            user_id="u",
            identity="operator",
            role="operator",
        )
        da_steps = [s for s in plan.steps if s.tool_name == "data_analyzer"]
        if not da_steps:
            # planner may have chosen document_reader; still verify Action Gate on any step
            step = plan.steps[0]
        else:
            step = da_steps[0]
        resp = client.post(
            "/api/agent/plan/execute-step",
            json={"plan_id": plan.plan_id, "step_id": step.step_id},
            headers=auth_headers,
        )
        assert resp.status_code == 403
        assert "allowlist" in resp.json()["detail"].lower() or "not permitted" in resp.json()["detail"].lower()

    def test_draft_task_blocks_execute(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = client.post(
            "/api/tasks",
            json={
                "title": "Draft",
                "purpose": "test",
                "allowed_tools": ["data_analyzer"],
            },
            headers=auth_headers,
        )
        task_id = resp.json()["task_id"]
        # leave draft
        plan_resp = client.post(
            "/api/agent/plan",
            json={"task_id": task_id, "query": "analyze data"},
            headers=auth_headers,
        )
        # COMPUTE may be blocked in draft too
        if plan_resp.status_code == 201 and plan_resp.json()["steps"]:
            step = plan_resp.json()["steps"][0]
            exec_resp = client.post(
                "/api/agent/plan/execute-step",
                json={"plan_id": plan_resp.json()["plan_id"], "step_id": step["step_id"]},
                headers=auth_headers,
            )
            assert exec_resp.status_code == 403
        else:
            assert plan_resp.status_code == 403

    def test_path_like_input_rejected_not_executed(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        task_id = _create_authorized_task(client, auth_headers)
        plan_resp = client.post(
            "/api/agent/plan",
            json={"task_id": task_id, "query": "Analyze data"},
            headers=auth_headers,
        )
        plan = plan_resp.json()
        step = next(s for s in plan["steps"] if s["tool_name"] == "data_analyzer")
        resp = client.post(
            "/api/agent/plan/execute-step",
            json={
                "plan_id": plan["plan_id"],
                "step_id": step["step_id"],
                "input_data": {"series": {"../../secret": [1, 2]}},
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert "[DataAnalyzer] Analysis complete" not in body["output"]
        assert "failed" in body["output"].lower()

    def test_non_numeric_input_rejected(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        task_id = _create_authorized_task(client, auth_headers)
        plan_resp = client.post(
            "/api/agent/plan",
            json={"task_id": task_id, "query": "Analyze data"},
            headers=auth_headers,
        )
        plan = plan_resp.json()
        step = next(s for s in plan["steps"] if s["tool_name"] == "data_analyzer")
        resp = client.post(
            "/api/agent/plan/execute-step",
            json={
                "plan_id": plan["plan_id"],
                "step_id": step["step_id"],
                "input_data": {"measurements": ["not-a-number"]},
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is False

    def test_cross_user_cannot_execute(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        engineer_headers: dict[str, str],
    ) -> None:
        task_id = _create_authorized_task(client, auth_headers)
        plan_resp = client.post(
            "/api/agent/plan",
            json={"task_id": task_id, "query": "Analyze data"},
            headers=auth_headers,
        )
        plan = plan_resp.json()
        step = next(s for s in plan["steps"] if s["tool_name"] == "data_analyzer")
        # engineer does not own the passport
        resp = client.post(
            "/api/agent/plan/execute-step",
            json={"plan_id": plan["plan_id"], "step_id": step["step_id"]},
            headers=engineer_headers,
        )
        assert resp.status_code == 403
        assert "identity" in resp.json()["detail"].lower() or "passport" in resp.json()["detail"].lower()

    def test_audit_records_execution(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        audit_service.clear()
        task_id = _create_authorized_task(client, auth_headers)
        plan_resp = client.post(
            "/api/agent/plan",
            json={"task_id": task_id, "query": "Analyze data"},
            headers=auth_headers,
        )
        plan = plan_resp.json()
        step = next(s for s in plan["steps"] if s["tool_name"] == "data_analyzer")
        client.post(
            "/api/agent/plan/execute-step",
            json={"plan_id": plan["plan_id"], "step_id": step["step_id"]},
            headers=auth_headers,
        )
        events = audit_service.get_events_for_task(task_id)
        types = {e.event_type for e in events}
        assert "plan_created" in types
        assert "plan_step_completed" in types
        completed = [e for e in events if e.event_type == "plan_step_completed"]
        assert completed
        assert "data_analyzer" in completed[0].detail
        assert completed[0].task_id == task_id
        assert completed[0].identity == "operator"

    def test_unexpected_tool_name_does_not_run_data_analyzer(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        task_id = _create_authorized_task(
            client, auth_headers, allowed_tools=["document_reader", "data_analyzer"]
        )
        plan_resp = client.post(
            "/api/agent/plan",
            json={"task_id": task_id, "query": "Read documents"},
            headers=auth_headers,
        )
        plan = plan_resp.json()
        # force a document_reader step (not data_analyzer)
        step = next(s for s in plan["steps"] if s["tool_name"] == "document_reader")
        resp = client.post(
            "/api/agent/plan/execute-step",
            json={
                "plan_id": plan["plan_id"],
                "step_id": step["step_id"],
                "input_data": {"measurements": [1, 2, 3]},
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        out = resp.json()["output"]
        assert "[Simulated]" in out
        assert "mean=" not in out


# ── Happy path: full chain with REAL data_analyzer ──────────────────────────


class TestP5HappyPath:
    def test_full_chain_real_execution(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        task_id = _create_authorized_task(client, auth_headers)
        plan_resp = client.post(
            "/api/agent/plan",
            json={
                "task_id": task_id,
                "query": "Analyze the Pump P-204 inspection measurements and calculate basic statistics",
            },
            headers=auth_headers,
        )
        assert plan_resp.status_code == 201
        plan = plan_resp.json()
        step = next(s for s in plan["steps"] if s["tool_name"] == "data_analyzer")
        assert step["requires_approval"] is False
        assert step["risk"] == "low"

        exec_resp = client.post(
            "/api/agent/plan/execute-step",
            json={"plan_id": plan["plan_id"], "step_id": step["step_id"]},
            headers=auth_headers,
        )
        assert exec_resp.status_code == 200
        body = exec_resp.json()
        assert body["success"] is True
        assert body["tool_name"] == "data_analyzer"
        assert "[DataAnalyzer]" in body["output"]
        assert "[Simulated]" not in body["output"]
        assert "temperature_c" in body["output"]
        assert "mean=" in body["output"]

    def test_custom_measurements_real_stats(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        task_id = _create_authorized_task(client, auth_headers)
        plan_resp = client.post(
            "/api/agent/plan",
            json={"task_id": task_id, "query": "Analyze data"},
            headers=auth_headers,
        )
        plan = plan_resp.json()
        step = next(s for s in plan["steps"] if s["tool_name"] == "data_analyzer")
        exec_resp = client.post(
            "/api/agent/plan/execute-step",
            json={
                "plan_id": plan["plan_id"],
                "step_id": step["step_id"],
                "input_data": {"measurements": [10.0, 20.0, 30.0]},
            },
            headers=auth_headers,
        )
        assert exec_resp.status_code == 200
        out = exec_resp.json()["output"]
        assert "mean=20.0000" in out

    def test_tools_endpoint_lists_data_analyzer(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = client.get("/api/agent/tools", headers=auth_headers)
        assert resp.status_code == 200
        names = {t["name"] for t in resp.json()["tools"]}
        assert "data_analyzer" in names
