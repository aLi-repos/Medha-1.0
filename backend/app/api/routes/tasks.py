"""Task Passport API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_user,
    get_db,
    require_roles,
    require_task_passport,
)
from app.schemas.auth import CurrentUser, Role
from app.schemas.task import (
    TaskCreate,
    TaskPassportRead,
    TaskStatusUpdate,
)
from app.services.task_service import (
    TaskPassportApprovalRequiredError,
    TaskPassportError,
    TaskPassportIdentityError,
    TaskPassportImmutableFieldError,
    TaskPassportInvalidTransitionError,
    TaskPassportNotFoundError,
    passport_service,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])

# Roles allowed to create tasks and drive their own lifecycle transitions.
# Supervision decisions (approve/reject/verify) are manager/admin only and
# live on the supervision routes.
TASK_WORKER_ROLES = (
    Role.OPERATOR,
    Role.ENGINEER,
    Role.JUNIOR_ENGINEER,
    Role.MONITOR,
    Role.ADMIN,
)


@router.get("", response_model=list[TaskPassportRead])
def list_tasks(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    security_mode: str | None = None,
) -> list[TaskPassportRead]:
    """List Task Passports owned by the current user.

    If security_mode is provided, only return tasks in that security domain.
    This enforces logical separation: Standard mode never sees Secure tasks.
    """
    from app.models.task import TaskPassportRow
    from app.services.task_service import _row_to_passport

    query = (
        db.query(TaskPassportRow)
        .filter(
            TaskPassportRow.user_id == current_user.user_id,
            TaskPassportRow.deleted_at.is_(None),
        )
    )

    if security_mode and security_mode in ("standard", "secure", "sovereign"):
        query = query.filter(TaskPassportRow.security_mode == security_mode)

    rows = query.order_by(TaskPassportRow.created_at.desc()).all()
    return [_row_to_passport(r) for r in rows]


@router.post("", response_model=TaskPassportRead, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    current_user: Annotated[CurrentUser, Depends(require_roles(*TASK_WORKER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> TaskPassportRead:
    """Create a new Task Passport in draft status.

    If the payload does not specify a security_mode (or uses the default),
    the user's preferred security mode is used as the baseline.
    The effective mode is max(user_preferred, sensitivity_required).
    """
    from app.schemas.task import SecurityMode

    # Use user's preferred mode as baseline if not explicitly set
    if payload.security_mode == SecurityMode.STANDARD:
        preferred = current_user.preferred_security_mode
        if preferred and preferred != "standard":
            payload = payload.model_copy(update={"security_mode": SecurityMode(preferred)})

    return passport_service.create(
        db,
        payload=payload,
        user_id=current_user.user_id,
        identity=current_user.username,
        role=current_user.role.value,
    )


@router.get("/{task_id}", response_model=TaskPassportRead)
def get_task(
    task_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    passport: TaskPassportRead = Depends(require_task_passport),
) -> TaskPassportRead:
    """Retrieve a Task Passport by ID.

    The dependency verifies the task exists and the user's identity
    matches the passport identity.
    """
    return passport


@router.patch("/{task_id}/status", response_model=TaskPassportRead)
def transition_task_status(
    task_id: str,
    payload: TaskStatusUpdate,
    current_user: Annotated[CurrentUser, Depends(require_roles(*TASK_WORKER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    _passport: TaskPassportRead = Depends(require_task_passport),
) -> TaskPassportRead:
    """Transition a Task Passport to a new status.

    Supervisory roles may read via require_task_passport, but only the
    passport owner may transition status. When approval is required, the
    service enforces manager/admin approval before authorized/executing.
    """
    if _passport.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your identity does not match this Task Passport",
        )
    try:
        return passport_service.transition_status(
            db,
            task_id=task_id,
            update=payload,
            user_id=current_user.user_id,
            identity=current_user.username,
            role=current_user.role.value,
        )
    except TaskPassportApprovalRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except TaskPassportInvalidTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except TaskPassportError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.patch("/{task_id}/security-fields", response_model=TaskPassportRead)
def update_security_fields(
    task_id: str,
    current_user: Annotated[CurrentUser, Depends(require_roles(Role.OPERATOR, Role.ENGINEER, Role.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    _passport: TaskPassportRead = Depends(require_task_passport),
    allowed_sources: list[str] | None = None,
    allowed_tools: list[str] | None = None,
    allowed_models: list[str] | None = None,
) -> TaskPassportRead:
    """Update security-critical fields on a draft Task Passport (owner only)."""
    if _passport.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your identity does not match this Task Passport",
        )
    try:
        return passport_service.update_security_fields(
            db,
            task_id=task_id,
            user_id=current_user.user_id,
            identity=current_user.username,
            role=current_user.role.value,
            allowed_sources=allowed_sources,
            allowed_tools=allowed_tools,
            allowed_models=allowed_models,
        )
    except TaskPassportImmutableFieldError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except TaskPassportError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Soft-delete a Task Passport. Only the owner or admin can delete."""
    try:
        passport = passport_service.get(db, task_id)
    except TaskPassportNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task passport not found",
        )

    if passport.user_id != current_user.user_id and current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to delete this Task Passport",
        )

    try:
        passport_service.soft_delete(
            db,
            task_id=task_id,
            user_id=current_user.user_id,
            identity=current_user.username,
            role=current_user.role.value,
        )
    except TaskPassportError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
