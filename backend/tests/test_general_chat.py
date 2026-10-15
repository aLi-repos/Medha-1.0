"""General Chat (nullable task_id) tests.

Covers:
  - task_id null/omitted → 200 in standard / secure / sovereign
  - no task_relevance_checked / no task_scope_denied / no scope message
  - no Task Passport created; conversation stores task_id=""
  - no task RAG / no external research on general path
  - security mode comes from current_user.preferred_security_mode
  - task send still runs the full task-aware pipeline
  - task ↔ general conversation listing isolation
  - model selection blocked for external model under sovereign
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.services.audit_service import audit_service
from app.services.model_router.model_adapter import ModelAdapterFactory, ModelResponse


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


# ── Helpers ──────────────────────────────────────────────────────────────


def _login(client: TestClient, username: str, password: str) -> dict:
    resp = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _set_mode(client: TestClient, headers: dict, mode: str) -> None:
    resp = client.patch(
        "/api/auth/security-mode",
        json={"security_mode": mode},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text


def _send_general(
    client: TestClient,
    headers: dict,
    prompt: str,
    conversation_id: str | None = None,
    model: str | None = None,
):
    body: dict = {"prompt": prompt}
    if conversation_id:
        body["conversation_id"] = conversation_id
    if model:
        body["model"] = model
    return client.post("/api/chat/send", json=body, headers=headers)


def _events(task_id: str) -> list:
    return audit_service.get_events_for_task(task_id)


def _has_event(task_id: str, event_type: str) -> bool:
    return any(e.event_type == event_type for e in _events(task_id))


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


def _task_count(client: TestClient, headers: dict) -> int:
    resp = client.get("/api/tasks", headers=headers)
    assert resp.status_code == 200, resp.text
    return len(resp.json())


# ── General Chat: null task_id works across three security modes ─────────


@pytest.mark.parametrize(
    "username,password,mode",
    [
        ("operator", "medha-operator-2026", "standard"),
        ("engineer", "medha-engineer-2026", "secure"),
        ("admin", "medha-admin-2026", "sovereign"),
    ],
)
def test_general_chat_sends_in_all_security_modes(
    client: TestClient, captured_model_inputs, username, password, mode
):
    headers = _login(client, username, password)
    # engineer default is standard; raise to secure for this param case.
    if mode == "secure":
        _set_mode(client, headers, "secure")
    if mode == "standard":
        _set_mode(client, headers, "standard")

    me = client.get("/api/auth/me", headers=headers).json()
    assert me["preferred_security_mode"] == mode

    resp = _send_general(client, headers, "What is a bearing?")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["model_used"] == "local-qwen2"
    assert body["execution_mode"] == "local"
    assert body["response_text"]
    assert len(captured_model_inputs) == 1

    # General path: no task pipeline audits
    assert not _has_event("", "task_relevance_checked")
    assert not _has_event("", "task_scope_denied")
    assert not _has_event("", "CHAT_RAG_SEARCH")
    assert _has_event("", "chat_message_sent")
    assert _has_event("", "final_decision")

    # Conversation is general (task_id empty string in DB / API)
    convo_id = body["conversation_id"]
    convos = client.get("/api/chat/conversations/general", headers=headers).json()
    assert convos["total"] >= 1
    match = [c for c in convos["conversations"] if c["id"] == convo_id]
    assert match and match[0]["task_id"] == ""

    # No Task Passport created by general chat
    assert _task_count(client, headers) == 0


def test_general_chat_null_vs_omitted_task_id(
    client: TestClient, captured_model_inputs
):
    headers = _login(client, "operator", "medha-operator-2026")

    resp_null = client.post(
        "/api/chat/send",
        json={"task_id": None, "prompt": "hello null"},
        headers=headers,
    )
    assert resp_null.status_code == 200, resp_null.text

    resp_omit = client.post(
        "/api/chat/send",
        json={"prompt": "hello omitted"},
        headers=headers,
    )
    assert resp_omit.status_code == 200, resp_omit.text

    assert len(captured_model_inputs) == 2
    for model_input in captured_model_inputs:
        assert "CONTEXT: General Chat" in model_input
        assert "TASK CONTEXT" not in model_input
        assert "SECURITY MODE: standard" in model_input

    assert not _has_event("", "task_relevance_checked")
    assert not _has_event("", "task_scope_denied")


def test_general_chat_create_conversation_without_task(
    client: TestClient, operator_token: str
):
    headers = {"Authorization": f"Bearer {operator_token}"}
    resp = client.post(
        "/api/chat/conversations",
        json={"task_id": None, "title": "General Chat convo"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["task_id"] == ""
    assert data["title"] == "General Chat convo"


def test_general_chat_list_general_path_only_returns_general(
    client: TestClient, captured_model_inputs
):
    headers = _login(client, "operator", "medha-operator-2026")

    # One general send → one general conversation
    g = _send_general(client, headers, "general question")
    assert g.status_code == 200, g.text

    # One task send → one task conversation
    task = _create_task(client, headers, "Isolation Task")
    _authorize_and_execute(client, headers, task["task_id"])
    t = client.post(
        "/api/chat/send",
        json={"task_id": task["task_id"], "prompt": "task question"},
        headers=headers,
    )
    assert t.status_code == 200, t.text

    general = client.get("/api/chat/conversations/general", headers=headers).json()
    assert general["total"] == 1
    assert all(c["task_id"] == "" for c in general["conversations"])
    assert general["conversations"][0]["id"] == g.json()["conversation_id"]

    task_list = client.get(
        f"/api/chat/conversations/{task['task_id']}", headers=headers
    ).json()
    assert task_list["total"] == 1
    assert task_list["conversations"][0]["task_id"] == task["task_id"]
    assert task_list["conversations"][0]["id"] == t.json()["conversation_id"]

    # Task pipeline still active for task sends
    assert _has_event(task["task_id"], "task_relevance_checked")
    assert _has_event(task["task_id"], "final_decision")


def test_general_chat_reuses_conversation_history(
    client: TestClient, captured_model_inputs
):
    headers = _login(client, "operator", "medha-operator-2026")
    first = _send_general(client, headers, "first turn")
    assert first.status_code == 200, first.text
    convo_id = first.json()["conversation_id"]

    second = _send_general(
        client, headers, "second turn", conversation_id=convo_id
    )
    assert second.status_code == 200, second.text
    assert second.json()["conversation_id"] == convo_id

    # Second turn model input includes prior conversation
    assert len(captured_model_inputs) == 2
    assert "second turn" in captured_model_inputs[1]
    assert "first turn" in captured_model_inputs[1]

    msgs = client.get(f"/api/chat/messages/{convo_id}", headers=headers).json()
    assert msgs["total"] == 4  # user, assistant, user, assistant
    roles = [m["role"] for m in msgs["messages"]]
    assert roles == ["user", "assistant", "user", "assistant"]


def test_general_chat_cannot_send_into_task_conversation(
    client: TestClient, captured_model_inputs
):
    headers = _login(client, "operator", "medha-operator-2026")
    task = _create_task(client, headers, "Bound Task")
    _authorize_and_execute(client, headers, task["task_id"])
    t = client.post(
        "/api/chat/send",
        json={"task_id": task["task_id"], "prompt": "task turn"},
        headers=headers,
    )
    assert t.status_code == 200, t.text
    task_convo = t.json()["conversation_id"]

    resp = _send_general(
        client, headers, "hijack general", conversation_id=task_convo
    )
    assert resp.status_code == 400
    assert "bound to a task" in resp.json()["detail"].lower()


def test_general_chat_sovereign_blocks_external_model(
    client: TestClient, captured_model_inputs
):
    headers = _login(client, "admin", "medha-admin-2026")
    resp = _send_general(
        client, headers, "explain photosynthesis", model="api-openai"
    )
    assert resp.status_code == 403
    assert not captured_model_inputs


def test_general_chat_empty_string_task_id_treated_as_general(
    client: TestClient, captured_model_inputs
):
    headers = _login(client, "operator", "medha-operator-2026")
    resp = client.post(
        "/api/chat/send",
        json={"task_id": "", "prompt": "empty string task id"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert len(captured_model_inputs) == 1
    assert "CONTEXT: General Chat" in captured_model_inputs[0]
    assert not _has_event("", "task_relevance_checked")


def test_general_chat_model_input_has_no_task_scope_message(
    client: TestClient, captured_model_inputs
):
    headers = _login(client, "admin", "medha-admin-2026")  # sovereign
    resp = _send_general(
        client, headers, "Tell me a funny joke about football"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "I can only answer questions relevant to the current task." not in body["response_text"]
    model_input = captured_model_inputs[0]
    assert "TASK CONTEXT" not in model_input
    assert "CONTEXT: General Chat" in model_input
    assert "SECURITY MODE: sovereign" in model_input
    # Sovereign general guidance is present (local only, no external)
    assert "local model only" in model_input
    assert not _has_event("", "task_scope_denied")
    assert not _has_event("", "task_relevance_checked")
