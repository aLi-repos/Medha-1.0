"""P9 — Live Sovereignty / Environment Monitor.

Verifies GET /api/environment/status is truthful, policy-honest, and free
of secrets or over-claims. No scanning; focused on this endpoint only.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import settings
from app.services.model_router import model_adapter as ma

ENDPOINT = "/api/environment/status"

FORBIDDEN_TERMS = [
    "air-gapped",
    "air gapped",
    "fully secure",
    "zero network",
    "physically isolated",
]

SECRET_MARKERS = [
    settings.jwt_secret,
    settings.local_llm_base_url,
    "MEDHA_JWT_SECRET",
    settings.database_url,
]


def _body_text(body: dict) -> str:
    return str(body).lower()


class TestEndpointContract:
    def test_status_code_and_shape(self, client: TestClient):
        resp = client.get(ENDPOINT)
        assert resp.status_code == 200
        body = resp.json()
        for key in (
            "execution",
            "model",
            "network",
            "external_ai",
            "rag",
            "ocr",
            "sandbox",
            "security_mode",
        ):
            assert key in body, f"missing key: {key}"
        assert body["model"] and {"name", "status", "runtime", "reason"} <= set(body["model"])
        assert body["network"]["policy"] == "POLICY_CONTROLLED"
        assert body["execution"] == "LOCAL"

    def test_public_endpoint_no_auth_needed(self, client: TestClient):
        # Intended policy: safe, high-level status is public like /health.
        resp = client.get(ENDPOINT)
        assert resp.status_code == 200

    def test_no_audit_events_on_repeated_polls(
        self, client: TestClient, auth_headers: dict
    ):
        from app.services.audit_service import audit_service

        for _ in range(5):
            assert client.get(ENDPOINT, headers=auth_headers).status_code == 200
        assert audit_service.get_all_events() == []


class TestTruthfulModelStatus:
    def test_available_when_runtime_reports_model(
        self, client: TestClient
    ):
        # conftest fake_get serves /api/tags with the configured model.
        body = client.get(ENDPOINT).json()
        assert body["model"]["status"] == "AVAILABLE"
        assert body["model"]["name"] == settings.local_llm_model
        assert body["model"]["runtime"] == "ollama-compatible"

    def test_unavailable_when_runtime_down(self, client: TestClient, monkeypatch):
        def down(url, timeout):
            raise ConnectionRefusedError("no server")

        monkeypatch.setattr(ma, "_http_get", down)
        body = client.get(ENDPOINT).json()
        assert body["model"]["status"] == "UNAVAILABLE"
        assert "reason" in body["model"] and body["model"]["reason"]

    def test_unavailable_when_model_not_installed(
        self, client: TestClient, monkeypatch
    ):
        monkeypatch.setattr(
            ma,
            "_http_get",
            lambda url, timeout: {"models": [{"name": "other-model:latest"}]},
        )
        body = client.get(ENDPOINT).json()
        assert body["model"]["status"] == "UNAVAILABLE"
        assert "not installed" in body["model"]["reason"]

    def test_status_is_not_config_only(self, client: TestClient):
        # Status must come from the live health probe (mocked transport in
        # tests still exercises the real LocalSmallLLMAdapter.health path),
        # not merely from settings.
        body = client.get(ENDPOINT).json()
        assert body["model"]["status"] in {"AVAILABLE", "UNAVAILABLE"}
        assert body["model"]["reason"]


class TestHonestyAndTerminology:
    def test_no_forbidden_security_claims(self, client: TestClient):
        text = _body_text(client.get(ENDPOINT).json())
        for term in FORBIDDEN_TERMS:
            assert term not in text, f"forbidden claim present: {term}"

    def test_external_ai_not_used_not_overclaimed(self, client: TestClient):
        body = client.get(ENDPOINT).json()
        assert body["external_ai"]["status"] == "NOT_USED"
        assert body["external_ai"]["cloud_llm_fallback"] == "NONE"
        assert body["network"]["external_ai"] == "NOT_USED"

    def test_network_is_policy_controlled_language(self, client: TestClient):
        body = client.get(ENDPOINT).json()
        assert body["network"]["policy"] == "POLICY_CONTROLLED"
        note = body["network"]["note"].lower()
        assert "not a physical air gap" in note

    def test_mode_policies_reported_as_policy(self, client: TestClient):
        modes = client.get(ENDPOINT).json()["network"]["modes"]
        assert modes["standard"]["external_network"] == "ALLOWED"
        assert modes["secure"]["external_network"] == "RESTRICTED"
        assert modes["sovereign"]["external_network"] == "DENIED"
        assert modes["sovereign"]["external_models"] == "DENIED"
        assert modes["sovereign"]["local_model"] == "required"


class TestCapabilityLabels:
    def test_rag_execution_local(self, client: TestClient):
        body = client.get(ENDPOINT).json()
        assert body["rag"]["execution"] == "LOCAL"
        assert body["rag"]["status"] in {"LOCAL", "UNAVAILABLE"}

    def test_ocr_configured_or_unavailable_never_fake_available(
        self, client: TestClient
    ):
        status = client.get(ENDPOINT).json()["ocr"]["status"]
        # CONFIGURED (module present) or UNAVAILABLE — not a live probe,
        # so it must not claim AVAILABLE.
        assert status in {"CONFIGURED", "UNAVAILABLE"}
        assert client.get(ENDPOINT).json()["ocr"]["execution"] == "LOCAL"

    def test_sandbox_configured_with_network_disabled(self, client: TestClient):
        body = client.get(ENDPOINT).json()
        assert body["sandbox"]["status"] in {"CONFIGURED", "UNAVAILABLE"}
        assert body["sandbox"]["network"] == "DISABLED"
        assert body["sandbox"]["execution"] == "LOCAL"

    def test_security_mode_scope(self, client: TestClient):
        body = client.get(ENDPOINT).json()
        assert set(body["security_mode"]["available"]) == {
            "standard",
            "secure",
            "sovereign",
        }
        assert "task" in body["security_mode"]["scope"]


class TestNoSecrets:
    def test_no_secrets_or_config_internals(self, client: TestClient):
        text = _body_text(client.get(ENDPOINT).json())
        for marker in SECRET_MARKERS:
            assert marker.lower() not in text, f"secret/config leaked: {marker!r}"
        for banned in ("base_url", "password", "secret", "token", "11434"):
            assert banned not in text, f"config internal leaked: {banned}"
