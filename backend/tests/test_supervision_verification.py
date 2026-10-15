"""Focused tests: role-based supervision + before/after human verification.

Covers the 25 required scenarios:
  1  six provisioned users exist correctly
  2  user_id is authoritative
  3  duplicate usernames remain separate
  4  manager can view operator task
  5  manager can view junior engineer task
  6  manager can view monitor task
  7  admin can view operator task
  8  admin can view junior engineer task
  9  admin can view monitor task
 10  worker cannot view another worker's task
 11  worker cannot bypass task authorization with task_id / supervision page
 12  worker cannot approve own task
 13  unauthorized user cannot approve task
 14  manager can approve authorized (supervised) task
 15  admin can approve authorized (supervised) task
 16  rejection requires reason
 17  unapproved task cannot execute when approval is required
 18  completed task enters completion verification
 19  manager can verify completion
 20  admin can verify completion
 21  completion rejection requires reason
 22  every supervisory action is audited
 23  frontend build succeeds (verified separately via `npm run build`)
 24  existing authentication still works
 25  existing tasks/data remain intact (idempotent seeding)
"""

from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.services.user_service import user_service

SIX_USERS = [
    ("nagarjuna", "medha-nagarjuna-2026", "SE00503", "senior_engineer"),
    ("lokesh", "medha-lokesh-2026", "AD00637", "admin"),
    ("Ali", "medha-ali-2026", "MD00574", "manager"),
    ("Balaji", "medha-balaji-2026", "OP00303", "operator"),
    ("keerthi", "medha-keerthi-2026", "JE00589", "junior_engineer"),
    ("saniya", "medha-saniya-2026", "MO00579", "monitor"),
]


def _login(client: TestClient, username: str, password: str, user_id: str | None = None) -> str:
    body: dict = {"username": username, "password": password}
    if user_id:
        body["user_id"] = user_id
    resp = client.post("/api/auth/login", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _me(client: TestClient, token: str) -> dict:
    resp = client.get("/api/auth/me", headers=_h(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


def _create_task(
    client: TestClient,
    token: str,
    title: str,
    approval: str = "none",
    tools: list[str] | None = None,
) -> dict:
    payload = {
        "title": title,
        "purpose": "role supervision and human verification test",
        "approval_requirement": approval,
        "allowed_tools": tools or ["document_reader"],
    }
    resp = client.post("/api/tasks", json=payload, headers=_h(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


def _transition(client: TestClient, token: str, task_id: str, new_status: str):
    return client.patch(
        f"/api/tasks/{task_id}/status",
        json={"new_status": new_status, "detail": f"transition to {new_status}"},
        headers=_h(token),
    )


def _submit(client: TestClient, token: str, task_id: str) -> dict:
    """Submit a draft task for human verification."""
    resp = _transition(client, token, task_id, "pending_approval")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "pending_approval"
    return resp.json()


def _audit(client: TestClient, token: str, task_id: str) -> list[dict]:
    resp = client.get(f"/api/verifier/audit/{task_id}", headers=_h(token))
    assert resp.status_code == 200, resp.text
    return resp.json()["events"]


def _audit_types(client: TestClient, token: str, task_id: str) -> set[str]:
    return {e["event_type"] for e in _audit(client, token, task_id)}


def _approve(client: TestClient, supervisor_token: str, task_id: str):
    return client.post(
        f"/api/supervision/tasks/{task_id}/approve", headers=_h(supervisor_token)
    )


def _reject(client: TestClient, supervisor_token: str, task_id: str, reason: str | None):
    url = f"/api/supervision/tasks/{task_id}/reject"
    if reason is None:
        return client.post(url, headers=_h(supervisor_token))
    return client.post(url, json={"reason": reason}, headers=_h(supervisor_token))


def _verify_completion(client: TestClient, supervisor_token: str, task_id: str):
    return client.post(
        f"/api/supervision/tasks/{task_id}/verify-completion",
        headers=_h(supervisor_token),
    )


def _reject_completion(
    client: TestClient, supervisor_token: str, task_id: str, reason: str | None
):
    url = f"/api/supervision/tasks/{task_id}/reject-completion"
    if reason is None:
        return client.post(url, headers=_h(supervisor_token))
    return client.post(url, json={"reason": reason}, headers=_h(supervisor_token))


def _to_pending_verification(
    client: TestClient, worker_token: str, task_id: str, supervisor_token: str
) -> str:
    """draft → pending_approval → approved → executing → completed (auto)."""
    _submit(client, worker_token, task_id)
    resp = _approve(client, supervisor_token, task_id)
    assert resp.status_code == 200, resp.text
    resp = _transition(client, worker_token, task_id, "executing")
    assert resp.status_code == 200, resp.text
    resp = _transition(client, worker_token, task_id, "completed")
    assert resp.status_code == 200, resp.text
    return resp.json()["status"]


# ── 1. six provisioned users ────────────────────────────────────────────────

class TestSixUsersExist:
    def test_six_org_users_exist_with_correct_roles(self, client: TestClient) -> None:
        for username, password, uid, role in SIX_USERS:
            token = _login(client, username, password)
            me = _me(client, token)
            assert me["user_id"] == uid
            assert me["role"] == role
            assert me["username"] == username


# ── 2. user_id is authoritative ─────────────────────────────────────────────

class TestUserIdAuthoritative:
    def test_login_and_rename_keep_user_id_authoritative(
        self, client: TestClient
    ) -> None:
        token = _login(client, "Balaji", "medha-balaji-2026", user_id="OP00303")
        assert _me(client, token)["user_id"] == "OP00303"

        task = _create_task(client, token, "UID-AUTH-TASK")

        rename = client.patch(
            "/api/auth/username",
            json={"username": "balaji.renamed"},
            headers=_h(token),
        )
        assert rename.status_code == 200
        assert rename.json()["user_id"] == "OP00303"
        assert rename.json()["role"] == "operator"

        new_token = _login(
            client, "balaji.renamed", "medha-balaji-2026", user_id="OP00303"
        )
        me = _me(client, new_token)
        assert me["user_id"] == "OP00303"
        tasks = client.get("/api/tasks", headers=_h(new_token)).json()
        assert any(t["task_id"] == task["task_id"] for t in tasks)


# ── 3. duplicate usernames remain separate ──────────────────────────────────

class TestDuplicateUsernames:
    def test_duplicate_username_accounts_stay_separate(
        self, client: TestClient
    ) -> None:
        original = _login(client, "Balaji", "medha-balaji-2026")
        assert _me(client, original)["user_id"] == "OP00303"

        reg = client.post(
            "/api/auth/register",
            json={"username": "Balaji", "password": "twin-balaji-77", "role": "operator"},
        )
        assert reg.status_code == 201, reg.text
        twin_token = reg.json()["access_token"]
        twin = _me(client, twin_token)
        assert twin["user_id"] != "OP00303"

        # Different passwords disambiguate duplicate usernames at login.
        again_original = _login(client, "Balaji", "medha-balaji-2026")
        assert _me(client, again_original)["user_id"] == "OP00303"
        again_twin = _login(client, "Balaji", "twin-balaji-77")
        assert _me(client, again_twin)["user_id"] == twin["user_id"]


# ── 4-9. manager/admin can view supervised worker tasks ─────────────────────

class TestSupervisorCanViewWorkerTasks:
    def _assert_manager_views(self, client, worker_token, task) -> None:
        ali = _login(client, "Ali", "medha-ali-2026")

        get_resp = client.get(f"/api/tasks/{task['task_id']}", headers=_h(ali))
        assert get_resp.status_code == 200, get_resp.text
        assert get_resp.json()["task_id"] == task["task_id"]

        detail = client.get(
            f"/api/supervision/tasks/{task['task_id']}", headers=_h(ali)
        )
        assert detail.status_code == 200, detail.text
        body = detail.json()
        assert body["task"]["task_id"] == task["task_id"]
        assert body["task"]["user_id"] == task["user_id"]
        assert "audit_events" in body and "verifications" in body

        worker = client.get(f"/api/verifier/audit/{task['task_id']}", headers=_h(worker_token))
        types = {e["event_type"] for e in worker.json()["events"]}
        assert "MANAGER_VIEW_TASK" in types
        assert "MANAGER_VIEW_TRACE" in types

        lst = client.get("/api/supervision/tasks", headers=_h(ali))
        assert lst.status_code == 200
        assert any(t["task_id"] == task["task_id"] for t in lst.json()["tasks"])

    def _assert_admin_views(self, client, worker_token, task) -> None:
        lokesh = _login(client, "lokesh", "medha-lokesh-2026")

        get_resp = client.get(f"/api/tasks/{task['task_id']}", headers=_h(lokesh))
        assert get_resp.status_code == 200, get_resp.text

        detail = client.get(
            f"/api/supervision/tasks/{task['task_id']}", headers=_h(lokesh)
        )
        assert detail.status_code == 200, detail.text
        assert detail.json()["task"]["task_id"] == task["task_id"]

        worker = client.get(f"/api/verifier/audit/{task['task_id']}", headers=_h(worker_token))
        types = {e["event_type"] for e in worker.json()["events"]}
        assert "ADMIN_VIEW_TASK" in types
        assert "ADMIN_VIEW_TRACE" in types

    def test_4_manager_views_operator_task(self, client: TestClient) -> None:
        balaji = _login(client, "Balaji", "medha-balaji-2026")
        task = _create_task(client, balaji, "MGR-OP-TASK")
        self._assert_manager_views(client, balaji, task)

    def test_5_manager_views_junior_engineer_task(self, client: TestClient) -> None:
        keerthi = _login(client, "keerthi", "medha-keerthi-2026")
        task = _create_task(client, keerthi, "MGR-JE-TASK")
        self._assert_manager_views(client, keerthi, task)

    def test_6_manager_views_monitor_task(self, client: TestClient) -> None:
        saniya = _login(client, "saniya", "medha-saniya-2026")
        task = _create_task(client, saniya, "MGR-MO-TASK")
        self._assert_manager_views(client, saniya, task)

    def test_7_admin_views_operator_task(self, client: TestClient) -> None:
        balaji = _login(client, "Balaji", "medha-balaji-2026")
        task = _create_task(client, balaji, "ADM-OP-TASK")
        self._assert_admin_views(client, balaji, task)

    def test_8_admin_views_junior_engineer_task(self, client: TestClient) -> None:
        keerthi = _login(client, "keerthi", "medha-keerthi-2026")
        task = _create_task(client, keerthi, "ADM-JE-TASK")
        self._assert_admin_views(client, keerthi, task)

    def test_9_admin_views_monitor_task(self, client: TestClient) -> None:
        saniya = _login(client, "saniya", "medha-saniya-2026")
        task = _create_task(client, saniya, "ADM-MO-TASK")
        self._assert_admin_views(client, saniya, task)


# ── 10-11. worker isolation / task_id tampering ─────────────────────────────

class TestWorkerCannotBypass:
    def test_10_worker_cannot_view_another_workers_task(
        self, client: TestClient
    ) -> None:
        balaji = _login(client, "Balaji", "medha-balaji-2026")
        task = _create_task(client, balaji, "PRIVATE-OP")

        keerthi = _login(client, "keerthi", "medha-keerthi-2026")
        assert (
            client.get(f"/api/tasks/{task['task_id']}", headers=_h(keerthi)).status_code
            == 403
        )
        assert (
            client.get(
                f"/api/verifier/audit/{task['task_id']}", headers=_h(keerthi)
            ).status_code
            == 403
        )

        legacy_op = _login(client, "operator", "medha-operator-2026")
        assert (
            client.get(f"/api/tasks/{task['task_id']}", headers=_h(legacy_op)).status_code
            == 403
        )

    def test_11_task_id_tampering_and_supervision_page_denied(
        self, client: TestClient
    ) -> None:
        balaji = _login(client, "Balaji", "medha-balaji-2026")
        task = _create_task(client, balaji, "TAMPER-TARGET")

        legacy_op = _login(client, "operator", "medha-operator-2026")
        # Direct fetch by task_id → denied.
        assert (
            client.get(f"/api/tasks/{task['task_id']}", headers=_h(legacy_op)).status_code
            == 403
        )
        # Status transition by non-owner → denied.
        resp = _transition(client, legacy_op, task["task_id"], "authorized")
        assert resp.status_code == 403
        # Supervision endpoints (the manager/admin page backend) → denied for workers.
        assert (
            client.get("/api/supervision/tasks", headers=_h(legacy_op)).status_code == 403
        )
        assert (
            client.get(
                f"/api/supervision/tasks/{task['task_id']}", headers=_h(legacy_op)
            ).status_code
            == 403
        )
        assert _approve(client, legacy_op, task["task_id"]).status_code == 403

        # Also denied for non-supervisor privileged-ish roles.
        saniya = _login(client, "saniya", "medha-saniya-2026")
        assert client.get("/api/supervision/tasks", headers=_h(saniya)).status_code == 403


# ── 12-13. approval authorization ───────────────────────────────────────────

class TestApprovalAuthorization:
    def test_12_worker_cannot_approve_own_task(self, client: TestClient) -> None:
        balaji = _login(client, "Balaji", "medha-balaji-2026")
        task = _create_task(client, balaji, "SELF-APPROVE", approval="reviewer")
        _submit(client, balaji, task["task_id"])

        # Worker role blocked before any ownership logic.
        assert _approve(client, balaji, task["task_id"]).status_code == 403
        # Status unchanged.
        current = client.get(
            f"/api/tasks/{task['task_id']}", headers=_h(balaji)
        ).json()
        assert current["status"] == "pending_approval"

    def test_13_unauthorized_users_cannot_approve(self, client: TestClient) -> None:
        balaji = _login(client, "Balaji", "medha-balaji-2026")
        task = _create_task(client, balaji, "UNAUTH-APPROVE", approval="reviewer")
        _submit(client, balaji, task["task_id"])

        saniya = _login(client, "saniya", "medha-saniya-2026")
        assert _approve(client, saniya, task["task_id"]).status_code == 403

        nagarjuna = _login(client, "nagarjuna", "medha-nagarjuna-2026")
        assert _approve(client, nagarjuna, task["task_id"]).status_code == 403

        keerthi = _login(client, "keerthi", "medha-keerthi-2026")
        assert _approve(client, keerthi, task["task_id"]).status_code == 403

        # Manager cannot approve a task outside the supervision scope
        # (admin-owned task — admin is not a supervised worker role).
        lokesh = _login(client, "lokesh", "medha-lokesh-2026")
        admin_task = _create_task(client, lokesh, "ADMIN-OWNED", approval="admin")
        _submit(client, lokesh, admin_task["task_id"])
        ali = _login(client, "Ali", "medha-ali-2026")
        assert _approve(client, ali, admin_task["task_id"]).status_code == 403


# ── 14-15. manager/admin approval ───────────────────────────────────────────

class TestSupervisorApproval:
    def test_14_manager_can_approve_supervised_task(
        self, client: TestClient
    ) -> None:
        balaji = _login(client, "Balaji", "medha-balaji-2026")
        task = _create_task(client, balaji, "OP-TASK-001", approval="reviewer")
        _submit(client, balaji, task["task_id"])

        # Worker prepares an execution plan for supervisor review.
        plan_resp = client.post(
            "/api/agent/plan",
            json={
                "task_id": task["task_id"],
                "query": "Read the inspection document",
            },
            headers=_h(balaji),
        )
        assert plan_resp.status_code == 201, plan_resp.text

        ali = _login(client, "Ali", "medha-ali-2026")
        detail = client.get(
            f"/api/supervision/tasks/{task['task_id']}", headers=_h(ali)
        )
        assert detail.status_code == 200
        body = detail.json()
        assert body["task"]["verification_status"] == "waiting_verification"
        assert body["plan"] is not None  # plan visible before approval

        approve = _approve(client, ali, task["task_id"])
        assert approve.status_code == 200, approve.text
        assert approve.json()["status"] == "authorized"
        assert approve.json()["decision"] == "approved"

        # Replay is rejected.
        replay = _approve(client, ali, task["task_id"])
        assert replay.status_code == 409

        # Execution is now permitted.
        exec_resp = client.post(
            "/api/sandbox/execute",
            json={
                "task_id": task["task_id"],
                "tool_name": "document_reader",
                "action": "Read report",
            },
            headers=_h(balaji),
        )
        assert exec_resp.status_code == 200, exec_resp.text

        assert "MANAGER_APPROVE_TASK" in _audit_types(client, balaji, task["task_id"])

    def test_15_admin_can_approve_supervised_task(self, client: TestClient) -> None:
        keerthi = _login(client, "keerthi", "medha-keerthi-2026")
        task = _create_task(client, keerthi, "JE-TASK-001", approval="reviewer")
        _submit(client, keerthi, task["task_id"])

        lokesh = _login(client, "lokesh", "medha-lokesh-2026")
        approve = _approve(client, lokesh, task["task_id"])
        assert approve.status_code == 200, approve.text
        assert approve.json()["status"] == "authorized"
        assert "ADMIN_APPROVE_TASK" in _audit_types(client, keerthi, task["task_id"])

        assert _approve(client, lokesh, task["task_id"]).status_code == 409


# ── 16. rejection requires reason ───────────────────────────────────────────

class TestRejectionRequiresReason:
    def test_16_rejection_requires_reason(self, client: TestClient) -> None:
        balaji = _login(client, "Balaji", "medha-balaji-2026")
        task = _create_task(client, balaji, "REJECT-NO-REASON", approval="reviewer")
        _submit(client, balaji, task["task_id"])
        ali = _login(client, "Ali", "medha-ali-2026")

        # Missing body / empty / whitespace reasons are all rejected.
        assert _reject(client, ali, task["task_id"], None).status_code == 422
        assert _reject(client, ali, task["task_id"], "").status_code == 422
        assert _reject(client, ali, task["task_id"], "   ").status_code in (400, 422)

        # With a reason the task is rejected and stays blocked.
        ok = _reject(client, ali, task["task_id"], "Plan lacks isolation checks")
        assert ok.status_code == 200, ok.text
        assert ok.json()["status"] == "rejected"

        current = client.get(f"/api/tasks/{task['task_id']}", headers=_h(balaji)).json()
        assert current["status"] == "rejected"

        # Worker sees the rejection reason through the audit trail.
        events = _audit(client, balaji, task["task_id"])
        reject_events = [e for e in events if e["event_type"] == "MANAGER_REJECT_TASK"]
        assert reject_events
        assert "Plan lacks isolation checks" in reject_events[-1]["detail"]
        assert "target_user_id=OP00303" in reject_events[-1]["detail"]

        # Rejected task cannot be executed or revived by the worker.
        exec_resp = client.post(
            "/api/sandbox/execute",
            json={
                "task_id": task["task_id"],
                "tool_name": "document_reader",
                "action": "Read report",
            },
            headers=_h(balaji),
        )
        assert exec_resp.status_code == 403
        assert _transition(client, balaji, task["task_id"], "authorized").status_code == 409


# ── 17. unapproved task cannot execute ──────────────────────────────────────

class TestUnapprovedCannotExecute:
    def test_17_unapproved_task_cannot_execute(self, client: TestClient) -> None:
        balaji = _login(client, "Balaji", "medha-balaji-2026")

        # (a) Draft approval-required task cannot skip straight to authorized.
        task_a = _create_task(client, balaji, "NO-SKIP", approval="reviewer")
        resp = _transition(client, balaji, task_a["task_id"], "authorized")
        assert resp.status_code == 403
        assert "human verification" in resp.json()["detail"].lower()

        # (b) Waiting-for-verification task cannot execute or start executing.
        task_b = _create_task(client, balaji, "WAITING-EXEC", approval="reviewer")
        _submit(client, balaji, task_b["task_id"])
        assert _transition(client, balaji, task_b["task_id"], "executing").status_code == 409
        exec_resp = client.post(
            "/api/sandbox/execute",
            json={
                "task_id": task_b["task_id"],
                "tool_name": "document_reader",
                "action": "Read report",
            },
            headers=_h(balaji),
        )
        assert exec_resp.status_code == 403

        # Agent step execution is blocked the same way.
        plan_resp = client.post(
            "/api/agent/plan",
            json={"task_id": task_b["task_id"], "query": "Read the inspection document"},
            headers=_h(balaji),
        )
        assert plan_resp.status_code == 201
        step = plan_resp.json()["steps"][0]
        step_exec = client.post(
            "/api/agent/plan/execute-step",
            json={"plan_id": plan_resp.json()["plan_id"], "step_id": step["step_id"]},
            headers=_h(balaji),
        )
        assert step_exec.status_code == 403

        # (c) Approval is invalidated when the task plan is modified after approval.
        task_c = _create_task(client, balaji, "MODIFIED-PLAN", approval="reviewer")
        _submit(client, balaji, task_c["task_id"])
        ali = _login(client, "Ali", "medha-ali-2026")
        assert _approve(client, ali, task_c["task_id"]).status_code == 200

        mode_resp = client.post(
            "/api/security-mode/set",
            json={"task_id": task_c["task_id"], "security_mode": "secure"},
            headers=_h(balaji),
        )
        assert mode_resp.status_code == 200, mode_resp.text

        exec_after_change = client.post(
            "/api/sandbox/execute",
            json={
                "task_id": task_c["task_id"],
                "tool_name": "document_reader",
                "action": "Read report",
            },
            headers=_h(balaji),
        )
        assert exec_after_change.status_code == 403
        assert "no longer valid" in exec_after_change.json()["detail"].lower()

        # (d) Approval bound to a reviewed plan cannot be reused for a
        # different (modified) execution plan.
        task_d = _create_task(client, balaji, "PLAN-SWAP", approval="reviewer")
        _submit(client, balaji, task_d["task_id"])
        plan_a = client.post(
            "/api/agent/plan",
            json={"task_id": task_d["task_id"], "query": "Read the inspection document"},
            headers=_h(balaji),
        )
        assert plan_a.status_code == 201
        assert _approve(client, ali, task_d["task_id"]).status_code == 200

        plan_b = client.post(
            "/api/agent/plan",
            json={"task_id": task_d["task_id"], "query": "Read the inspection document again"},
            headers=_h(balaji),
        )
        assert plan_b.status_code == 201
        step_b = plan_b.json()["steps"][0]
        swap_exec = client.post(
            "/api/agent/plan/execute-step",
            json={"plan_id": plan_b.json()["plan_id"], "step_id": step_b["step_id"]},
            headers=_h(balaji),
        )
        assert swap_exec.status_code == 403
        assert "does not match" in swap_exec.json()["detail"].lower()

        # The originally approved plan still executes.
        step_a = plan_a.json()["steps"][0]
        approved_exec = client.post(
            "/api/agent/plan/execute-step",
            json={"plan_id": plan_a.json()["plan_id"], "step_id": step_a["step_id"]},
            headers=_h(balaji),
        )
        assert approved_exec.status_code == 200, approved_exec.text


# ── 18-20. completion verification ──────────────────────────────────────────

class TestCompletionVerification:
    def test_18_completed_task_enters_completion_verification(
        self, client: TestClient
    ) -> None:
        balaji = _login(client, "Balaji", "medha-balaji-2026")
        task = _create_task(client, balaji, "COMPLETE-WAIT", approval="reviewer")
        ali = _login(client, "Ali", "medha-ali-2026")
        final = _to_pending_verification(client, balaji, task["task_id"], ali)
        assert final == "pending_verification"

        current = client.get(
            f"/api/tasks/{task['task_id']}", headers=_h(balaji)
        ).json()
        assert current["status"] == "pending_verification"

        # Worker cannot self-verify completion.
        assert _verify_completion(client, balaji, task["task_id"]).status_code == 403
        # Worker cannot re-execute a completed task.
        assert _transition(client, balaji, task["task_id"], "executing").status_code == 409

    def test_19_manager_can_verify_completion(self, client: TestClient) -> None:
        balaji = _login(client, "Balaji", "medha-balaji-2026")
        task = _create_task(client, balaji, "MGR-VERIFY", approval="reviewer")
        ali = _login(client, "Ali", "medha-ali-2026")
        assert (
            _to_pending_verification(client, balaji, task["task_id"], ali)
            == "pending_verification"
        )

        resp = _verify_completion(client, ali, task["task_id"])
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "verified"
        assert resp.json()["decision"] == "verified"

        # Replay rejected.
        assert _verify_completion(client, ali, task["task_id"]).status_code == 409
        assert "MANAGER_VERIFY_COMPLETION" in _audit_types(
            client, balaji, task["task_id"]
        )

    def test_20_admin_can_verify_completion(self, client: TestClient) -> None:
        keerthi = _login(client, "keerthi", "medha-keerthi-2026")
        task = _create_task(client, keerthi, "ADM-VERIFY", approval="reviewer")
        lokesh = _login(client, "lokesh", "medha-lokesh-2026")
        assert (
            _to_pending_verification(client, keerthi, task["task_id"], lokesh)
            == "pending_verification"
        )

        resp = _verify_completion(client, lokesh, task["task_id"])
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "verified"
        assert "ADMIN_VERIFY_COMPLETION" in _audit_types(
            client, keerthi, task["task_id"]
        )


# ── 21. completion rejection requires reason ────────────────────────────────

class TestCompletionRejection:
    def test_21_completion_rejection_requires_reason(
        self, client: TestClient
    ) -> None:
        balaji = _login(client, "Balaji", "medha-balaji-2026")
        task = _create_task(client, balaji, "COMPLETION-REJECT", approval="reviewer")
        ali = _login(client, "Ali", "medha-ali-2026")
        assert (
            _to_pending_verification(client, balaji, task["task_id"], ali)
            == "pending_verification"
        )

        assert _reject_completion(client, ali, task["task_id"], None).status_code == 422
        assert _reject_completion(client, ali, task["task_id"], "").status_code == 422

        ok = _reject_completion(
            client, ali, task["task_id"], "Output fails safety checks"
        )
        assert ok.status_code == 200, ok.text
        assert ok.json()["status"] == "rejected"

        current = client.get(
            f"/api/tasks/{task['task_id']}", headers=_h(balaji)
        ).json()
        assert current["status"] == "rejected"

        events = _audit(client, balaji, task["task_id"])
        rejects = [
            e for e in events if e["event_type"] == "MANAGER_REJECT_COMPLETION"
        ]
        assert rejects
        assert "Output fails safety checks" in rejects[-1]["detail"]


# ── 22. every supervisory action is audited ─────────────────────────────────

class TestSupervisoryActionsAudited:
    def test_22_every_supervisory_action_is_audited(
        self, client: TestClient
    ) -> None:
        balaji = _login(client, "Balaji", "medha-balaji-2026")
        keerthi = _login(client, "keerthi", "medha-keerthi-2026")
        ali = _login(client, "Ali", "medha-ali-2026")
        lokesh = _login(client, "lokesh", "medha-lokesh-2026")

        all_types: set[str] = set()

        # --- Manager journey: view → approve → execute → verify ---
        m_task = _create_task(client, balaji, "AUDIT-M-APPROVE", approval="reviewer")
        _submit(client, balaji, m_task["task_id"])
        client.get(f"/api/tasks/{m_task['task_id']}", headers=_h(ali))
        client.get(f"/api/supervision/tasks/{m_task['task_id']}", headers=_h(ali))
        client.get(f"/api/verifier/audit/{m_task['task_id']}", headers=_h(ali))
        assert _approve(client, ali, m_task["task_id"]).status_code == 200
        _transition(client, balaji, m_task["task_id"], "executing")
        _transition(client, balaji, m_task["task_id"], "completed")
        assert _verify_completion(client, ali, m_task["task_id"]).status_code == 200
        all_types |= _audit_types(client, balaji, m_task["task_id"])

        # --- Manager reject (before-task) ---
        m_rej = _create_task(client, balaji, "AUDIT-M-REJECT", approval="reviewer")
        _submit(client, balaji, m_rej["task_id"])
        assert _reject(client, ali, m_rej["task_id"], "unsafe").status_code == 200
        all_types |= _audit_types(client, balaji, m_rej["task_id"])

        # --- Manager reject completion ---
        m_rc = _create_task(client, balaji, "AUDIT-M-REJ-COMP", approval="reviewer")
        assert (
            _to_pending_verification(client, balaji, m_rc["task_id"], ali)
            == "pending_verification"
        )
        assert (
            _reject_completion(client, ali, m_rc["task_id"], "rework needed").status_code
            == 200
        )
        all_types |= _audit_types(client, balaji, m_rc["task_id"])

        # --- Admin journey: view → approve → execute → verify ---
        a_task = _create_task(client, keerthi, "AUDIT-A-APPROVE", approval="reviewer")
        _submit(client, keerthi, a_task["task_id"])
        client.get(f"/api/tasks/{a_task['task_id']}", headers=_h(lokesh))
        client.get(f"/api/supervision/tasks/{a_task['task_id']}", headers=_h(lokesh))
        client.get(f"/api/verifier/audit/{a_task['task_id']}", headers=_h(lokesh))
        assert _approve(client, lokesh, a_task["task_id"]).status_code == 200
        _transition(client, keerthi, a_task["task_id"], "executing")
        _transition(client, keerthi, a_task["task_id"], "completed")
        assert _verify_completion(client, lokesh, a_task["task_id"]).status_code == 200
        all_types |= _audit_types(client, keerthi, a_task["task_id"])

        # --- Admin reject (before-task) ---
        a_rej = _create_task(client, keerthi, "AUDIT-A-REJECT", approval="reviewer")
        _submit(client, keerthi, a_rej["task_id"])
        assert _reject(client, lokesh, a_rej["task_id"], "not acceptable").status_code == 200
        all_types |= _audit_types(client, keerthi, a_rej["task_id"])

        # --- Admin reject completion ---
        a_rc = _create_task(client, keerthi, "AUDIT-A-REJ-COMP", approval="reviewer")
        assert (
            _to_pending_verification(client, keerthi, a_rc["task_id"], lokesh)
            == "pending_verification"
        )
        assert (
            _reject_completion(
                client, lokesh, a_rc["task_id"], "needs review"
            ).status_code
            == 200
        )
        all_types |= _audit_types(client, keerthi, a_rc["task_id"])

        required = {
            "MANAGER_VIEW_TASK",
            "MANAGER_VIEW_TRACE",
            "MANAGER_APPROVE_TASK",
            "MANAGER_REJECT_TASK",
            "MANAGER_VERIFY_COMPLETION",
            "MANAGER_REJECT_COMPLETION",
            "ADMIN_VIEW_TASK",
            "ADMIN_VIEW_TRACE",
            "ADMIN_APPROVE_TASK",
            "ADMIN_REJECT_TASK",
            "ADMIN_VERIFY_COMPLETION",
            "ADMIN_REJECT_COMPLETION",
        }
        missing = required - all_types
        assert not missing, f"Missing audit events: {missing}"

        # Audit detail carries actor/target/action/reason fields.
        reject_events = [
            e
            for e in _audit(client, balaji, m_rej["task_id"])
            if e["event_type"] == "MANAGER_REJECT_TASK"
        ]
        assert reject_events
        detail = reject_events[-1]["detail"]
        assert "actor_user_id=MD00574" in detail
        assert "actor_role=manager" in detail
        assert "target_user_id=OP00303" in detail
        assert "task_id=" in detail
        assert "reason=unsafe" in detail


# ── 24. existing authentication still works ─────────────────────────────────

class TestExistingAuthStillWorks:
    def test_24_legacy_demo_logins_still_work(self, client: TestClient) -> None:
        token = _login(client, "operator", "medha-operator-2026")
        me = _me(client, token)
        assert me["user_id"] == "USR-00000001"
        assert me["role"] == "operator"

        token = _login(client, "admin", "medha-admin-2026")
        me = _me(client, token)
        assert me["user_id"] == "USR-00000004"
        assert me["role"] == "admin"

        token = _login(client, "engineer", "medha-engineer-2026")
        assert _me(client, token)["user_id"] == "USR-00000002"


# ── 25. existing tasks/data remain intact ───────────────────────────────────

class TestDataIntact:
    def test_25_seeding_preserves_existing_tasks_and_users(
        self, client: TestClient
    ) -> None:
        balaji = _login(client, "Balaji", "medha-balaji-2026")
        task = _create_task(client, balaji, "PRECIOUS-DATA")

        db = SessionLocal()
        try:
            from app.models.user import UserRow

            before_count = db.query(UserRow).count()
            # Idempotent re-seed (as on every server start).
            user_service.seed_demo_users(db)
            after_count = db.query(UserRow).count()
            assert before_count == after_count
        finally:
            db.close()

        # Existing task and its audit trail remain intact.
        tasks = client.get("/api/tasks", headers=_h(balaji)).json()
        assert any(t["task_id"] == task["task_id"] for t in tasks)
        events = _audit(client, balaji, task["task_id"])
        assert any(e["event_type"] == "passport_created" for e in events)

        # All six org users still log in after re-seed.
        for username, password, uid, role in SIX_USERS:
            token = _login(client, username, password)
            me = _me(client, token)
            assert me["user_id"] == uid
            assert me["role"] == role
