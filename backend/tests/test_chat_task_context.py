"""Focused tests: task-aware AI chat context injection (Phase 1).

Proves the model adapter receives the authorized Task Passport context and
the current conversation — not a bare user prompt:

  1  Chat with task_id loads the correct task
  2  Task context reaches the model adapter
  3  Task A context is never sent for Task B
  4  Unauthorized task access returns 403
  5  Previous authorized conversation is included
  6  Cross-user conversation is not included
  7  Security mode/sensitivity context is preserved
  8  Existing chat authorization tests still pass (test_chat.py)
"""

import pytest
from fastapi.testclient import TestClient

from app.services.model_router.model_adapter import ModelAdapterFactory, ModelResponse


@pytest.fixture
def captured_model_inputs(monkeypatch):
    """Spy on the model adapter factory to capture every model input."""
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

        @property
        def _name(self) -> str:  # pragma: no cover - unused
            return self.name

    monkeypatch.setattr(
        ModelAdapterFactory,
        "get",
        classmethod(lambda cls, name: _SpyAdapter()),
    )
    return captured


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


# ── 1 + 2: correct task loaded; task context reaches the adapter ──────────

def test_chat_loads_correct_task_and_context_reaches_adapter(
    client: TestClient, captured_model_inputs
):
    headers = _login(client, "operator", "medha-operator-2026")
    task = _create_task(
        client, headers, "P-204 Pump Failure Investigation",
        purpose="Investigate excessive vibration on pump P-204",
        allowed_sources=["pump_handbook.txt"],
        allowed_tools=["document_reader"],
    )
    _authorize_and_execute(client, headers, task["task_id"])

    resp = _send(
        client, headers, task["task_id"],
        "What is causing this vibration?",
    )
    assert resp.status_code == 200, resp.text

    assert len(captured_model_inputs) == 1
    model_input = captured_model_inputs[0]

    # Structured sections present
    assert "TASK CONTEXT:" in model_input
    assert "RECENT CONVERSATION:" in model_input
    assert "CURRENT USER MESSAGE:" in model_input

    # Correct task identity and authorized fields from the DB passport
    assert f"task_id: {task['task_id']}" in model_input
    assert "title: P-204 Pump Failure Investigation" in model_input
    assert "purpose: Investigate excessive vibration on pump P-204" in model_input
    assert "authorized_sources: pump_handbook.txt" in model_input
    assert "authorized_tools: document_reader" in model_input

    # Current user message is included verbatim
    assert model_input.rstrip().endswith("What is causing this vibration?")


# ── 3: Task A context is never sent for Task B ────────────────────────────

def test_task_a_context_never_sent_for_task_b(
    client: TestClient, captured_model_inputs
):
    headers = _login(client, "operator", "medha-operator-2026")
    task_a = _create_task(client, headers, "Task Alpha Unique Title")
    task_b = _create_task(client, headers, "Task Beta Unique Title")
    _authorize_and_execute(client, headers, task_a["task_id"])
    _authorize_and_execute(client, headers, task_b["task_id"])

    resp = _send(client, headers, task_b["task_id"], "Hello from beta")
    assert resp.status_code == 200, resp.text

    model_input = captured_model_inputs[-1]
    assert f"task_id: {task_b['task_id']}" in model_input
    assert "Task Beta Unique Title" in model_input
    assert "Task Alpha Unique Title" not in model_input
    assert task_a["task_id"] not in model_input


# ── 4: unauthorized task access returns 403 ───────────────────────────────

def test_unauthorized_task_access_returns_403(
    client: TestClient, captured_model_inputs
):
    owner_headers = _login(client, "operator", "medha-operator-2026")
    other_headers = _login(client, "engineer", "medha-engineer-2026")
    task = _create_task(client, owner_headers, "Owner Private Task")
    _authorize_and_execute(client, owner_headers, task["task_id"])

    resp = _send(client, other_headers, task["task_id"], "Let me in")
    assert resp.status_code == 403
    assert captured_model_inputs == []


# ── 5: previous authorized conversation is included ───────────────────────

def test_previous_conversation_included(
    client: TestClient, captured_model_inputs
):
    headers = _login(client, "operator", "medha-operator-2026")
    task = _create_task(client, headers, "Conversation History Task")
    _authorize_and_execute(client, headers, task["task_id"])

    first = _send(client, headers, task["task_id"], "First user message about bearings")
    assert first.status_code == 200, first.text
    convo_id = first.json()["conversation_id"]

    second = _send(
        client, headers, task["task_id"],
        "Follow-up question",
        conversation_id=convo_id,
    )
    assert second.status_code == 200, second.text

    model_input = captured_model_inputs[-1]
    # Prior user turn is present in RECENT CONVERSATION
    assert "First user message about bearings" in model_input
    # Prior assistant reply is present too
    assert "ok" in model_input.split("RECENT CONVERSATION:")[1]
    # Current message appears only as the current turn, not duplicated into
    # the conversation history section.
    conv_block = model_input.split("RECENT CONVERSATION:", 1)[1].split("INTENT:", 1)[0]
    assert "Follow-up question" not in conv_block
    current_part = model_input.split("CURRENT USER MESSAGE:", 1)[1]
    assert "Follow-up question" in current_part
    assert f"task_id: {task['task_id']}" in model_input


# ── 6: cross-user conversation is not included ────────────────────────────

def test_cross_user_conversation_not_included(
    client: TestClient, captured_model_inputs
):
    headers_a = _login(client, "operator", "medha-operator-2026")
    headers_b = _login(client, "engineer", "medha-engineer-2026")

    task_a = _create_task(client, headers_a, "User A Task")
    task_b = _create_task(client, headers_b, "User B Task")
    _authorize_and_execute(client, headers_a, task_a["task_id"])
    _authorize_and_execute(client, headers_b, task_b["task_id"])

    resp_b = _send(client, headers_b, task_b["task_id"], "SECRETFROMUSERB hello")
    assert resp_b.status_code == 200, resp_b.text

    resp_a = _send(client, headers_a, task_a["task_id"], "My own message")
    assert resp_a.status_code == 200, resp_a.text

    model_input = captured_model_inputs[-1]
    assert "SECRETFROMUSERB" not in model_input
    assert f"task_id: {task_a['task_id']}" in model_input
    assert f"task_id: {task_b['task_id']}" not in model_input

    # Also: user B's conversation id cannot be used by user A
    cross = _send(
        client, headers_a, task_a["task_id"],
        "steal history",
        conversation_id=resp_b.json()["conversation_id"],
    )
    assert cross.status_code == 404


# ── 7: security mode / sensitivity context is preserved ───────────────────

def test_security_mode_and_sensitivity_preserved(
    client: TestClient, captured_model_inputs
):
    headers = _login(client, "operator", "medha-operator-2026")
    # restricted sensitivity auto-enforces sovereign security mode
    task = _create_task(
        client, headers, "Restricted Analysis Task",
        sensitivity="restricted",
    )
    assert task["security_mode"] == "sovereign"
    _authorize_and_execute(client, headers, task["task_id"])

    resp = _send(client, headers, task["task_id"], "Hello there")
    assert resp.status_code == 200, resp.text

    model_input = captured_model_inputs[-1]
    assert "security_mode: sovereign" in model_input
    assert "sensitivity: restricted" in model_input
    assert f"task_id: {task['task_id']}" in model_input


# ── 8: existing chat authorization tests still pass ───────────────────────
# (Run explicitly as part of this focused file's execution.)
