"""Reusable authentication, coarse-grained RBAC, and Task Passport dependencies."""

from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.schemas.auth import CurrentUser, Role
from app.schemas.task import TaskPassportRead
from app.services.user_service import user_service

bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication credentials are invalid or missing",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> CurrentUser:
    """Validate a bearer token and return the current user from DB."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        username = payload.get("sub")
        token_role = payload.get("role")
        token_uid = payload.get("uid")
    except jwt.PyJWTError as error:
        raise _unauthorized() from error

    if not isinstance(username, str) or not isinstance(token_role, str):
        raise _unauthorized()

    # Prefer uid (user_id) for lookup — authoritative and stable across username edits.
    # Fall back to username for tokens issued before user_id migration.
    user = None
    if isinstance(token_uid, str):
        user = user_service.get_by_user_id(db, token_uid)
    if user is None:
        user = user_service.get_by_username(db, username)
    if user is None or user.role != token_role:
        raise _unauthorized()

    return CurrentUser(
        user_id=user.user_id,
        username=user.username,
        role=token_role,
        preferred_security_mode=user_service.get_preferred_security_mode(db, user.user_id),
    )


def require_roles(*allowed_roles: Role) -> Callable[[CurrentUser], CurrentUser]:
    """Return a dependency that permits only the supplied coarse roles."""
    def role_guard(
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your role is not permitted to perform this action",
            )
        return current_user

    return role_guard


# Roles permitted read-only supervisory access to other users' tasks/traces.
# Access is audited; write paths stay gated by require_roles / Action Gate.
SUPERVISORY_VIEW_ROLES = {"manager", "admin", "senior_engineer", "monitor"}

# Worker roles that manager/admin (and other supervisory roles) may inspect.
# Tasks owned by peer/supervisor roles stay private.
SUPERVISED_WORKER_ROLES = {"operator", "junior_engineer", "monitor"}


def _role_value(role: Role | str) -> str:
    return role.value if isinstance(role, Role) else str(role)


def record_supervisory_view(
    current_user: CurrentUser,
    *,
    task_id: str,
    target_user_id: str,
    view: str,
) -> None:
    """Record MANAGER_VIEW_TASK / ADMIN_VIEW_TRACE / etc. in the existing audit log."""
    from app.services.audit_service import audit_service

    role = _role_value(current_user.role)
    event_type = f"{role.upper()}_VIEW_{view.upper()}"
    audit_service.record(
        event_type=event_type,
        task_id=task_id,
        user_id=current_user.user_id,
        identity=current_user.username,
        role=role,
        detail=f"actor_user_id={current_user.user_id}; target_user_id={target_user_id}; action={event_type}",
    )


def can_supervise(current_user: CurrentUser) -> bool:
    return _role_value(current_user.role) in SUPERVISORY_VIEW_ROLES


def _require_task_passport_from_path(
    task_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TaskPassportRead:
    """Internal: fetch passport and verify identity match (or supervisory view)."""
    from app.services.task_service import TaskPassportNotFoundError, passport_service

    try:
        passport = passport_service.get(db, task_id)
    except TaskPassportNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task passport not found",
        ) from exc

    if passport.user_id != current_user.user_id:
        if can_supervise(current_user) and passport.role in SUPERVISED_WORKER_ROLES:
            record_supervisory_view(
                current_user,
                task_id=task_id,
                target_user_id=passport.user_id,
                view="task",
            )
            return passport
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your identity does not match this Task Passport",
        )

    return passport


def require_task_passport(
    task_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TaskPassportRead:
    """FastAPI dependency that enforces passport existence and identity match.

    Use this in route signatures to gate access on a valid, matching Task Passport.
    """
    return _require_task_passport_from_path(task_id, current_user, db)
