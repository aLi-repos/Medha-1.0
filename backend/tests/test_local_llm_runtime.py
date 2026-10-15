"""Phase 4 — real local LLM runtime tests.

Transport-level mocking only (_http_post/_http_get in conftest); the real
LocalLLMClient / LocalSmallLLMAdapter / chat pipeline code executes.

Covers:
 1  local adapter calls the local inference runtime (transport payload)
 2  simulated echo response no longer used on the local production path
 3  model configuration comes from backend configuration
 4  local model health check works (AVAILABLE / UNAVAILABLE)
 5  unavailable local model fails safely (503, no fabrication)
 6  Sovereign mode never selects an external model
 7  allowed-model policy remains enforced (existing test also covers)
 8  task context reaches the real adapter (via transport capture)
 9  RAG evidence reaches the model
10  public research reaches the model only when permitted
11  local execution audits recorded
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.schemas.task import (
    ApprovalRequirement,
    NetworkPolicy,
    SecurityMode,
    TaskPassportRead,
    TaskSensitivity,
    TaskStatus,
)
from app.services.audit_service import audit_service
from app.services.model_router import model_adapter as ma
from app.services.model_router.model_adapter import (
    UNAVAILABLE_MESSAGE,
    LocalLLMClient,
    LocalSmallLLMAdapter,
    ModelAdapterFactory,
)
from app.services.model_router.router import ModelRouter
from app.services.privacy_gateway import (
    DeterministicTestSearchProvider,
    UnavailablePublicSearchProvider,
    privacy_gateway,
)
from app.services.rag.retrieval import retrieval_service
from app.services.rag.vector_store import vector_store


# ── Helpers ──────────────────────────────────────────────────────────────


def _login(client: TestClient, username: str, password: str) -> dict:
    resp = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_and_execute(
    client: TestClient, headers: dict, title: str, **kwargs
) -> dict:
    resp = client.post(
        "/api/tasks",
        json={"title": title, "purpose": f"Purpose for {title}", **kwargs},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    task = resp.json()
    for status_name in ("authorized", "executing"):
        r = client.patch(
            f"/api/tasks/{task['task_id']}/status",
            json={"new_status": status_name, "detail": f"to {status_name}"},
            headers=headers,
        )
        assert r.status_code == 200, r.text
    return task


def _send(client: TestClient, headers: dict, task_id: str, prompt: str, **extra):
    return client.post(
        "/api/chat/send",
        json={"task_id": task_id, "prompt": prompt, **extra},
        headers=headers,
    )


def _events(task_id: str) -> list:
    return audit_service.get_events_for_task(task_id)


def _has(task_id: str, event_type: str) -> bool:
    return any(e.event_type == event_type for e in _events(task_id))


@pytest.fixture
def capturing_transport(monkeypatch):
    """Replace conftest transport with one that captures generate prompts."""
    prompts: list[str] = []

    def fake_post(url: str, payload: dict, timeout: int) -> dict:
        assert url.endswith("/api/generate")
        prompt = str(payload.get("prompt", ""))
        prompts.append(prompt)
        return {
            "model": payload.get("model"),
            "response": "Real local model answer grounded in provided context.",
            "eval_count": 12,
        }

    monkeypatch.setattr(ma, "_http_post", fake_post)
    return prompts


@pytest.fixture
def research_provider():
    provider = DeterministicTestSearchProvider()
    privacy_gateway.set_provider(provider)
    yield provider
    privacy_gateway.set_provider(UnavailablePublicSearchProvider())


# ── 1–4: adapter, config, health ─────────────────────────────────────────


class TestLocalRuntime:
    def test_adapter_calls_local_runtime(self, monkeypatch):
        calls: list[dict] = []

        def fake_post(url, payload, timeout):
            calls.append({"url": url, "payload": payload, "timeout": timeout})
            return {"response": "runtime says hi", "eval_count": 3}

        monkeypatch.setattr(ma, "_http_post", fake_post)
        resp = LocalSmallLLMAdapter().generate("hello context", max_tokens=64)

        assert len(calls) == 1
        assert calls[0]["url"].endswith("/api/generate")
        assert calls[0]["payload"]["prompt"] == "hello context"
        assert calls[0]["payload"]["stream"] is False
        assert calls[0]["payload"]["options"]["num_predict"] == 64
        assert calls[0]["payload"]["model"] == "qwen2.5:3b-instruct"
        assert calls[0]["payload"]["model"] == settings.local_llm_model
        assert resp.text == "runtime says hi"
        assert resp.tokens_used == 3

    def test_simulated_echo_not_used(self, monkeypatch):
        monkeypatch.setattr(
            ma,
            "_http_post",
            lambda url, payload, timeout: {
                "response": "Transport-provided local completion",
                "eval_count": 5,
            },
        )
        resp = LocalSmallLLMAdapter().generate("anything")
        assert resp.text == "Transport-provided local completion"
        assert "Local Qwen-2 Analysis" not in resp.text
        assert "Based on the provided context" not in resp.text

    def test_configuration_from_backend_settings(self):
        client = LocalLLMClient()
        assert client.base_url == settings.local_llm_base_url
        assert client.model == settings.local_llm_model
        assert client.timeout == settings.local_llm_timeout
        # Explicit overrides (per-instance) win over settings.
        custom = LocalLLMClient(base_url="http://127.0.0.1:9999", model="m2", timeout=5)
        assert custom.base_url == "http://127.0.0.1:9999"
        assert custom.model == "m2"
        assert custom.timeout == 5
        # Settings fields exist and are non-empty (env-driven).
        assert settings.local_llm_base_url.startswith("http")
        assert settings.local_llm_model
        assert settings.local_llm_timeout > 0

    def test_configured_model_is_qwen_3b_instruct(self):
        # Configuration test (not a real-inference test): the app must be
        # configured for qwen2.5:3b-instruct via the existing env/config path.
        assert settings.local_llm_model == "qwen2.5:3b-instruct"
        assert LocalLLMClient().model == "qwen2.5:3b-instruct"

    def test_health_available(self, client: TestClient):
        # conftest fake_get serves /api/tags with the configured model.
        resp = client.get("/health/local-llm")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "AVAILABLE"
        assert body["model"] == "qwen2.5:3b-instruct"
        assert body["model"] == settings.local_llm_model
        assert body["runtime"] == "ollama-compatible"
        assert "reason" in body
        # must not expose internals like base URL credentials
        assert "base_url" not in body

    def test_health_unavailable_runtime(self, client: TestClient, monkeypatch):
        def boom(url, timeout):
            raise ConnectionRefusedError("no server")

        monkeypatch.setattr(ma, "_http_get", boom)
        resp = client.get("/health/local-llm")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "UNAVAILABLE"
        assert "unreachable" in body["reason"]

    def test_health_unavailable_model_not_installed(
        self, client: TestClient, monkeypatch
    ):
        monkeypatch.setattr(
            ma,
            "_http_get",
            lambda url, timeout: {"models": [{"name": "other-model:latest"}]},
        )
        resp = client.get("/health/local-llm")
        body = resp.json()
        assert body["status"] == "UNAVAILABLE"
        assert "not installed" in body["reason"]


# ── 5: fail closed when runtime unavailable ──────────────────────────────


class TestFailClosed:
    def test_chat_fails_closed_when_runtime_down(
        self, client: TestClient, monkeypatch
    ):
        def down(url, payload, timeout):
            raise ConnectionRefusedError("runtime down")

        monkeypatch.setattr(ma, "_http_post", down)

        headers = _login(client, "operator", "medha-operator-2026")
        task = _create_and_execute(client, headers, "Runtime Down Task")
        resp = _send(client, headers, task["task_id"], "Hello, are you there?")

        assert resp.status_code == 503
        assert resp.json()["detail"] == UNAVAILABLE_MESSAGE
        # audited as unavailable; no assistant message fabricated
        assert _has(task["task_id"], "LOCAL_MODEL_UNAVAILABLE")
        assert not _has(task["task_id"], "LOCAL_MODEL_INFERENCE")

    def test_infer_fails_closed_when_runtime_down(
        self, client: TestClient, monkeypatch
    ):
        def down(url, payload, timeout):
            raise OSError("no route to host")

        monkeypatch.setattr(ma, "_http_post", down)

        headers = _login(client, "operator", "medha-operator-2026")
        task = _create_and_execute(client, headers, "Infer Down Task")
        resp = client.post(
            "/api/models/infer",
            json={"task_id": task["task_id"], "prompt": "Analyze the trend"},
            headers=headers,
        )
        assert resp.status_code == 503
        assert resp.json()["detail"] == UNAVAILABLE_MESSAGE


# ── 6: sovereign routing ─────────────────────────────────────────────────


class TestSovereignRouting:
    def test_sovereign_never_selects_external_model(self):
        router = ModelRouter()
        decision = router.route(
            "Generate a complex multi-step design plan with reason",
            security_mode=SecurityMode.SOVEREIGN,
        )
        assert not decision.model_name.startswith(
            ("api-", "openai-", "claude-", "gpt-")
        )
        assert decision.local_execution is True
        assert decision.security_mode == "sovereign"

    def test_routing_decision_reports_category_and_local_status(self):
        router = ModelRouter()
        decision = router.route("List all pumps in the facility")
        assert decision.category == decision.complexity
        assert decision.local_execution is True
        high = router.route("Generate a complex multi-step design plan")
        assert high.category == "high"
        assert high.local_execution is False  # api tier reported honestly


# ── 7: allowed-model policy (existing tests also cover) ──────────────────


class TestAllowedModelPolicy:
    def test_disallowed_explicit_model_still_403(
        self, client: TestClient, capturing_transport
    ):
        headers = _login(client, "operator", "medha-operator-2026")
        resp = client.post(
            "/api/tasks",
            json={
                "title": "Allowed Model Task",
                "purpose": "Purpose for Allowed Model Task",
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        task = resp.json()
        # Security fields must be set in draft (immutable afterwards).
        patch = client.patch(
            f"/api/tasks/{task['task_id']}/security-fields",
            json={"allowed_models": ["local-qwen2"]},
            headers=headers,
        )
        assert patch.status_code == 200, patch.text
        for status_name in ("authorized", "executing"):
            r = client.patch(
                f"/api/tasks/{task['task_id']}/status",
                json={"new_status": status_name, "detail": f"to {status_name}"},
                headers=headers,
            )
            assert r.status_code == 200, r.text

        resp = _send(
            client, headers, task["task_id"],
            "Try the other model", model="api-claude",
        )
        assert resp.status_code == 403
        # blocked before any generation call
        assert capturing_transport == []


# ── 8–10: full structured context reaches the REAL adapter ───────────────


class TestContextReachesRealAdapter:
    def test_task_context_reaches_real_adapter(
        self, client: TestClient, capturing_transport
    ):
        headers = _login(client, "operator", "medha-operator-2026")
        task = _create_and_execute(
            client, headers, "P-204 Real Runtime Investigation"
        )
        resp = _send(
            client, headers, task["task_id"],
            "What is causing this vibration?",
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["execution_mode"] == "local"
        prompt = capturing_transport[-1]
        assert "TASK CONTEXT:" in prompt
        assert f"task_id: {task['task_id']}" in prompt
        assert "title: P-204 Real Runtime Investigation" in prompt
        assert "INTENT:" in prompt
        assert "RESOURCE PLAN:" in prompt
        # old echo template never fed to runtime either — prompt is structured
        assert "CURRENT USER MESSAGE:" in prompt

    def test_rag_evidence_reaches_model(
        self, client: TestClient, capturing_transport
    ):
        headers = _login(client, "operator", "medha-operator-2026")
        vector_store.reset()
        retrieval_service.ingest_document(
            "Pump bearing lubrication procedure requires ISO VG 68 oil.",
            "lube_procedure.txt",
            "internal",
        )
        task = _create_and_execute(
            client, headers, "Lube Task",
            allowed_sources=["lube_procedure.txt"],
        )
        resp = _send(
            client, headers, task["task_id"],
            "What oil grade does the procedure require for pump bearing lubrication?",
        )
        assert resp.status_code == 200, resp.text
        prompt = capturing_transport[-1]
        assert "INTERNAL EVIDENCE (authorized local RAG):" in prompt
        assert "lube_procedure.txt" in prompt
        assert "ISO VG 68" in prompt

    def test_public_research_reaches_model_only_when_permitted(
        self, client: TestClient, capturing_transport, research_provider
    ):
        headers = _login(client, "operator", "medha-operator-2026")

        # Permitted: standard + allow_internal + RAG miss → public research
        allowed_task = _create_and_execute(
            client, headers, "Permitted Research Task",
            allowed_sources=["never_fed_research.txt"],
            network_policy="allow_internal",
        )
        resp = _send(
            client, headers, allowed_task["task_id"],
            "What industry vibration limits apply to hydrolock cases?",
        )
        assert resp.status_code == 200, resp.text
        allowed_prompt = capturing_transport[-1]
        assert "PUBLIC RESEARCH" in allowed_prompt
        assert "bearing failure vibration indicators" in allowed_prompt
        assert len(research_provider.received_queries) == 1

        # Denied: default deny_external → blocked marker, no public results
        denied_task = _create_and_execute(
            client, headers, "Denied Research Task",
            allowed_sources=["never_fed_research2.txt"],
            network_policy="deny_external",
        )
        resp = _send(
            client, headers, denied_task["task_id"],
            "What industry vibration limits apply to hydrolock cases?",
        )
        assert resp.status_code == 200, resp.text
        denied_prompt = capturing_transport[-1]
        public_section = denied_prompt.split("PUBLIC RESEARCH", 1)[1]
        assert "(blocked:" in public_section
        assert "bearing failure vibration indicators" not in public_section
        assert len(research_provider.received_queries) == 1  # no second call


# ── 11: local execution audits ───────────────────────────────────────────


class TestLocalModelAudits:
    def test_local_model_audit_events(
        self, client: TestClient, capturing_transport
    ):
        headers = _login(client, "operator", "medha-operator-2026")
        task = _create_and_execute(client, headers, "Local Audit Task")
        resp = _send(client, headers, task["task_id"], "Check the local runtime")
        assert resp.status_code == 200, resp.text

        for evt in (
            "MODEL_ROUTED",
            "LOCAL_MODEL_REQUESTED",
            "LOCAL_MODEL_INFERENCE",
            "CHAT_RESPONSE_GENERATED",
        ):
            assert _has(task["task_id"], evt), f"missing audit {evt}"

        routed = next(
            e for e in _events(task["task_id"]) if e.event_type == "MODEL_ROUTED"
        )
        assert "local_execution=True" in routed.detail
        assert "selected=" in routed.detail
        assert "category=" in routed.detail


# ── Priority 2: chat local inference uses configured qwen2.5:3b-instruct ──


class TestChatUsesConfiguredModel:
    def test_chat_transport_receives_qwen_3b(
        self, client: TestClient, monkeypatch
    ):
        """Transport test: chat generate payload model == configured 3B model."""
        payloads: list[dict] = []

        def capture_post(url, payload, timeout):
            payloads.append(payload)
            return {"response": "3B local answer", "eval_count": 7}

        monkeypatch.setattr(ma, "_http_post", capture_post)
        headers = _login(client, "operator", "medha-operator-2026")
        task = _create_and_execute(client, headers, "Qwen 3B Chat Task")
        resp = _send(client, headers, task["task_id"], "Hello local model")
        assert resp.status_code == 200, resp.text
        assert payloads, "expected a generate call"
        assert payloads[-1]["model"] == "qwen2.5:3b-instruct"
        assert resp.json()["execution_mode"] == "local"
