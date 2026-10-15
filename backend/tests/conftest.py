import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

# Must precede application imports because the application rejects missing secrets.
os.environ.setdefault("MEDHA_JWT_SECRET", "test-only-jwt-secret-not-for-production")
os.environ.setdefault("MEDHA_ENV", "test")
# Use an in-memory SQLite database for tests.
os.environ.setdefault("MEDHA_DATABASE_URL", "sqlite://")

from app.core.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.audit import AuditEventRow  # noqa: E402 — ensure audit table is registered
from app.services.audit_service import audit_service  # noqa: E402
from app.services.rag.vector_store import vector_store  # noqa: E402
from app.services.agent.service import agent_service  # noqa: E402
from app.services.sandbox.sandbox import sandbox_service  # noqa: E402


@pytest.fixture(autouse=True)
def _setup_database() -> None:
    """Create tables before each test and drop them afterwards."""
    Base.metadata.create_all(bind=engine)
    vector_store.reset()
    agent_service.reset()
    sandbox_service.reset()
    yield
    audit_service.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _mock_local_llm_transport(monkeypatch) -> None:
    """Mock the HTTP transport to the local LLM runtime.

    This stubs ONLY the HTTP layer (_http_post/_http_get); the real
    LocalLLMClient + LocalSmallLLMAdapter code runs against it. It does
    NOT replace the production adapter itself.
    """
    from app.core.config import settings as _settings
    from app.services.model_router import model_adapter as _ma

    def fake_post(url: str, payload: dict, timeout: int) -> dict:
        if url.endswith("/api/generate"):
            prompt = str(payload.get("prompt", ""))
            return {
                "model": payload.get("model"),
                "response": f"Local response for: {prompt[:80]}",
                "eval_count": max(1, len(prompt.split()) // 2),
            }
        raise AssertionError(f"unexpected transport POST {url}")

    def fake_get(url: str, timeout: int) -> dict:
        if url.endswith("/api/tags"):
            return {"models": [{"name": _settings.local_llm_model}]}
        raise AssertionError(f"unexpected transport GET {url}")

    monkeypatch.setattr(_ma, "_http_post", fake_post)
    monkeypatch.setattr(_ma, "_http_get", fake_get)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    return response.json()["access_token"]


@pytest.fixture
def operator_token(client: TestClient) -> str:
    return _login(client, "operator", "medha-operator-2026")


@pytest.fixture
def engineer_token(client: TestClient) -> str:
    return _login(client, "engineer", "medha-engineer-2026")


@pytest.fixture
def reviewer_token(client: TestClient) -> str:
    return _login(client, "reviewer", "medha-reviewer-2026")


@pytest.fixture
def admin_token(client: TestClient) -> str:
    return _login(client, "admin", "medha-admin-2026")


@pytest.fixture
def auth_headers(operator_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {operator_token}"}


@pytest.fixture
def engineer_headers(engineer_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {engineer_token}"}


@pytest.fixture
def reviewer_headers(reviewer_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {reviewer_token}"}


@pytest.fixture
def admin_headers(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}
