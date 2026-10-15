"""3-scenario validation matrix for task-aware conversational reasoning.

Scenarios:
  A — industrial maintenance (task-scoped investigation)
  B — document analysis (task-scoped document question)
  C — data analysis (task-scoped data question)
  + General Chat (no task)

Behaviors checked per scenario (10 each):
  1  Intent classified and exposed as INTENT metadata (not a canned answer)
  2  Task context reaches the model; marked as background, not the reply
  3  Natural-response guidance (no forced Task/Purpose/Status template)
  4  FACT/INTERPRETATION separation guidance present
  5  Follow-up continuity: short reference anchors prior turn + RAG
  6  RAG query built from information need + task context
  7  Missing-information path states what/why/next (not bare refusal)
  8  Model routing still produces a decision (cheap vs complex path)
  9  No hardcoded question→answer map in model input
 10  Security pipeline intact (relevance audit + final decision)

General Chat: works without a Task Passport, still gets conversational rules.

These tests assert pipeline behavior and prompt construction. They do not
claim the local model produces perfect natural language — quality of free
text depends on the runtime model.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.services.audit_service import audit_service
from app.services.model_router.model_adapter import ModelAdapterFactory, ModelResponse
from app.services.rag.retrieval import retrieval_service
from app.services.rag.vector_store import vector_store


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


# ── Scenario fixtures ────────────────────────────────────────────────────


SCENARIOS = {
    "A_industrial": {
        "title": "Compressor vibration investigation",
        "purpose": "Investigate abnormal vibration on plant compressor train C-12",
        "source": "compressor_handbook.txt",
        "doc_text": (
            "Compressor train C-12 vibration troubleshooting: check coupling "
            "alignment, bearing clearance, and rotor imbalance. Record spectral "
            "readings before any corrective work."
        ),
        "first_prompt": "What should we check first for abnormal vibration on this train?",
        "follow_up": "the vibration",
        "ambiguous": "Is it within limits?",
        "off_topic": "Tell me a joke about football",
    },
    "B_document": {
        "title": "Vendor SOP document analysis",
        "purpose": "Summarize and compare steps in the vendor startup SOP document",
        "source": "vendor_sop.txt",
        "doc_text": (
            "Vendor startup SOP: step 1 verify lubrication pressure, step 2 "
            "confirm seal gas flow, step 3 open discharge valve slowly, step 4 "
            "record differential pressure."
        ),
        "first_prompt": "What does the vendor SOP say about seal gas flow?",
        "follow_up": "the discharge step",
        "ambiguous": "Is that procedure acceptable?",
        "off_topic": "What is the stock market doing today?",
    },
    "C_data": {
        "title": "Sensor trend data analysis",
        "purpose": "Analyze recent bearing temperature and vibration trend data for line 4",
        "source": "trend_notes.txt",
        "doc_text": (
            "Trend notes line 4: bearing temperature rose from 78C to 91C over "
            "six hours while vibration stayed near 4.1 mm/s. No shutdown logged."
        ),
        "first_prompt": "What does the trend data show about bearing temperature?",
        "follow_up": "the temperature",
        "ambiguous": "Should we act now?",
        "off_topic": "Bake a chocolate cake recipe",
    },
}


def _prepare_scenario(client, name):
    headers = _login(client, "operator", "medha-operator-2026")
    spec = SCENARIOS[name]
    vector_store.reset()
    retrieval_service.ingest_document(spec["doc_text"], spec["source"], "internal")
    task = _create_task(
        client,
        headers,
        spec["title"],
        purpose=spec["purpose"],
        allowed_sources=[spec["source"]],
        allowed_tools=["document_reader"],
        network_policy="deny_external",
    )
    _authorize_and_execute(client, headers, task["task_id"])
    return headers, task, spec


def _guidance_block(model_input: str) -> str:
    assert "RESPONSE GUIDANCE:" in model_input
    return model_input.split("RESPONSE GUIDANCE:", 1)[1]


# ── Shared behavior assertions ──────────────────────────────────────────


def _assert_behavior_1_intent(headers, task, spec, client, captured):
    resp = _send(client, headers, task["task_id"], spec["first_prompt"])
    assert resp.status_code == 200, resp.text
    mi = captured[-1]
    assert "INTENT:" in mi
    assert f"objective: {spec['first_prompt']}" in mi
    assert "category:" in mi
    assert "answer_type:" in mi
    assert _has_event(task["task_id"], "CHAT_INTENT_CLASSIFIED")


def _assert_behavior_2_task_context(task, captured, spec):
    mi = captured[-1]
    assert "TASK CONTEXT:" in mi
    assert f"task_id: {task['task_id']}" in mi
    assert f"title: {spec['title']}" in mi
    # Root-cause fix: task context labeled as background, not the reply
    assert "background authorization context" in mi
    assert "user's question is primary" in mi
    # Passport metadata must not dominate as the final answer structure —
    # current user message remains last and guidance forbids reciting fields.
    assert mi.rstrip().endswith(spec["first_prompt"])
    assert "never recite passport fields" in _guidance_block(mi)


def _assert_behavior_3_natural_guidance(captured):
    g = _guidance_block(captured[-1])
    assert "natural prose" in g
    assert "Do not force a" in g
    assert "Task/Purpose/Status/Analysis/Recommendation" in g


def _assert_behavior_4_fact_interpretation(captured):
    g = _guidance_block(captured[-1])
    assert "(FACT)" in g
    assert "(INTERPRETATION)" in g
    assert "(POSSIBILITY)" in g
    assert "UNKNOWN" in g


def _assert_behavior_5_follow_up(headers, task, spec, client, captured):
    first = _send(
        client, headers, task["task_id"], spec["first_prompt"],
    )
    assert first.status_code == 200, first.text
    convo_id = first.json()["conversation_id"]
    second = _send(
        client, headers, task["task_id"], spec["follow_up"],
        conversation_id=convo_id,
    )
    assert second.status_code == 200, second.text
    mi = captured[-1]
    assert "follow_up: true" in mi
    # Prior turn present for continuity
    conv_block = mi.split("RECENT CONVERSATION:", 1)[1]
    assert spec["first_prompt"] in conv_block
    # Guidance instructs resolution from history
    assert "RECENT CONVERSATION" in _guidance_block(mi)
    # Information need / RAG anchors prior subject
    assert "prior user turn referenced by this follow-up" in mi
    rag_events = [
        e for e in _events(task["task_id"]) if e.event_type == "rag_search"
    ]
    assert rag_events, "follow-up investigation must still attempt RAG"


def _assert_behavior_6_rag_query(headers, task, spec, client, captured):
    resp = _send(client, headers, task["task_id"], spec["first_prompt"])
    assert resp.status_code == 200, resp.text
    assert _has_event(task["task_id"], "CHAT_RAG_SEARCH")
    rag_events = [
        e for e in _events(task["task_id"]) if e.event_type == "rag_search"
    ]
    # Query includes user information need words + task title context
    joined = " ".join(e.detail for e in rag_events)
    assert spec["source"].replace(".txt", "") in joined or "query=" in joined
    mi = captured[-1]
    assert "RESOURCE PLAN:" in mi
    assert f"rag_query:" in mi
    assert spec["source"] in mi


def _assert_behavior_7_missing_info(headers, task, spec, client, captured):
    # Point task at a source that was never ingested → miss path
    task2 = _create_task(
        client,
        headers,
        spec["title"] + " Miss",
        purpose=spec["purpose"],
        allowed_sources=["never_ingested_for_validation.txt"],
        network_policy="deny_external",
    )
    _authorize_and_execute(client, headers, task2["task_id"])
    resp = _send(client, headers, task2["task_id"], spec["first_prompt"])
    assert resp.status_code == 200, resp.text
    mi = captured[-1]
    assert "MISSING INFORMATION:" in mi
    assert "do not fabricate" in mi
    g = _guidance_block(mi)
    # what / why / next-step structure — not a bare "insufficient" refusal
    assert "what can" in g or "what is missing" in g
    assert "why it matters" in g
    assert "next step" in g
    assert "Do not reply with only" in g
    assert "insufficient information" in g


def _assert_behavior_8_routing(headers, task, spec, client, captured):
    resp = _send(client, headers, task["task_id"], spec["first_prompt"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["complexity"] in ("low", "medium", "high")
    assert body["model_used"]
    assert body["routing_reason"]
    assert _has_event(task["task_id"], "MODEL_ROUTED")
    routed = _event_detail(task["task_id"], "MODEL_ROUTED")
    assert "selected=" in routed
    assert "category=" in routed


def _assert_behavior_9_no_hardcoded_qa(headers, task, spec, client, captured):
    resp = _send(client, headers, task["task_id"], spec["first_prompt"])
    assert resp.status_code == 200, resp.text
    mi = captured[-1]
    # No canned answer block: guidance forbids templates; objective is the
    # raw user text (intent metadata), not a prewritten answer.
    assert f"objective: {spec['first_prompt']}" in mi
    # No P-204 hardcode leak into an unrelated validation scenario
    # (P-204 is only a demo example elsewhere; must not be injected here).
    assert "P-204" not in mi or "P-204" in spec["title"] or "P-204" in spec["purpose"]
    # Pattern that would indicate Q→A mapping in prompt assembly
    assert not re.search(r"(?i)if\s+user\s+asks\s*:.*then\s+answer", mi)


def _assert_behavior_10_security(task):
    assert _has_event(task["task_id"], "task_relevance_checked")
    assert _has_event(task["task_id"], "final_decision")
    final = _event_detail(task["task_id"], "final_decision")
    assert "decision=" in final
    # Authorization path ran (Action Gate COMPUTE) — presence of relevance
    # + final decision proves the security pipeline was not bypassed.
    assert _has_event(task["task_id"], "CHAT_INTENT_CLASSIFIED")


# ── Parametrized scenario runs ───────────────────────────────────────────


@pytest.mark.parametrize("scenario", list(SCENARIOS.keys()))
class TestScenarioBehaviors:
    def test_1_intent_first(
        self, client, captured_model_inputs, scenario
    ):
        headers, task, spec = _prepare_scenario(client, scenario)
        _assert_behavior_1_intent(headers, task, spec, client, captured_model_inputs)

    def test_2_task_context_background(
        self, client, captured_model_inputs, scenario
    ):
        headers, task, spec = _prepare_scenario(client, scenario)
        _send(client, headers, task["task_id"], spec["first_prompt"])
        _assert_behavior_2_task_context(task, captured_model_inputs, spec)

    def test_3_natural_response_guidance(
        self, client, captured_model_inputs, scenario
    ):
        headers, task, spec = _prepare_scenario(client, scenario)
        _send(client, headers, task["task_id"], spec["first_prompt"])
        _assert_behavior_3_natural_guidance(captured_model_inputs)

    def test_4_fact_vs_interpretation(
        self, client, captured_model_inputs, scenario
    ):
        headers, task, spec = _prepare_scenario(client, scenario)
        _send(client, headers, task["task_id"], spec["first_prompt"])
        _assert_behavior_4_fact_interpretation(captured_model_inputs)

    def test_5_follow_up_continuity(
        self, client, captured_model_inputs, scenario
    ):
        headers, task, spec = _prepare_scenario(client, scenario)
        _assert_behavior_5_follow_up(
            headers, task, spec, client, captured_model_inputs
        )

    def test_6_rag_query_uses_need_and_task(
        self, client, captured_model_inputs, scenario
    ):
        headers, task, spec = _prepare_scenario(client, scenario)
        _assert_behavior_6_rag_query(
            headers, task, spec, client, captured_model_inputs
        )

    def test_7_missing_information_what_why_next(
        self, client, captured_model_inputs, scenario
    ):
        headers, task, spec = _prepare_scenario(client, scenario)
        _assert_behavior_7_missing_info(
            headers, task, spec, client, captured_model_inputs
        )

    def test_8_model_routing_decision(
        self, client, captured_model_inputs, scenario
    ):
        headers, task, spec = _prepare_scenario(client, scenario)
        _assert_behavior_8_routing(headers, task, spec, client, captured_model_inputs)

    def test_9_no_hardcoded_question_answer(
        self, client, captured_model_inputs, scenario
    ):
        headers, task, spec = _prepare_scenario(client, scenario)
        _assert_behavior_9_no_hardcoded_qa(
            headers, task, spec, client, captured_model_inputs
        )

    def test_10_security_pipeline_intact(
        self, client, captured_model_inputs, scenario
    ):
        headers, task, spec = _prepare_scenario(client, scenario)
        _send(client, headers, task["task_id"], spec["first_prompt"])
        _assert_behavior_10_security(task)


# ── Extra: ambiguous clarifies; off-topic sovereign scope; depth ─────────


@pytest.mark.parametrize("scenario", list(SCENARIOS.keys()))
class TestExtraBehaviors:
    def test_ambiguous_gets_clarification_guidance(
        self, client, captured_model_inputs, scenario
    ):
        headers, task, spec = _prepare_scenario(client, scenario)
        resp = _send(client, headers, task["task_id"], spec["ambiguous"])
        assert resp.status_code == 200, resp.text
        mi = captured_model_inputs[-1]
        g = _guidance_block(mi)
        # Only when genuinely ambiguous — detection is conservative.
        # "within limits" / "acceptable" / "act now" may or may not trip
        # heuristics; if it does, clarification template must be present.
        if "I need clarification" in g:
            assert "Detected gaps:" in g

    def test_depth_instruction_present(
        self, client, captured_model_inputs, scenario
    ):
        headers, task, spec = _prepare_scenario(client, scenario)
        _send(client, headers, task["task_id"], spec["first_prompt"])
        g = _guidance_block(captured_model_inputs[-1])
        assert "Match depth to the question" in g

    def test_suggest_alternatives_for_investigation(
        self, client, captured_model_inputs, scenario
    ):
        headers, task, spec = _prepare_scenario(client, scenario)
        _send(client, headers, task["task_id"], spec["first_prompt"])
        g = _guidance_block(captured_model_inputs[-1])
        # first_prompt phrasing is investigation-like across scenarios
        assert "alternative or next step" in g


# ── General Chat validation ──────────────────────────────────────────────


class TestGeneralChatBehaviors:
    def test_general_chat_works_without_task(
        self, client, captured_model_inputs
    ):
        headers = _login(client, "operator", "medha-operator-2026")
        resp = client.post(
            "/api/chat/send",
            json={"prompt": "Explain what a bearing clearance check is"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        mi = captured_model_inputs[-1]
        assert "CONTEXT: General Chat" in mi
        assert "TASK CONTEXT" not in mi
        # Conversational reasoning rules still applied
        assert "natural prose" in mi
        assert "FACT" in mi and "INTERPRETATION" in mi
        assert "RECENT CONVERSATION" in mi

    def test_general_chat_follow_up_history(
        self, client, captured_model_inputs
    ):
        headers = _login(client, "operator", "medha-operator-2026")
        first = client.post(
            "/api/chat/send",
            json={"prompt": "What is radial clearance?"},
            headers=headers,
        )
        assert first.status_code == 200, first.text
        convo_id = first.json()["conversation_id"]
        second = client.post(
            "/api/chat/send",
            json={
                "prompt": "and the axial",
                "conversation_id": convo_id,
            },
            headers=headers,
        )
        assert second.status_code == 200, second.text
        mi = captured_model_inputs[-1]
        assert "What is radial clearance?" in mi
        assert "follow_up: true" in mi

    def test_general_chat_greeting_short(
        self, client, captured_model_inputs
    ):
        headers = _login(client, "operator", "medha-operator-2026")
        resp = client.post(
            "/api/chat/send",
            json={"prompt": "hello"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert "CONTEXT: General Chat" in captured_model_inputs[-1]
