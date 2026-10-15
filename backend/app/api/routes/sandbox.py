"""Sandbox API routes — controlled tool execution with network policy enforcement."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.schemas.auth import CurrentUser
from app.schemas.sandbox import (
    ExecuteRequest,
    ExecuteResponse,
    RollbackRequest,
    RollbackResponse,
)
from app.services.action_gate import (
    ActionCategory,
    ActionGateError,
    AuthorizationContext,
    action_gate,
)
from app.services.agent.tool_registry import tool_registry
from app.services.sandbox.sandbox import sandbox_service
from app.services.task_service import TaskPassportNotFoundError, passport_service

router = APIRouter(prefix="/sandbox", tags=["sandbox"])


@router.post("/execute", response_model=ExecuteResponse)
def execute_tool(
    payload: ExecuteRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ExecuteResponse:
    """Execute a tool in the sandbox, gated by the Task Passport."""
    try:
        passport = passport_service.get(db, payload.task_id)
    except TaskPassportNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task passport not found",
        )

    # Action Gate: full authorization check
    try:
        action_gate.authorize_action(
            AuthorizationContext(
                passport=passport,
                current_user=current_user,
                action_category=ActionCategory.EXECUTE,
                tool_name=payload.tool_name,
            )
        )
    except ActionGateError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    input_data = dict(payload.input_data or {})
    if payload.code is not None:
        input_data["code"] = payload.code

    try:
        result = sandbox_service.execute(
            tool_name=payload.tool_name,
            action=payload.action,
            input_data=input_data,
            network_policy=passport.network_policy.value,
            task_id=passport.task_id,
            user_id=current_user.user_id,
            identity=current_user.username,
            role=current_user.role.value,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    return ExecuteResponse(
        execution_id=result.execution_id,
        tool_name=result.tool_name,
        status=result.status.value,
        output=result.output,
        error=result.error,
        cpu_ms=result.cpu_ms,
        memory_mb=result.memory_mb,
        network_calls=result.network_calls,
        sandbox=result.sandbox,
        network=result.network,
    )


@router.post("/rollback", response_model=RollbackResponse)
def rollback_execution(
    payload: RollbackRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> RollbackResponse:
    """Rollback a completed execution."""
    try:
        result = sandbox_service.rollback(
            payload.execution_id,
            task_id=payload.task_id,
            user_id=current_user.user_id,
            identity=current_user.username,
            role=current_user.role.value,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return RollbackResponse(
        execution_id=result.execution_id,
        tool_name=result.tool_name,
        status=result.status.value,
        output=result.output,
    )
