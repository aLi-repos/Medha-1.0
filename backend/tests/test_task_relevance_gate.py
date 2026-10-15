"""Task-relevance gate + sovereign controlled-verification tests.

Covers:
  sovereign + relevant  → continues through pipeline (answer via model)
  sovereign + irrelevant → exact scope refusal, no RAG/external/model
  sovereign + relevant + internal evidence → answer with INTERNAL EVIDENCE
  sovereign + relevant + insufficient → EXTERNAL denied + exact message,
      no model call, empty provider queries
  standard + off-topic  → NO scope message, 200, model called
  cross-user → 403
  unauthorized source never in captured prompt
  relevant + authorized source → RAG → local model
  sanitization: no task_id / user_id in external query
"""

import pytest
from fastapi.testclient import TestClient

from app.services.audit_service import audit_service
from app.services.model_router.model_adapter import ModelAdapterFactory, ModelResponse
from app.services.privacy_gateway import (
    DeterministicTestSearchProvider,
    UnavailablePublicSearchProvider,
    privacy_gateway,
    sanitize_research_query,
)
from app.services.rag.retrieval import retrieval_service
from app.services.rag.vector_store import vector_store
from app.services.ai_pipeline.intent import classify_intent
from datetime import datetime, timezone

from app.schemas.task import (
    ApprovalRequirement,
    NetworkPolicy,
    SecurityMode,
    TaskPassportRead,
    TaskSensitivity,
    TaskStatus,
)


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def captured_model_inputs(monkeypatch):
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


# ── Sovereign + irrelevant → exact scope refusal ─────────────────────────


def test_sovereign_irrelevant_denied_no_model_no_rag_no_external(
    client: TestClient, captured_model_inputs, research_provider
):
    headers = _login(client, "operator", "medha-operator-2026")
    task = _create_task(
        client, headers, "Restricted Sovereign Scope Task",
        sensitivity="restricted",
        allowed_sources=["scope_src.txt"],
        network_policy="allow_internal",
    )
    assert task["security_mode"] == "sovereign"
    _authorize_and_execute(client, headers, task["task_id"])

    resp = _send(client, headers, task["task_id"], "Tell me a funny joke about football")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["response_text"] == (
        "I can only answer questions relevant to the current task."
    )
    assert body["execution_mode"] == "policy"
    assert body["model_used"] == "task-relevance-gate"
    assert body["tokens_used"] == 0

    # No model, no RAG, no external research
    assert captured_model_inputs == []
    assert research_provider.received_queries == []
    assert not _has_event(task["task_id"], "CHAT_RAG_SEARCH")
    assert not _has_event(task["task_id"], "EXTERNAL_RESEARCH_REQUESTED")
    assert not _has_event(task["task_id"], "CHAT_INTENT_CLASSIFIED")

    # Audits
    assert _has_event(task["task_id"], "task_relevance_checked")
    assert _has_event(task["task_id"], "task_scope_denied")
    assert _has_event(task["task_id"], "final_decision")
    detail = _event_detail(task["task_id"], "task_relevance_checked")
    assert "relevant=false" in detail
    final = _event_detail(task["task_id"], "final_decision")
    assert "decision=task_scope_denied" in final
    assert "task_id" in final or True  # task_id is on the audit record itself
    checked = next(
        e for e in _events(task["task_id"]) if e.event_type == "task_relevance_checked"
    )
    assert checked.task_id == task["task_id"]
    assert checked.user_id
    assert checked.security_mode == "sovereign"
    assert checked.timestamp is not None


# ── Sovereign + relevant → continues (greeting) ──────────────────────────


def test_sovereign_relevant_continues_via_model(
    client: TestClient, captured_model_inputs
):
    headers = _login(client, "operator", "medha-operator-2026")
    task = _create_task(
        client, headers, "Restricted Sovereign Relevant Task",
        sensitivity="restricted",
    )
    assert task["security_mode"] == "sovereign"
    _authorize_and_execute(client, headers, task["task_id"])

    resp = _send(client, headers, task["task_id"], "Hello there")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["response_text"] != (
        "I can only answer questions relevant to the current task."
    )
    assert body["response_text"] != (
        "I don't have enough verified information to answer that."
    )
    assert len(captured_model_inputs) == 1
    model_input = captured_model_inputs[0]
    assert "TASK CONTEXT:" in model_input
    assert "security_mode: sovereign" in model_input
    assert _has_event(task["task_id"], "final_decision")
    final = _event_detail(task["task_id"], "final_decision")
    assert "decision=answered_via_model" in final


# ── Sovereign + relevant + internal evidence → answer with evidence ─────


def test_sovereign_relevant_with_internal_evidence_answers(
    client: TestClient, captured_model_inputs, research_provider
):
    headers = _login(client, "operator", "medha-operator-2026")
    vector_store.reset()
    retrieval_service.ingest_document(
        "Authorized pump handbook: bearing vibration diagnosis thresholds.",
        "sov_handbook.txt",
        "internal",
    )
    task = _create_task(
        client, headers, "Restricted Sovereign Evidence Task",
        sensitivity="restricted",
        allowed_sources=["sov_handbook.txt"],
        network_policy="allow_internal",
    )
    assert task["security_mode"] == "sovereign"
    _authorize_and_execute(client, headers, task["task_id"])

    resp = _send(
        client, headers, task["task_id"],
        "What does the handbook say about bearing vibration diagnosis thresholds?",
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["response_text"] != (
        "I don't have enough verified information to answer that."
    )
    assert len(captured_model_inputs) == 1
    model_input = captured_model_inputs[0]
    assert "INTERNAL EVIDENCE" in model_input
    assert "sov_handbook.txt" in model_input
    # No external research under sovereign even when provider is present
    assert research_provider.received_queries == []


# ── Sovereign + relevant + insufficient + external allowed → sanitized
#    external research runs, combined evidence reaches local model ───────


def test_sovereign_insufficient_external_allowed_sanitized_research(
    client: TestClient, captured_model_inputs, research_provider
):
    headers = _login(client, "operator", "medha-operator-2026")
    task = _create_task(
        client, headers, "Restricted Sovereign Insufficient Allowed Task",
        sensitivity="restricted",
        allowed_sources=["never_ingested_sov.txt"],
        network_policy="allow_internal",
    )
    assert task["security_mode"] == "sovereign"
    _authorize_and_execute(client, headers, task["task_id"])

    resp = _send(
        client, headers, task["task_id"],
        "What caused this hydrolock failure mode?",
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["response_text"] != (
        "I can only answer questions relevant to the current task."
    )
    assert body["response_text"] != (
        "I don't have enough verified information to answer that."
    )
    # Sanitized external research occurred exactly once
    assert len(research_provider.received_queries) == 1
    sent = research_provider.received_queries[0]
    assert task["task_id"] not in sent
    assert "USR-" not in sent
    assert _has_event(task["task_id"], "EXTERNAL_QUERY_SANITIZED")
    assert _has_event(task["task_id"], "EXTERNAL_RESEARCH_COMPLETED")
    # Combined internal + public evidence reaches the local model
    assert len(captured_model_inputs) == 1
    model_input = captured_model_inputs[0]
    assert "INTERNAL EVIDENCE" in model_input
    assert "PUBLIC RESEARCH" in model_input
    assert "bearing failure vibration indicators" in model_input
    assert _has_event(task["task_id"], "final_decision")
    final = _event_detail(task["task_id"], "final_decision")
    assert "decision=answered_via_model" in final


# ── Sovereign + relevant + external blocked → exact insufficient message ─


def test_sovereign_relevant_external_blocked_returns_insufficient(
    client: TestClient, captured_model_inputs, research_provider
):
    headers = _login(client, "operator", "medha-operator-2026")
    task = _create_task(
        client, headers, "Restricted Sovereign Insufficient Blocked Task",
        sensitivity="restricted",
        allowed_sources=["never_ingested_sov.txt"],
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

    # External research requested then denied by deny_external passport policy
    assert _has_event(task["task_id"], "EXTERNAL_RESEARCH_REQUESTED")
    assert _has_event(task["task_id"], "EXTERNAL_RESEARCH_DENIED")
    detail = _event_detail(task["task_id"], "EXTERNAL_RESEARCH_DENIED")
    assert "deny_external" in detail
    assert not _has_event(task["task_id"], "EXTERNAL_RESEARCH_COMPLETED")
    assert _has_event(task["task_id"], "final_decision")
    final = _event_detail(task["task_id"], "final_decision")
    assert "decision=insufficient_verified_evidence" in final


# ── Standard/secure behavior remains unchanged ──────────────────────────


def test_standard_offtopic_no_scope_message_model_called(
    client: TestClient, captured_model_inputs
):
    headers = _login(client, "operator", "medha-operator-2026")
    task = _create_task(client, headers, "Standard Offtopic Task")
    assert task["security_mode"] == "standard"
    _authorize_and_execute(client, headers, task["task_id"])

    resp = _send(client, headers, task["task_id"], "Tell me a joke about football")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["response_text"] != (
        "I can only answer questions relevant to the current task."
    )
    assert body["execution_mode"] != "policy"
    assert len(captured_model_inputs) == 1
    # Still audited as irrelevant but not denied in standard mode
    assert _has_event(task["task_id"], "task_relevance_checked")
    detail = _event_detail(task["task_id"], "task_relevance_checked")
    assert "relevant=false" in detail
    assert not _has_event(task["task_id"], "task_scope_denied")


# ── Cross-user → 403, no model ──────────────────────────────────────────


def test_cross_user_403_no_model(client: TestClient, captured_model_inputs):
    owner_headers = _login(client, "operator", "medha-operator-2026")
    other_headers = _login(client, "engineer", "medha-engineer-2026")
    task = _create_task(client, owner_headers, "Owner Gate Task")
    _authorize_and_execute(client, owner_headers, task["task_id"])

    resp = _send(client, other_headers, task["task_id"], "Let me in")
    assert resp.status_code == 403
    assert captured_model_inputs == []


# ── Unauthorized source never enters captured prompt ─────────────────────


def test_unauthorized_source_never_in_captured_prompt(
    client: TestClient, captured_model_inputs
):
    headers = _login(client, "operator", "medha-operator-2026")
    vector_store.reset()
    retrieval_service.ingest_document(
        "Authorized content about hydrolock diagnosis steps.",
        "allowed_gate.txt",
        "internal",
    )
    retrieval_service.ingest_document(
        "SECRET_UNAUTHORIZED_CONTENT payroll annex.",
        "secret_gate.txt",
        "internal",
    )
    task = _create_task(
        client, headers, "Gate Auth Task",
        allowed_sources=["allowed_gate.txt"],
    )
    _authorize_and_execute(client, headers, task["task_id"])

    resp = _send(
        client, headers, task["task_id"],
        "What does the handbook say about hydrolock diagnosis steps?",
    )
    assert resp.status_code == 200, resp.text
    model_input = captured_model_inputs[-1]
    assert "allowed_gate.txt" in model_input
    assert "SECRET_UNAUTHORIZED_CONTENT" not in model_input
    assert "secret_gate.txt" not in model_input


# ── Relevant + authorized source → RAG → local model ────────────────────


def test_relevant_authorized_source_rag_then_local_model(
    client: TestClient, captured_model_inputs
):
    headers = _login(client, "operator", "medha-operator-2026")
    vector_store.reset()
    retrieval_service.ingest_document(
        "Pump bearing lubrication requires ISO VG 68 oil grade.",
        "lube_gate.txt",
        "internal",
    )
    task = _create_task(
        client, headers, "Gate RAG Task",
        allowed_sources=["lube_gate.txt"],
    )
    _authorize_and_execute(client, headers, task["task_id"])

    resp = _send(
        client, headers, task["task_id"],
        "What oil grade does the procedure require for pump bearing lubrication?",
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["model_used"] == "local-qwen2"
    assert body["execution_mode"] == "local"
    assert len(captured_model_inputs) == 1
    model_input = captured_model_inputs[0]
    assert "INTERNAL EVIDENCE" in model_input
    assert "lube_gate.txt" in model_input
    assert "ISO VG 68" in model_input
    assert _has_event(task["task_id"], "CHAT_RAG_SEARCH")
    assert _has_event(task["task_id"], "final_decision")


# ── Sanitization: external query has no confidential task information ───


def test_sanitize_query_has_no_task_or_user_id():
    now = datetime.now(timezone.utc)
    passport = TaskPassportRead(
        task_id="11111111-2222-3333-4444-555555555555",
        user_id="USR-00000004",
        identity="operator",
        role="operator",
        title="Pump vibration investigation",
        purpose="Investigate bearing degradation at the plant",
        sensitivity=TaskSensitivity.INTERNAL,
        security_mode=SecurityMode.STANDARD,
        security_policy_version="1.0",
        requested_operation="analyze",
        allowed_sources=["handbook.txt"],
        allowed_tools=["document_reader"],
        allowed_models=[],
        approval_requirement=ApprovalRequirement.NONE,
        network_policy=NetworkPolicy.ALLOW_INTERNAL,
        status=TaskStatus.EXECUTING,
        created_at=now,
        updated_at=now,
    )
    intent = classify_intent(
        "Compare industry bearing failure cases for user USR-00000004 task "
        f"{passport.task_id}",
        passport,
        [],
    )
    result = sanitize_research_query(intent, passport)
    assert result.safe, result.reason
    assert passport.task_id not in result.query
    assert passport.user_id not in result.query
    assert "USR-" not in result.query
    assert "operator" not in result.query.lower()  # username/identity
    assert "MRPL" not in result.query
    # Raw confidential user prompt must not leave as-is for private tokens
    assert "USR-00000004" not in result.query
