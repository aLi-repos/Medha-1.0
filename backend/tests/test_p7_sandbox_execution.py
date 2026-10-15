"""P7 focused tests — ONE real isolated sandboxed code path.

Covers:
  1. Real child-process execution (25+17 → 42, not hard-coded)
  2. Filesystem isolation (host/MEDHA paths blocked)
  3. Network isolation (external connect blocked)
  4. Timeout terminates infinite loop
  5. Temp sandbox cleanup
  6. Code/input/output size limits
  7. Authorization (auth, ownership, allowlist, lifecycle)
  8. Action Gate + unknown tool
  9. Audit records
 10. Direct API cannot bypass authorization

MOCKED vs REAL: pytest mocks LLM transport only; code_runner subprocess is unmocked real.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.services.sandbox.code_runner import (
    MAX_CODE_BYTES,
    CodeSandboxError,
    run_isolated_python,
)
from app.services.sandbox.sandbox import (
    ExecutionStatus,
    ResourceLimits,
    sandbox_service,
)


def _authorize(client: TestClient, task_id: str, headers: dict[str, str]) -> None:
    client.patch(
        f"/api/tasks/{task_id}/status",
        json={"new_status": "authorized", "detail": "P7 authorization"},
        headers=headers,
    )


def _create_task(
    client: TestClient,
    headers: dict[str, str],
    allowed_tools: list[str] | None = None,
) -> str:
    resp = client.post(
        "/api/tasks",
        json={
            "title": "Pump P-204 calculation",
            "purpose": "Sandboxed code execution demo A+B",
            "allowed_tools": allowed_tools
            if allowed_tools is not None
            else ["code_executor"],
        },
        headers=headers,
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["task_id"]


# ── Real sandbox runner (unmocked subprocess) ────────────────────────────────


class TestRealSandboxRunner:
    def test_successful_execution_returns_42(self) -> None:
        run = run_isolated_python(
            "A = 25\nB = 17\nprint(A + B)\n",
            input_data={"A": 25, "B": 17},
            timeout_s=10,
        )
        assert run.status == "completed"
        assert run.output.strip() == "42"
        assert run.error == ""
        assert run.sandbox == "active"
        assert run.network == "blocked"
        assert run.timed_out is False

    def test_not_hardcoded_output_varies_with_input(self) -> None:
        run = run_isolated_python(
            "print(int(INPUT['A']) * 2)\n",
            input_data={"A": 21},
            timeout_s=10,
        )
        assert run.output.strip() == "42"

    def test_sandbox_temp_dir_cleaned(self, tmp_path: Path | None = None) -> None:
        import tempfile

        before = set(Path(tempfile.gettempdir()).glob("medha_sbx_*"))
        run_isolated_python("print('ok')\n", timeout_s=10)
        after = set(Path(tempfile.gettempdir()).glob("medha_sbx_*"))
        assert after == before

    def test_filesystem_host_path_blocked(self) -> None:
        # Attempt to read this process's own source (outside sandbox cwd).
        host_path = str(Path(__file__).resolve())
        run = run_isolated_python(
            f"open({host_path!r}).read()\n",
            timeout_s=10,
        )
        assert run.status == "failed"
        assert "filesystem access blocked" in run.error.lower() or "permissionerror" in run.error.lower() or "blocked" in run.error.lower()

    def test_filesystem_env_secrets_not_available(self) -> None:
        run = run_isolated_python(
            "import os\nprint(os.environ.get('MEDHA_JWT_SECRET', 'MISSING'))\n",
            timeout_s=10,
        )
        assert run.status == "completed"
        assert run.output.strip() == "MISSING"

    def test_network_external_blocked(self) -> None:
        run = run_isolated_python(
            "import socket\nsocket.create_connection(('example.com', 80), timeout=1)\n",
            timeout_s=10,
        )
        assert run.status == "failed"
        err = (run.error + run.output).lower()
        assert "blocked" in err or "network" in err or "permissionerror" in err

    def test_network_urllib_blocked(self) -> None:
        run = run_isolated_python(
            "import urllib.request\nurllib.request.urlopen('http://example.com', timeout=1)\n",
            timeout_s=10,
        )
        assert run.status == "failed"

    def test_timeout_terminates_infinite_loop(self) -> None:
        start = time.monotonic()
        run = run_isolated_python("while True:\n    pass\n", timeout_s=1.5)
        elapsed = time.monotonic() - start
        assert run.status == "timeout"
        assert run.timed_out is True
        assert elapsed < 15
        assert "exceeded" in run.error.lower() or "limit" in run.error.lower()

    def test_timeout_cleans_sandbox_dir(self) -> None:
        import tempfile

        before = set(Path(tempfile.gettempdir()).glob("medha_sbx_*"))
        run_isolated_python("while True:\n    pass\n", timeout_s=1)
        after = set(Path(tempfile.gettempdir()).glob("medha_sbx_*"))
        assert after == before

    def test_output_size_limit_rejected(self) -> None:
        run = run_isolated_python(
            "print('x' * 100000)\n",
            timeout_s=10,
            max_output_bytes=1000,
        )
        assert run.status == "failed"
        assert "output exceeded" in run.error.lower() or run.output_truncated

    def test_oversized_code_rejected(self) -> None:
        with pytest.raises(CodeSandboxError, match="byte limit"):
            run_isolated_python("x = 1\n" + "# pad\n" * 5000, timeout_s=5)

    def test_empty_code_rejected(self) -> None:
        with pytest.raises(CodeSandboxError):
            run_isolated_python("   \n", timeout_s=5)

    def test_null_byte_code_rejected(self) -> None:
        with pytest.raises(CodeSandboxError, match="null"):
            run_isolated_python("print(1)\x00", timeout_s=5)

    def test_subprocess_spawn_blocked(self) -> None:
        run = run_isolated_python(
            "import os\nos.system('echo pwned')\n",
            timeout_s=10,
        )
        assert run.status == "failed"
        assert "blocked" in (run.error + run.output).lower()


# ── SandboxService code_executor path ────────────────────────────────────────


class TestSandboxServiceCodeExecutor:
    def test_service_executes_real_code(self) -> None:
        result = sandbox_service.execute(
            tool_name="code_executor",
            action="A+B",
            input_data={"code": "print(25 + 17)", "A": 25, "B": 17},
            task_id="t-p7",
            user_id="u1",
            identity="op",
            role="operator",
        )
        assert result.status == ExecutionStatus.COMPLETED
        assert result.output.strip() == "42"
        assert result.sandbox == "active"
        assert result.network == "blocked"
        assert "[CodeExecutor]" not in result.output

    def test_missing_code_fails(self) -> None:
        result = sandbox_service.execute(
            tool_name="code_executor",
            action="no code",
            input_data={},
        )
        assert result.status == ExecutionStatus.FAILED
        assert "code is required" in result.error

    def test_oversized_code_fails_service(self) -> None:
        limits = ResourceLimits(max_code_bytes=100)
        result = sandbox_service.execute(
            tool_name="code_executor",
            action="big",
            input_data={"code": "# " + ("x" * 200)},
            resource_limits=limits,
        )
        assert result.status == ExecutionStatus.FAILED
        assert "byte limit" in result.error


# ── API authorization / Action Gate ──────────────────────────────────────────


class TestCodeExecutorAuthorization:
    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.post(
            "/api/sandbox/execute",
            json={"task_id": "x", "tool_name": "code_executor", "action": "run", "code": "print(1)"},
        )
        assert resp.status_code == 401

    def test_real_execution_via_api(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        task_id = _create_task(client, auth_headers)
        _authorize(client, task_id, auth_headers)
        resp = client.post(
            "/api/sandbox/execute",
            json={
                "task_id": task_id,
                "tool_name": "code_executor",
                "action": "Pump P-204 A+B",
                "code": "A = INPUT.get('A', 0)\nB = INPUT.get('B', 0)\nprint(A + B)",
                "input_data": {"A": 25, "B": 17},
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "completed"
        assert body["output"].strip() == "42"
        assert body["sandbox"] == "active"
        assert body["network"] == "blocked"

    def test_draft_task_blocked(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        task_id = _create_task(client, auth_headers)
        # no authorize — still draft
        resp = client.post(
            "/api/sandbox/execute",
            json={"task_id": task_id, "tool_name": "code_executor", "action": "x", "code": "print(1)"},
            headers=auth_headers,
        )
        assert resp.status_code == 403

    def test_tool_not_in_allowlist_blocked(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        task_id = _create_task(client, auth_headers, allowed_tools=["document_reader"])
        _authorize(client, task_id, auth_headers)
        resp = client.post(
            "/api/sandbox/execute",
            json={"task_id": task_id, "tool_name": "code_executor", "action": "x", "code": "print(1)"},
            headers=auth_headers,
        )
        assert resp.status_code == 403
        assert "not in the Task Passport" in resp.json()["detail"]

    def test_unknown_tool_blocked(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        task_id = _create_task(client, auth_headers, allowed_tools=["document_reader", "evil_tool"])
        _authorize(client, task_id, auth_headers)
        resp = client.post(
            "/api/sandbox/execute",
            json={"task_id": task_id, "tool_name": "evil_tool", "action": "x"},
            headers=auth_headers,
        )
        assert resp.status_code == 403
        assert "Unknown tool" in resp.json()["detail"]

    def test_wrong_owner_blocked(self, client: TestClient, auth_headers: dict[str, str], engineer_headers: dict[str, str]) -> None:
        task_id = _create_task(client, auth_headers)
        _authorize(client, task_id, auth_headers)
        resp = client.post(
            "/api/sandbox/execute",
            json={"task_id": task_id, "tool_name": "code_executor", "action": "x", "code": "print(1)"},
            headers=engineer_headers,
        )
        assert resp.status_code == 403

    def test_completed_task_cannot_execute(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        task_id = _create_task(client, auth_headers)
        _authorize(client, task_id, auth_headers)
        # move to completed via authorized → executing → completed
        client.patch(
            f"/api/tasks/{task_id}/status",
            json={"new_status": "executing", "detail": "start"},
            headers=auth_headers,
        )
        client.patch(
            f"/api/tasks/{task_id}/status",
            json={"new_status": "completed", "detail": "done"},
            headers=auth_headers,
        )
        resp = client.post(
            "/api/sandbox/execute",
            json={"task_id": task_id, "tool_name": "code_executor", "action": "x", "code": "print(1)"},
            headers=auth_headers,
        )
        assert resp.status_code == 403

    def test_oversized_code_schema_rejected(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        task_id = _create_task(client, auth_headers)
        _authorize(client, task_id, auth_headers)
        resp = client.post(
            "/api/sandbox/execute",
            json={
                "task_id": task_id,
                "tool_name": "code_executor",
                "action": "x",
                "code": "x = 1\n" * 5000,  # exceeds max_length
            },
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_missing_task_404(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        resp = client.post(
            "/api/sandbox/execute",
            json={"task_id": "no-such-task", "tool_name": "code_executor", "action": "x", "code": "print(1)"},
            headers=auth_headers,
        )
        assert resp.status_code == 404


# ── Audit ────────────────────────────────────────────────────────────────────


class TestCodeExecutorAudit:
    def test_audit_records_execution(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        from app.services.audit_service import audit_service

        audit_service.clear()
        task_id = _create_task(client, auth_headers)
        _authorize(client, task_id, auth_headers)
        client.post(
            "/api/sandbox/execute",
            json={
                "task_id": task_id,
                "tool_name": "code_executor",
                "action": "A+B",
                "code": "print(25 + 17)",
            },
            headers=auth_headers,
        )
        events = audit_service.get_events_for_task(task_id)
        types = {e.event_type for e in events}
        assert "sandbox_execution_started" in types
        assert "sandbox_execution_completed" in types
        completed = [e for e in events if e.event_type == "sandbox_execution_completed"]
        assert completed
        detail = completed[-1].detail
        assert "status=completed" in detail
        assert "sandbox=active" in detail
        assert "network=blocked" in detail


# ── Agent path (plan → Action Gate → code_executor) ──────────────────────────


class TestAgentCodeExecutorPath:
    def test_plan_execute_step_real_sandbox(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        task_id = _create_task(client, auth_headers)
        _authorize(client, task_id, auth_headers)
        plan_resp = client.post(
            "/api/agent/plan",
            json={"task_id": task_id, "query": "execute code calculation for A+B"},
            headers=auth_headers,
        )
        assert plan_resp.status_code == 201, plan_resp.text
        plan = plan_resp.json()
        step = next(s for s in plan["steps"] if s["tool_name"] == "code_executor")
        # high-risk step requires approval
        appr = client.post(
            "/api/agent/plan/approve-step",
            json={"plan_id": plan["plan_id"], "step_id": step["step_id"]},
            headers=auth_headers,
        )
        assert appr.status_code == 200, appr.text
        ex = client.post(
            "/api/agent/plan/execute-step",
            json={
                "plan_id": plan["plan_id"],
                "step_id": step["step_id"],
                "input_data": {"code": "print(25 + 17)"},
            },
            headers=auth_headers,
        )
        assert ex.status_code == 200, ex.text
        body = ex.json()
        assert body["success"] is True
        assert body["output"].strip() == "42"
        assert body["sandbox"] == "active"
        assert body["network"] == "blocked"

    def test_agent_unapproved_step_blocked(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        task_id = _create_task(client, auth_headers)
        _authorize(client, task_id, auth_headers)
        plan = client.post(
            "/api/agent/plan",
            json={"task_id": task_id, "query": "execute code now"},
            headers=auth_headers,
        ).json()
        step = next(s for s in plan["steps"] if s["tool_name"] == "code_executor")
        ex = client.post(
            "/api/agent/plan/execute-step",
            json={
                "plan_id": plan["plan_id"],
                "step_id": step["step_id"],
                "input_data": {"code": "print(1)"},
            },
            headers=auth_headers,
        )
        # PENDING high-risk step is rejected before sandbox runs (400 approval gate)
        assert ex.status_code in (400, 403)
        body = ex.json()
        assert "approval" in body.get("detail", "").lower() or "approval" in str(body).lower()
        assert ex.json().get("output") is None
