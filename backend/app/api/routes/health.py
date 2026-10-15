from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["system"])


@router.get("/health")
def health_check() -> dict[str, str]:
    """Return the local backend's basic liveness status."""
    return {"status": "ok", "service": settings.app_name}


@router.get("/health/local-llm")
def local_llm_health() -> dict[str, str]:
    """Local open-weight LLM runtime health — no configuration internals."""
    from app.services.model_router.model_adapter import LocalSmallLLMAdapter

    health = LocalSmallLLMAdapter().health()
    return {
        "runtime": health.get("runtime", "ollama-compatible"),
        "model": health.get("model", settings.local_llm_model),
        "status": health.get("status", "UNAVAILABLE"),
        "reason": health.get("reason", ""),
    }
