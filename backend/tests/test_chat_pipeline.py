"""Focused behavioral tests — task-aware intent → RAG → privacy gateway.

Covers the required behaviors:
  task context, intent classification, task-aware resource plan, chat→RAG,
  information-need query, RAG authorization, fail-closed empty allowlist,
  RAG-miss missing-information state, external research not automatic,
  sovereign deny, allow only when policy permits, sanitized external query
  (no task_id / user_id / company / equipment IDs / measurements / private
  file content), sanitized query == what provider receives, public results
  return to MEDHA, internal + public evidence combined, external research
  audits (allowed + denied), cross-task isolation.
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.schemas.task import (
    ApprovalRequirement,
    NetworkPolicy,
    SecurityMode,
    TaskPassportRead,
    TaskSensitivity,
    TaskStatus,
)
from app.services.ai_pipeline.intent import classify_intent
from app.services.audit_service import audit_service
from app.services.model_router.model_adapter import ModelAdapterFactory, ModelResponse
from app.services.privacy_gateway import (
    DeterministicTestSearchProvider,
    UnavailablePublicSearchProvider,
    decide_external_research,
    privacy_gateway,
    sanitize_research_query,
)
from app.services.rag.retrieval import retrieval_service
from app.services.rag.vector_store import vector_store


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def captured_model_inputs(monkeypatch):
    """Spy on the model adapter factory to capture structured model input."""
    captured: list[str] = []

    class _SpyAdapter:
        name = "local-qwen2"

        def generate(self, prompt: str, max_tokens: int = 512) -> ModelResponse:
            captured.append(prompt)
            return ModelResponse(
                model_name=self.name,
                text="ok",
                tokens_used=1,
                latency_ms=1.0,
            )

    monkeypatch.setattr(
        ModelAdapterFactory,
        "get",
        classmethod(lambda cls, name: _SpyAdapter()),
    )
    return captured


@pytest.fixture
def research_provider():
    """Inject the deterministic test provider; restore unavailable after."""
    provider = DeterministicTestSearchProvider()
    privacy_gateway.set_provider(provider)
    yield provider
    privacy_gateway.set_provider(UnavailablePublicSearchProvider())


# ── Helpers ──────────────────────────────────────────────────────────────


def _login(client: TestClient, username: str, password: str) -> dict:
    resp = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_task(client: TestClient, headers: dict, title: str, **kwargs) -> dict:
    payload = {"title": title, "purpose": f"Purpose for {title}", **kwargs}
    resp = client.post("/api/tasks", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _authorize_and_execute(client: TestClient, headers: dict, task_id: str) -> None:
    for status_name in ("authorized", "executing"):
        resp = client.patch(
            f"/api/tasks/{task_id}/status",
            json={"new_status": status_name, "detail": f"transition {status_name}"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text


def _send(
    client: TestClient,
    headers: dict,
    task_id: str,
    prompt: str,
    conversation_id: str | None = None,
):
    body = {"task_id": task_id, "prompt": prompt}
    if conversation_id:
        body["conversation_id"] = conversation_id
    return client.post("/api/chat/send", json=body, headers=headers)


def _events(task_id: str) -> list:
    return audit_service.get_events_for_task(task_id)


def _has_event(task_id: str, event_type: str) -> bool:
    return any(e.event_type == event_type for e in _events(task_id))


def _event_detail(task_id: str, event_type: str) -> str:
    for e in _events(task_id):
        if e.event_type == event_type:
            return e.detail
    raise AssertionError(f"event {event_type} not found for task {task_id}")


def _make_passport(**overrides) -> TaskPassportRead:
    now = datetime.now(timezone.utc)
    base = dict(
        task_id="11111111-2222-3333-4444-555555555555",
        user_id="USR-00000004",
        identity="operator",
        role="operator",
        title="Pump vibration investigation",
        purpose="Investigate our refinery Pump P-204 bearing degradation at MRPL plant",
        sensitivity=TaskSensitivity.INTERNAL,
        security_mode=SecurityMode.STANDARD,
        security_policy_version="1.0",
        requested_operation="analyze",
        allowed_sources=["handbook.txt"],
        allowed_tools=["document_reader"],
        allowed_models=[],
        approval_requirement=ApprovalRequirement.NONE,
        network_policy=NetworkPolicy.DENY_EXTERNAL,
        status=TaskStatus.EXECUTING,
        created_at=now,
        updated_at=now,
    )
    base.update(overrides)
    return TaskPassportRead(**base)


# ── Unit: sanitization + policy (requirements 10, 12–16) ────────────────


class TestSanitization:
    def test_external_query_excludes_private_tokens(self):
        passport = _make_passport()
        intent = classify_intent(
            "Our P-204 vibration is 8.4 mm/s and 92\u00b0C bearing temp — "
            "compare with recent industry cases for user USR-00000004 task "
            f"{passport.task_id}",
            passport,
            [],
        )
        result = sanitize_research_query(intent, passport)
        assert result.safe, result.reason
        q = result.query
        assert passport.task_id not in q
        assert passport.user_id not in q
        assert "P-204" not in q
        assert "8.4" not in q
        assert "mm/s" not in q
        assert "92" not in q
        assert "MRPL" not in q
        assert "P-204" not in passport.purpose or "P-204" not in q

    def test_company_and_equipment_removed(self):
        passport = _make_passport()
        intent = classify_intent(
            "Why is our MRPL Pump P-204 failing?", passport, []
        )
        result = sanitize_research_query(intent, passport)
        assert result.safe, result.reason
        assert "MRPL" not in result.query
        assert "P-204" not in result.query
        assert "our" not in result.query.lower().split()

    def test_unsafe_query_blocks_when_nothing_safe_remains(self):
        passport = _make_passport(purpose="P-204")
        intent = classify_intent("8.4", passport, [])
        result = sanitize_research_query(intent, passport)
        assert result.safe is False
        assert "could not be generated" in result.reason

    def test_private_file_content_never_an_input(self):
        """Sanitizer inputs are information_need + purpose only — chunk/file
        content is never passed in, so file content cannot leak."""
        passport = _make_passport()
        intent = classify_intent("General bearing failure studies", passport, [])
        result = sanitize_research_query(intent, passport)
        assert result.safe
        assert "confidential file content" not in result.query


class TestExternalPolicy:
    def test_sovereign_allow_internal_permits_policy_controlled_research(self):
        passport = _make_passport(
            security_mode=SecurityMode.SOVEREIGN,
            sensitivity=TaskSensitivity.RESTRICTED,
            network_policy=NetworkPolicy.ALLOW_INTERNAL,
        )
        allowed, reason = decide_external_research(passport)
        assert allowed is True
        assert "sovereign" in reason.lower()
        assert "sanitized" in reason.lower()

    def test_sovereign_deny_external_blocks(self):
        passport = _make_passport(
            security_mode=SecurityMode.SOVEREIGN,
            sensitivity=TaskSensitivity.RESTRICTED,
            network_policy=NetworkPolicy.DENY_EXTERNAL,
        )
        allowed, reason = decide_external_research(passport)
        assert allowed is False
        assert "deny_external" in reason

    def test_deny_external_network_policy_blocks(self):
        passport = _make_passport(network_policy=NetworkPolicy.DENY_EXTERNAL)
        allowed, reason = decide_external_research(passport)
        assert allowed is False
        assert "deny_external" in reason

    def test_standard_allow_internal_permits(self):
        passport = _make_passport(network_policy=NetworkPolicy.ALLOW_INTERNAL)
        allowed, _reason = decide_external_research(passport)
        assert allowed is True


# ── Integration through /chat/send ───────────────────────────────────────


class TestChatPipeline:
    # 1 — task context reaches the model adapter
    def test_chat_loads_task_context(self, client, captured_model_inputs):
        headers = _login(client, "operator", "medha-operator-2026")
        task = _create_task(client, headers, "P-204 Pump Failure Investigation")
        _authorize_and_execute(client, headers, task["task_id"])
        resp = _send(client, headers, task["task_id"], "What is causing this vibration?")
        assert resp.status_code == 200, resp.text
        model_input = captured_model_inputs[-1]
        assert "TASK CONTEXT:" in model_input
        assert f"task_id: {task['task_id']}" in model_input
        assert "title: P-204 Pump Failure Investigation" in model_input

    # 2 — intent is classified for the active task
    def test_intent_classified(self, client, captured_model_inputs):
        headers = _login(client, "operator", "medha-operator-2026")
        task = _create_task(client, headers, "Intent Task")
        _authorize_and_execute(client, headers, task["task_id"])
        resp = _send(
            client, headers, task["task_id"],
            "What is causing this abnormal vibration?",
        )
        assert resp.status_code == 200, resp.text
        assert _has_event(task["task_id"], "CHAT_INTENT_CLASSIFIED")
        detail = _event_detail(task["task_id"], "CHAT_INTENT_CLASSIFIED")
        assert "category=investigation" in detail
        assert "evidence_required=True" in detail
        model_input = captured_model_inputs[-1]
        assert "INTENT:" in model_input
        assert "answer_type: technical_analysis" in model_input

    # 3 — resource plan is task-aware
    def test_resource_plan_task_aware(self, client, captured_model_inputs):
        headers = _login(client, "operator", "medha-operator-2026")
        task = _create_task(
            client, headers, "Planned Task",
            allowed_sources=["plan_source.txt"],
            allowed_tools=["document_reader"],
        )
        _authorize_and_execute(client, headers, task["task_id"])
        resp = _send(client, headers, task["task_id"], "What failed here?")
        assert resp.status_code == 200, resp.text
        assert _has_event(task["task_id"], "CHAT_RESOURCE_PLAN_CREATED")
        model_input = captured_model_inputs[-1]
        assert "RESOURCE PLAN:" in model_input
        assert "plan_source.txt" in model_input
        assert "document_reader" in model_input

    # 4 + 5 — chat invokes RAG; query uses the user's information need
    def test_chat_invokes_rag_with_information_need(
        self, client, captured_model_inputs
    ):
        headers = _login(client, "operator", "medha-operator-2026")
        task = _create_task(
            client, headers, "RAG Task", allowed_sources=["rag_handbook.txt"]
        )
        _authorize_and_execute(client, headers, task["task_id"])
        resp = _send(
            client, headers, task["task_id"],
            "What indicates hydrolock in this equipment?",
        )
        assert resp.status_code == 200, resp.text
        assert _has_event(task["task_id"], "CHAT_RAG_SEARCH")
        # retrieval audit contains the actual query built from information need
        rag_events = [
            e for e in _events(task["task_id"]) if e.event_type == "rag_search"
        ]
        assert rag_events, "retrieval_service must audit rag_search"
        assert any("hydrolock" in e.detail for e in rag_events)

    # 6 — RAG respects task/user authorization (unauthorized source excluded)
    def test_rag_respects_authorization(self, client, captured_model_inputs):
        headers = _login(client, "operator", "medha-operator-2026")
        vector_store.reset()
        retrieval_service.ingest_document(
            "Authorized pump handbook content about bearing vibration diagnosis.",
            "allowed_handbook.txt",
            "internal",
        )
        retrieval_service.ingest_document(
            "SECRET_OTHER_TASK_CONTENT Payroll salaries confidential annex.",
            "secret_other_task.txt",
            "internal",
        )
        task = _create_task(
            client, headers, "Auth RAG Task",
            allowed_sources=["allowed_handbook.txt"],
        )
        _authorize_and_execute(client, headers, task["task_id"])
        resp = _send(
            client, headers, task["task_id"],
            "What does the handbook say about bearing vibration diagnosis?",
        )
        assert resp.status_code == 200, resp.text
        model_input = captured_model_inputs[-1]
        assert "allowed_handbook.txt" in model_input
        assert "SECRET_OTHER_TASK_CONTENT" not in model_input
        assert "secret_other_task.txt" not in model_input

    # 7 — empty allowed_sources fails closed
    def test_empty_allowlist_fails_closed(self, client, captured_model_inputs):
        headers = _login(client, "operator", "medha-operator-2026")
        vector_store.reset()
        retrieval_service.ingest_document(
            "Something indexed globally that must not leak.",
            "global_doc.txt",
            "internal",
        )
        task = _create_task(client, headers, "No Sources Task")  # default []
        assert task["allowed_sources"] == []
        _authorize_and_execute(client, headers, task["task_id"])
        resp = _send(
            client, headers, task["task_id"],
            "What caused this equipment failure?",
        )
        assert resp.status_code == 200, resp.text
        model_input = captured_model_inputs[-1]
        assert "fail-closed" in model_input
        assert "Something indexed globally" not in model_input
        # RAG was not attempted (no authorized sources)
        assert not _has_event(task["task_id"], "CHAT_RAG_SEARCH")
        assert _has_event(task["task_id"], "CHAT_RAG_NO_RESULT")
        detail = _event_detail(task["task_id"], "CHAT_RAG_NO_RESULT")
        assert "fails closed" in detail

    # 8 — RAG miss produces missing-information state (no fabrication)
    def test_rag_miss_missing_information(self, client, captured_model_inputs):
        headers = _login(client, "operator", "medha-operator-2026")
        task = _create_task(
            client, headers, "Miss Task", allowed_sources=["never_ingested_xyz.txt"]
        )
        _authorize_and_execute(client, headers, task["task_id"])
        resp = _send(
            client, headers, task["task_id"],
            "What caused the hydrolock failure?",
        )
        assert resp.status_code == 200, resp.text
        model_input = captured_model_inputs[-1]
        assert "MISSING INFORMATION:" in model_input
        assert "do not fabricate" in model_input
        assert _has_event(task["task_id"], "CHAT_RAG_NO_RESULT")
        # missing section appears AFTER internal evidence section
        assert model_input.index("INTERNAL EVIDENCE") < model_input.index(
            "MISSING INFORMATION"
        )

    # 9 — external research is not automatically triggered (default deny)
    def test_external_not_automatic(
        self, client, captured_model_inputs, research_provider
    ):
        headers = _login(client, "operator", "medha-operator-2026")
        task = _create_task(
            client, headers, "Deny Task",
            allowed_sources=["miss_src_denied.txt"],  # never ingested
            network_policy="deny_external",
        )
        _authorize_and_execute(client, headers, task["task_id"])
        resp = _send(
            client, headers, task["task_id"],
            "What caused this hydrolock event?",
        )
        assert resp.status_code == 200, resp.text
        assert research_provider.received_queries == []
        assert _has_event(task["task_id"], "EXTERNAL_RESEARCH_DENIED")
        assert not _has_event(task["task_id"], "EXTERNAL_RESEARCH_COMPLETED")
        model_input = captured_model_inputs[-1]
        assert "(blocked:" in model_input.split("PUBLIC RESEARCH")[1]

    # 10a — sovereign + allow_internal: controlled sanitized external research runs
    def test_sovereign_allow_internal_runs_sanitized_research(
        self, client, captured_model_inputs, research_provider
    ):
        headers = _login(client, "operator", "medha-operator-2026")
        task = _create_task(
            client, headers, "Sovereign Task",
            sensitivity="restricted",
            allowed_sources=["miss_src_sov.txt"],
            network_policy="allow_internal",  # policy permits sanitized research
        )
        assert task["security_mode"] == "sovereign"
        _authorize_and_execute(client, headers, task["task_id"])
        resp = _send(
            client, headers, task["task_id"],
            "What caused this hydrolock failure mode?",
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # Not the scope message; not the insufficient refusal — research ran.
        assert body["response_text"] != (
            "I can only answer questions relevant to the current task."
        )
        assert body["response_text"] != (
            "I don't have enough verified information to answer that."
        )
        assert len(research_provider.received_queries) == 1
        assert _has_event(task["task_id"], "EXTERNAL_RESEARCH_ALLOWED")
        assert _has_event(task["task_id"], "EXTERNAL_QUERY_SANITIZED")
        assert _has_event(task["task_id"], "EXTERNAL_RESEARCH_COMPLETED")
        # Sanitized query contains no confidential task information
        sent = research_provider.received_queries[0]
        assert task["task_id"] not in sent
        assert "USR-" not in sent
        assert "MRPL" not in sent
        # Combined evidence reaches the local model
        assert len(captured_model_inputs) == 1
        model_input = captured_model_inputs[-1]
        assert "PUBLIC RESEARCH" in model_input
        assert "INTERNAL EVIDENCE" in model_input
        assert _has_event(task["task_id"], "final_decision")
        final = _event_detail(task["task_id"], "final_decision")
        assert "decision=answered_via_model" in final

    # 10b — sovereign + deny_external: controlled research blocked → insufficient
    def test_sovereign_deny_external_returns_insufficient(
        self, client, captured_model_inputs, research_provider
    ):
        headers = _login(client, "operator", "medha-operator-2026")
        task = _create_task(
            client, headers, "Sovereign Blocked Task",
            sensitivity="restricted",
            allowed_sources=["miss_src_sov.txt"],
            network_policy="deny_external",
        )
        assert task["security_mode"] == "sovereign"
        _authorize_and_execute(client, headers, task["task_id"])
        resp = _send(
            client, headers, task["task_id"],
            "What caused this hydrolock failure mode?",
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["response_text"] == (
            "I don't have enough verified information to answer that."
        )
        assert body["execution_mode"] == "policy"
        assert body["model_used"] == "evidence-verification-gate"
        assert captured_model_inputs == []
        assert research_provider.received_queries == []
        assert _has_event(task["task_id"], "EXTERNAL_RESEARCH_DENIED")
        detail = _event_detail(task["task_id"], "EXTERNAL_RESEARCH_DENIED")
        assert "deny_external" in detail
        assert _has_event(task["task_id"], "final_decision")
        final = _event_detail(task["task_id"], "final_decision")
        assert "decision=insufficient_verified_evidence" in final
        assert _has_event(task["task_id"], "task_relevance_checked")

    # 11 — external research allowed only when policy permits
    def test_external_allowed_when_policy_permits(
        self, client, captured_model_inputs, research_provider
    ):
        headers = _login(client, "operator", "medha-operator-2026")
        task = _create_task(
            client, headers, "Allow Task",
            allowed_sources=["miss_src_allowed.txt"],
            network_policy="allow_internal",
        )
        assert task["security_mode"] == "standard"
        _authorize_and_execute(client, headers, task["task_id"])
        resp = _send(
            client, headers, task["task_id"],
            "What caused this hydrolock condition?",
        )
        assert resp.status_code == 200, resp.text
        assert len(research_provider.received_queries) == 1
        assert _has_event(task["task_id"], "EXTERNAL_RESEARCH_ALLOWED")
        assert _has_event(task["task_id"], "EXTERNAL_RESEARCH_COMPLETED")

    # 12–14 + 17 — sanitized query is what reaches the provider
    def test_sanitized_query_reaches_provider(
        self, client, captured_model_inputs, research_provider
    ):
        headers = _login(client, "operator", "medha-operator-2026")
        task = _create_task(
            client, headers, "P-204 Sanitize Task",
            purpose=(
                "Investigate our MRPL refinery Pump P-204 bearing failure; "
                "vibration 8.4 mm/s, bearing temperature 92\u00b0C"
            ),
            allowed_sources=["miss_src_sanitize.txt"],
            network_policy="allow_internal",
        )
        _authorize_and_execute(client, headers, task["task_id"])
        resp = _send(
            client, headers, task["task_id"],
            "Compare our failure with recent industry cases; our P-204 shows "
            "8.4 mm/s vibration",
        )
        assert resp.status_code == 200, resp.text

        assert len(research_provider.received_queries) == 1
        sent = research_provider.received_queries[0]

        # 12: task_id absent
        assert task["task_id"] not in sent
        # 13: user_id absent
        operator_user_id = resp.json()  # ensure 200 shape
        assert "USR-" not in sent
        # 14: company + internal equipment identifiers absent
        assert "MRPL" not in sent
        assert "P-204" not in sent
        # 15: private measurements absent
        assert "8.4" not in sent
        assert "92" not in sent
        assert "mm/s" not in sent
        # 17: sanitized query equals what the EXTERNAL_QUERY_SANITIZED audit logged
        assert _has_event(task["task_id"], "EXTERNAL_QUERY_SANITIZED")
        detail = _event_detail(task["task_id"], "EXTERNAL_QUERY_SANITIZED")
        logged = detail.split("query='", 1)[1].split("'", 1)[0]
        assert sent == logged
        assert operator_user_id["conversation_id"]

    # 16 — private file content absent from external query
    def test_private_file_content_absent(
        self, client, captured_model_inputs, research_provider
    ):
        headers = _login(client, "operator", "medha-operator-2026")
        vector_store.reset()
        retrieval_service.ingest_document(
            "CONFIDENTIAL FILE CONTENT maintenance history internal only.",
            "confidential_history.txt",
            "confidential",
        )
        task = _create_task(
            client, headers, "File Leak Task",
            allowed_sources=["confidential_history.txt"],
            network_policy="allow_internal",
        )
        _authorize_and_execute(client, headers, task["task_id"])
        # Prompt words don't overlap the doc → partial/miss path may run
        resp = _send(
            client, headers, task["task_id"],
            "Explain general hydrolock diagnosis approaches in industry literature?",
        )
        assert resp.status_code == 200, resp.text
        for q in research_provider.received_queries:
            assert "CONFIDENTIAL FILE CONTENT" not in q
            assert "confidential_history" not in q

    # 18 + 19 — public results return; final input combines internal + public
    def test_internal_and_public_evidence_combined(
        self, client, captured_model_inputs, research_provider
    ):
        headers = _login(client, "operator", "medha-operator-2026")
        vector_store.reset()
        retrieval_service.ingest_document(
            "Friday cafeteria menu features pasta, salad, and soup specials.",
            "team_lunch_notes.txt",
            "internal",
        )
        task = _create_task(
            client, headers, "Combined Evidence Task",
            allowed_sources=["team_lunch_notes.txt"],
            network_policy="allow_internal",
        )
        _authorize_and_execute(client, headers, task["task_id"])
        resp = _send(
            client, headers, task["task_id"],
            "Explain bearing vibration spectrum hydrolock indicators used in industry?",
        )
        assert resp.status_code == 200, resp.text

        model_input = captured_model_inputs[-1]
        assert "INTERNAL EVIDENCE (authorized local RAG):" in model_input
        assert "team_lunch_notes.txt" in model_input
        assert "PUBLIC RESEARCH" in model_input
        assert (
            "bearing failure vibration indicators"
            in model_input
        )
        assert model_input.index("INTERNAL EVIDENCE") < model_input.index(
            "PUBLIC RESEARCH"
        )
        assert "PROVENANCE:" in model_input

    # 20 — external research audited (allowed + sanitized + completed)
    def test_external_research_audited_allowed(
        self, client, captured_model_inputs, research_provider
    ):
        headers = _login(client, "operator", "medha-operator-2026")
        task = _create_task(
            client, headers, "Audit Allow Task",
            allowed_sources=["miss_src_audit_ok.txt"],
            network_policy="allow_internal",
        )
        _authorize_and_execute(client, headers, task["task_id"])
        resp = _send(
            client, headers, task["task_id"],
            "What hydrolock failure modes exist in industry?",
        )
        assert resp.status_code == 200, resp.text
        for evt in (
            "EXTERNAL_RESEARCH_REQUESTED",
            "EXTERNAL_RESEARCH_ALLOWED",
            "EXTERNAL_QUERY_SANITIZED",
            "EXTERNAL_RESEARCH_COMPLETED",
            "CHAT_INTENT_CLASSIFIED",
            "CHAT_RESOURCE_PLAN_CREATED",
            "CHAT_RESPONSE_GENERATED",
        ):
            assert _has_event(task["task_id"], evt), f"missing audit {evt}"

    # 21 — denied external research audited
    def test_external_research_denied_audited(
        self, client, captured_model_inputs, research_provider
    ):
        headers = _login(client, "operator", "medha-operator-2026")
        task = _create_task(
            client, headers, "Audit Deny Task",
            allowed_sources=["miss_src_audit_deny.txt"],
            network_policy="deny_external",
        )
        _authorize_and_execute(client, headers, task["task_id"])
        resp = _send(
            client, headers, task["task_id"],
            "What caused this hydrolock anomaly?",
        )
        assert resp.status_code == 200, resp.text
        assert _has_event(task["task_id"], "EXTERNAL_RESEARCH_REQUESTED")
        assert _has_event(task["task_id"], "EXTERNAL_RESEARCH_DENIED")
        assert not _has_event(task["task_id"], "EXTERNAL_RESEARCH_COMPLETED")
        assert not _has_event(task["task_id"], "EXTERNAL_RESEARCH_ALLOWED")

    # 22 — cross-task data cannot enter the context
    def test_cross_task_isolation(self, client, captured_model_inputs):
        headers = _login(client, "operator", "medha-operator-2026")
        task_a = _create_task(client, headers, "Cross Task Alpha Unique")
        task_b = _create_task(client, headers, "Cross Task Beta Unique")
        _authorize_and_execute(client, headers, task_a["task_id"])
        _authorize_and_execute(client, headers, task_b["task_id"])
        resp = _send(client, headers, task_b["task_id"], "Status of beta work?")
        assert resp.status_code == 200, resp.text
        model_input = captured_model_inputs[-1]
        assert "Cross Task Alpha Unique" not in model_input
        assert task_a["task_id"] not in model_input
        assert "Cross Task Beta Unique" in model_input
        # also: full pipeline sections present for task B only
        assert f"task_id: {task_b['task_id']}" in model_input

    # extra — external research NOT triggered when internal evidence covers need
    def test_no_external_when_evidence_sufficient(
        self, client, captured_model_inputs, research_provider
    ):
        headers = _login(client, "operator", "medha-operator-2026")
        vector_store.reset()
        retrieval_service.ingest_document(
            "hydrolock failure causes include overheating and improper fuel "
            "ignition timing diagnostics procedures.",
            "hydrolock_manual.txt",
            "internal",
        )
        task = _create_task(
            client, headers, "Enough Evidence Task",
            allowed_sources=["hydrolock_manual.txt"],
            network_policy="allow_internal",
        )
        _authorize_and_execute(client, headers, task["task_id"])
        resp = _send(
            client, headers, task["task_id"],
            "What causes hydrolock failure?",
        )
        assert resp.status_code == 200, resp.text
        assert research_provider.received_queries == []
        assert not _has_event(task["task_id"], "EXTERNAL_RESEARCH_REQUESTED")
        model_input = captured_model_inputs[-1]
        assert "not needed (internal evidence sufficient)" in model_input
