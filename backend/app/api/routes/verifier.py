"""Verifier and Audit Trail API routes — output verification and structured audit inspection."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import (
    SUPERVISED_WORKER_ROLES,
    can_supervise,
    get_current_user,
    get_db,
    record_supervisory_view,
)
from app.schemas.auth import CurrentUser
from app.schemas.verifier import (
    AuditEventResponse,
    AuditTrailResponse,
    CheckResultResponse,
    TaskWithAuditSummary,
    TasksAuditSummaryResponse,
    VerifyRequest,
    VerifyResponse,
)
from app.services.action_gate import (
    ActionCategory,
    ActionGateError,
    AuthorizationContext,
    action_gate,
)
from app.services.audit_service import audit_service
from app.services.task_service import TaskPassportNotFoundError, passport_service
from app.services.verifier.verifier import output_verifier

router = APIRouter(prefix="/verifier", tags=["verifier"])


@router.post("/verify", response_model=VerifyResponse)
def verify_output(
    payload: VerifyRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> VerifyResponse:
    """Verify AI output against safety, hallucination, and compliance criteria."""
    try:
        passport = passport_service.get(db, payload.task_id)
    except TaskPassportNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task passport not found",
        )

    # Action Gate: authorize verification
    try:
        action_gate.authorize_action(
            AuthorizationContext(
                passport=passport,
                current_user=current_user,
                action_category=ActionCategory.READ,
            )
        )
    except ActionGateError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    result = output_verifier.verify(
        output_text=payload.output_text,
        allowed_sources=payload.allowed_sources or passport.allowed_sources,
        task_id=passport.task_id,
        user_id=current_user.user_id,
        identity=current_user.username,
        role=current_user.role.value,
    )

    return VerifyResponse(
        overall=result.overall.value,
        checks=[CheckResultResponse(**c.__dict__) for c in result.checks],
        summary=result.summary,
    )


@router.get("/audit/{task_id}", response_model=AuditTrailResponse)
def get_audit_trail(
    task_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AuditTrailResponse:
    """Retrieve the full audit trail for a task.

    The task's security_mode is included in each event.
    """
    try:
        passport = passport_service.get(db, task_id)
    except TaskPassportNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task passport not found",
        )

    if passport.user_id != current_user.user_id:
        if can_supervise(current_user) and passport.role in SUPERVISED_WORKER_ROLES:
            record_supervisory_view(
                current_user,
                task_id=task_id,
                target_user_id=passport.user_id,
                view="trace",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your identity does not match this Task Passport",
            )

    events = audit_service.get_events_for_task(task_id)
    return AuditTrailResponse(
        task_id=task_id,
        events=[
            AuditEventResponse(
                event_id=e.event_id,
                timestamp=e.timestamp.isoformat(),
                event_type=e.event_type,
                task_id=e.task_id,
                user_id=e.user_id,
                identity=e.identity,
                role=e.role,
                security_mode=getattr(e, "security_mode", "standard") or "standard",
                previous_status=e.previous_status,
                new_status=e.new_status,
                detail=e.detail,
            )
            for e in events
        ],
        total_events=len(events),
    )


@router.get("/audit", response_model=TasksAuditSummaryResponse)
def get_tasks_with_audit_summary(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    security_mode: str | None = None,
) -> TasksAuditSummaryResponse:
    """Auto-load tasks owned by the current user with their latest audit event.

    If security_mode is provided, only return tasks/events in that security domain.
    This enforces logical separation: Standard Audit never shows Secure records.
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

    tasks_with_audit = []
    for row in rows:
        events = audit_service.get_events_for_task(row.task_id)
        # Filter events by security_mode if specified
        if security_mode and security_mode in ("standard", "secure", "sovereign"):
            events = [e for e in events if getattr(e, "security_mode", "standard") == security_mode]
        latest_event = events[-1] if events else None
        tasks_with_audit.append(
            TaskWithAuditSummary(
                task_id=row.task_id,
                title=row.title,
                status=row.status,
                sensitivity=row.sensitivity,
                security_mode=getattr(row, "security_mode", "standard") or "standard",
                created_at=row.created_at.isoformat(),
                updated_at=row.updated_at.isoformat(),
                latest_event_type=latest_event.event_type if latest_event else None,
                latest_event_timestamp=latest_event.timestamp.isoformat() if latest_event else None,
                latest_event_detail=latest_event.detail if latest_event else None,
                total_events=len(events),
            )
        )

    return TasksAuditSummaryResponse(tasks=tasks_with_audit, total=len(tasks_with_audit))
