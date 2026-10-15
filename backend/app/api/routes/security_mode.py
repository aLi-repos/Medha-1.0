"""Security Mode API — server-side authoritative security mode management."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.schemas.auth import CurrentUser
from app.schemas.task import (
    SecurityMode,
    TaskPassportRead,
)
from app.services.task_service import (
    TaskPassportIdentityError,
    TaskPassportImmutableFieldError,
    TaskPassportNotFoundError,
    passport_service,
)
from app.services.security_mode import security_mode_engine

router = APIRouter(prefix="/security-mode", tags=["security-mode"])


class SecurityModeUpdate(BaseModel):
    task_id: str = Field(min_length=1, max_length=36)
    security_mode: SecurityMode


@router.get("/status/{task_id}")
async def get_security_status(
    task_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Get the security mode status for a task."""
    try:
        passport = passport_service.get(db, task_id)
    except TaskPassportNotFoundError:
        raise HTTPException(status_code=404, detail="Task passport not found")

    if passport.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Identity mismatch")

    return security_mode_engine.get_status_panel_data(passport)


@router.post("/set")
async def set_security_mode(
    payload: SecurityModeUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Set the security mode for a task. Users can only increase protection.

    Server-side authoritative: the backend enforces policy requirements
    and prevents downgrade below the sensitivity-required minimum.
    """
    try:
        result = passport_service.change_security_mode(
            db,
            task_id=payload.task_id,
            new_mode=payload.security_mode,
            user_id=current_user.user_id,
            identity=current_user.username,
            role=current_user.role.value,
        )
        return {
            "task_id": result.task_id,
            "security_mode": result.security_mode.value,
            "security_policy_version": result.security_policy_version,
            "status_panel": security_mode_engine.get_status_panel_data(result),
        }
    except TaskPassportImmutableFieldError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except TaskPassportIdentityError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except TaskPassportNotFoundError:
        raise HTTPException(status_code=404, detail="Task passport not found")


@router.get("/policy/{mode}")
async def get_security_policy(mode: SecurityMode):
    """Get the effective security policy for a given mode."""
    policy = security_mode_engine.get_policy(mode)
    display = security_mode_engine.get_mode_display(mode)
    return {
        "mode": mode.value,
        "display": display,
        "external_network": policy.external_network.value,
        "external_models": policy.external_models.value,
        "local_model": policy.local_model,
        "rag_policy": policy.rag_policy,
        "tool_policy": policy.tool_policy,
        "execution_policy": policy.execution_policy,
        "human_approval": policy.human_approval,
        "audit_level": policy.audit_level,
        "description": display["description"],
    }
