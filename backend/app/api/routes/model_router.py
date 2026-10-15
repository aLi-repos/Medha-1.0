"""Model Router API routes — complexity-based model inference with Task Passport gating."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.schemas.auth import CurrentUser
from app.schemas.model_router import InferenceRequest, InferenceResponse, ModelsResponse
from app.services.action_gate import (
    ActionCategory,
    ActionGateError,
    AuthorizationContext,
    action_gate,
)
from app.services.model_router.model_adapter import (
    LocalModelUnavailableError,
    ModelAdapterFactory,
    UNAVAILABLE_MESSAGE,
)
from app.services.model_router.service import model_router_service
from app.services.task_service import TaskPassportNotFoundError, passport_service

router = APIRouter(prefix="/models", tags=["models"])


@router.post("/infer", response_model=InferenceResponse)
def infer(
    payload: InferenceRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> InferenceResponse:
    """Run model inference gated by the Task Passport."""
    try:
        passport = passport_service.get(db, payload.task_id)
    except TaskPassportNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task passport not found",
        )

    # Action Gate: authorize model inference
    try:
        action_gate.authorize_action(
            AuthorizationContext(
                passport=passport,
                current_user=current_user,
                action_category=ActionCategory.COMPUTE,
            )
        )
    except ActionGateError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    try:
        result = model_router_service.infer(
            prompt=payload.prompt,
            allowed_models=passport.allowed_models,
            requested_operation=passport.requested_operation,
            max_tokens=payload.max_tokens,
            task_id=passport.task_id,
            user_id=current_user.user_id,
            identity=current_user.username,
            role=current_user.role.value,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except LocalModelUnavailableError:
        # Fail closed: never fabricate a response or fall back to a cloud model.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=UNAVAILABLE_MESSAGE,
        )

    return InferenceResponse(
        model_used=result.model_used,
        response_text=result.response_text,
        complexity=result.complexity,
        routing_reason=result.routing_reason,
        tokens_used=result.tokens_used,
        latency_ms=result.latency_ms,
        input_filtered=result.input_filtered,
        output_filtered=result.output_filtered,
    )


@router.get("/available", response_model=ModelsResponse)
def list_models(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ModelsResponse:
    """List available model adapters."""
    return ModelsResponse(available_models=ModelAdapterFactory.available())
