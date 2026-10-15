"""Model Router service — orchestrates filtering, routing, inference, and audit."""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.task import SecurityMode
from app.services.audit_service import audit_service
from app.services.model_router.filters import input_filter, output_filter
from app.services.model_router.model_adapter import ModelAdapterFactory
from app.services.model_router.router import model_router
from app.services.security_mode import PolicyDecision, security_mode_engine


@dataclass
class InferenceResult:
    model_used: str
    response_text: str
    complexity: str
    routing_reason: str
    tokens_used: int
    latency_ms: float
    input_filtered: bool
    output_filtered: bool


class ModelRouterService:
    """End-to-end model routing with filtering and audit."""

    def __init__(self) -> None:
        self._router = model_router

    def infer(
        self,
        prompt: str,
        allowed_models: list[str] | None = None,
        requested_operation: str = "",
        max_tokens: int = 512,
        task_id: str = "",
        user_id: str = "",
        identity: str = "",
        role: str = "",
        security_mode: SecurityMode = SecurityMode.STANDARD,
    ) -> InferenceResult:
        input_result = input_filter.check(prompt)
        if not input_result.passed:
            audit_service.record(
                event_type="model_input_blocked",
                task_id=task_id,
                user_id=user_id,
                identity=identity,
                role=role,
                detail=input_result.blocked_reason,
            )
            raise ValueError(input_result.blocked_reason)

        clean_prompt = input_result.cleaned_text
        decision = self._router.route(
            clean_prompt, allowed_models, requested_operation, security_mode
        )

        # Check if security mode denied the model
        if decision.security_decision == "deny":
            audit_service.record(
                event_type="model_denied_by_security_mode",
                task_id=task_id,
                user_id=user_id,
                identity=identity,
                role=role,
                detail=decision.reason,
            )
            raise ValueError(decision.reason)

        adapter = ModelAdapterFactory.get(decision.model_name)
        model_response = adapter.generate(clean_prompt, max_tokens)

        output_result = output_filter.check(model_response.text)
        output_filtered = not output_result.passed
        response_text = output_result.cleaned_text if output_result.passed else "[OUTPUT BLOCKED]"

        audit_service.record(
            event_type="model_inference",
            task_id=task_id,
            user_id=user_id,
            identity=identity,
            role=role,
            detail=(
                f"model={decision.model_name} complexity={decision.complexity} "
                f"tokens={model_response.tokens_used} latency={model_response.latency_ms}ms"
            ),
        )

        return InferenceResult(
            model_used=decision.model_name,
            response_text=response_text,
            complexity=decision.complexity,
            routing_reason=decision.reason,
            tokens_used=model_response.tokens_used,
            latency_ms=model_response.latency_ms,
            input_filtered=input_result.cleaned_text != prompt,
            output_filtered=output_filtered,
        )


model_router_service = ModelRouterService()
