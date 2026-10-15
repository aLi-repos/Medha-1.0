from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.schemas.auth import (
    AUTHORIZED_ORG_RECORDS,
    CurrentUser,
    LoginRequest,
    PasswordUpdate,
    RegisterRequest,
    Role,
    TokenResponse,
    UsernameUpdate,
)
from app.services.auth_service import auth_service
from app.services.user_service import user_service
from app.services.audit_service import audit_service
from app.services.security_mode import security_mode_engine

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Authenticate a user and issue a short-lived bearer token."""
    token = auth_service.login(
        db, payload.username, payload.password, user_id=payload.user_id
    )
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Register a new user and return a bearer token.

    When user_id is supplied it must match an authorized organization
    record, and the selected role must match that record — wrong UID/role
    combinations are rejected. Without user_id, registration keeps the
    legacy server-assigned OPERATOR behavior (generated user_id).
    """
    role = Role.OPERATOR
    if payload.user_id is not None:
        org_record = AUTHORIZED_ORG_RECORDS.get(payload.user_id)
        if org_record is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User ID is not an authorized organization record",
            )
        _, expected_role = org_record
        if payload.role != expected_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User ID and Role do not match the authorized organization record",
            )
        role = expected_role
        if user_service.get_by_user_id(db, payload.user_id) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User ID already registered",
            )

    user = user_service.register(
        db,
        payload.username,
        payload.password,
        role,
        user_id=payload.user_id,
    )

    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_expiration_minutes
    )
    token = jwt.encode(
        {
            "sub": user.username,
            "uid": user.user_id,
            "role": user.role,
            "iat": datetime.now(timezone.utc),
            "exp": expires_at,
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=CurrentUser)
def get_me(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    """Return the identity, user_id, and role represented by the bearer token."""
    return current_user


@router.patch("/username", response_model=CurrentUser)
def update_username(
    payload: UsernameUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CurrentUser:
    """Edit the current user's username. Validates uniqueness and format.

    The user_id remains stable — only the username changes.
    """
    try:
        user = user_service.edit_username(
            db,
            user_id=current_user.user_id,
            new_username=payload.username,
        )
        return CurrentUser(
            user_id=user.user_id,
            username=user.username,
            role=user.role,
            preferred_security_mode=user_service.get_preferred_security_mode(db, user.user_id),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.patch("/password", response_model=CurrentUser)
def update_password(
    payload: PasswordUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CurrentUser:
    """Change the current user's password.

    user_id and role are never modified by a password change.
    """
    try:
        user = user_service.change_password(
            db,
            user_id=current_user.user_id,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return CurrentUser(
        user_id=user.user_id,
        username=user.username,
        role=user.role,
        preferred_security_mode=user_service.get_preferred_security_mode(db, user.user_id),
    )


@router.get("/security-mode")
def get_security_mode(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Get the current user's effective security mode and its policy.

    The effective mode is floored by the organization's role → security-mode
    mapping (server-side; never trusted from the client).
    """
    from app.core.config import security_mode_for_role

    mode = user_service.get_preferred_security_mode(db, current_user.user_id)
    role_floor = security_mode_for_role(current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role))
    policy = security_mode_engine.get_policy(mode)
    display = security_mode_engine.get_mode_display(mode)
    return {
        "security_mode": mode,
        "role_floor": role_floor,
        "policy": {
            "external_network": policy.external_network.value,
            "external_models": policy.external_models.value,
            "local_model": policy.local_model,
            "rag_policy": policy.rag_policy,
            "tool_policy": policy.tool_policy,
            "execution_policy": policy.execution_policy,
            "human_approval": policy.human_approval,
            "audit_level": policy.audit_level,
        },
        "display": display,
    }


class SecurityModeUpdate(BaseModel):
    security_mode: str


@router.patch("/security-mode")
def set_security_mode(
    payload: SecurityModeUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Set the current user's preferred security mode.

    This is the user's global capability selector. The EFFECTIVE mode
    for any operation is max(user_selected, task_required), and the
    user cannot select below the minimum required by their role.
    """
    if payload.security_mode not in ("standard", "secure", "sovereign"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="security_mode must be standard, secure, or sovereign",
        )

    old_mode = user_service.get_preferred_security_mode(db, current_user.user_id)
    try:
        new_mode = user_service.set_preferred_security_mode(
            db, current_user.user_id, payload.security_mode
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # Record audit event
    audit_service.record(
        event_type="security_mode_changed",
        task_id="",
        user_id=current_user.user_id,
        identity=current_user.username,
        role=current_user.role,
        security_mode=new_mode,
        detail=f"User security mode changed: {old_mode} -> {new_mode}",
    )

    policy = security_mode_engine.get_policy(new_mode)
    display = security_mode_engine.get_mode_display(new_mode)
    return {
        "security_mode": new_mode,
        "previous_mode": old_mode,
        "policy": {
            "external_network": policy.external_network.value,
            "external_models": policy.external_models.value,
            "local_model": policy.local_model,
            "rag_policy": policy.rag_policy,
            "tool_policy": policy.tool_policy,
            "execution_policy": policy.execution_policy,
            "human_approval": policy.human_approval,
            "audit_level": policy.audit_level,
        },
        "display": display,
    }
