"""Environment / sovereignty status — truthful runtime visibility.

Public, high-level capability status only. Never returns secrets, credentials,
filesystem paths, task data, or configuration internals (URLs, DB, JWT).
"""

from __future__ import annotations

import importlib.util

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.task import SecurityMode
from app.services.security_mode import POLICIES, PolicyDecision

router = APIRouter(prefix="/environment", tags=["environment"])

_MODE_LABEL = {
    PolicyDecision.ALLOW: "ALLOWED",
    PolicyDecision.RESTRICT: "RESTRICTED",
    PolicyDecision.DENY: "DENIED",
}


def _module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


@router.get("/status")
def environment_status() -> dict:
    """Return live, truthful MEDHA environment status.

    Local AI is probed against the real Ollama-compatible runtime.
    Capabilities that cannot be live-probed cheaply are labeled
    CONFIGURED/LOCAL rather than AVAILABLE.
    """
    from app.services.model_router.model_adapter import LocalSmallLLMAdapter

    # Real local LLM health (network probe of local runtime only).
    try:
        llm = LocalSmallLLMAdapter().health()
    except Exception:
        llm = {
            "runtime": "ollama-compatible",
            "model": settings.local_llm_model,
            "status": "UNAVAILABLE",
            "reason": "health check failed",
        }

    ocr_ok = _module_available("rapidocr_onnxruntime")
    sandbox_ok = _module_available("app.services.sandbox.code_runner")
    rag_ok = _module_available("app.services.rag.vector_store")

    mode_policies = {
        mode.value: {
            "external_network": _MODE_LABEL[policy.external_network],
            "external_models": _MODE_LABEL[policy.external_models],
            "local_model": policy.local_model,
        }
        for mode, policy in POLICIES.items()
        if isinstance(mode, SecurityMode)
    }

    return {
        "execution": "LOCAL",
        "model": {
            "name": llm.get("model", settings.local_llm_model),
            "status": llm.get("status", "UNKNOWN"),
            "runtime": llm.get("runtime", "ollama-compatible"),
            "reason": llm.get("reason", ""),
        },
        "network": {
            "policy": "POLICY_CONTROLLED",
            "external_ai": "NOT_USED",
            "note": (
                "Connectivity is governed by security-mode policy "
                "(standard/secure/sovereign). This is policy control, "
                "not a physical air gap."
            ),
            "modes": mode_policies,
        },
        "external_ai": {
            "status": "NOT_USED",
            "cloud_llm_fallback": "NONE",
            "note": (
                "MEDHA performs real inference only on the local model path. "
                "External adapters are labeled simulations for policy demos "
                "and do not call live cloud LLM APIs."
            ),
        },
        "rag": {
            "execution": "LOCAL",
            "status": "LOCAL" if rag_ok else "UNAVAILABLE",
        },
        "ocr": {
            "execution": "LOCAL",
            "status": "CONFIGURED" if ocr_ok else "UNAVAILABLE",
        },
        "sandbox": {
            "execution": "LOCAL",
            "status": "CONFIGURED" if sandbox_ok else "UNAVAILABLE",
            "network": "DISABLED",
        },
        "security_mode": {
            "available": [m.value for m in SecurityMode],
            "scope": "user/task-scoped policy",
        },
    }
