"""Supervision & Verification API — manager/admin worker oversight + human verification.

Server-side enforced:
- Only manager/admin may access (require_roles), regardless of the frontend.
- Only tasks owned by supervised worker roles (operator, junior_engineer,
  monitor) are visible — peer/supervisor tasks stay private.
- Self-approval, cross-worker access, replays and modified-plan approvals
  are rejected by the human verification service.
- Every supervisory action is recorded in the existing audit log.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import (
    SUPERVISED_WORKER_ROLES,
    get_current_user,
    get_db,
    record_supervisory_view,
    require_roles,
)
from app.schemas.auth import CurrentUser, Role
from app.schemas.supervision import (
    DecisionRequest,
    PlanStepSupervision,
    PlanSupervision,
    StrictDecisionRequest,
    SupervisedTaskItem,
    SupervisedTaskListResponse,
    SupervisionDetailResponse,
    VerificationRecordResponse,
)
from app.schemas.verifier import AuditEventResponse
from app.models.task import TaskPassportRow
from app.services.audit_service import audit_service
from app.services.human_verification import (
    HumanVerificationConflict,
    HumanVerificationDenied,
    HumanVerificationReasonRequired,
    human_verification_service,
    requires_human_verification,
)
from app.services.task_service import TaskPassportNotFoundError, passport_service

router = APIRouter(prefix="/supervision", tags=["supervision"])

# Manager/Admin only — workers and monitor never reach these endpoints.
SupervisorOnly = require_roles(Role.MANAGER, Role.ADMIN)


def _verification_status(passport_status: str, approval_required: bool) -> str:
    if not approval_required:
        return "not_required"
    return {
        "draft": "not_submitted",
        "pending_approval": "waiting_verification",
        "authorized": "approved",
        "executing": "approved",
        "failed": "approved",
        "rejected": "rejected",
        "completed": "waiting_completion_verification",
        "pending_verification": "waiting_completion_verification",
        "verified": "verified",
        "denied": "not_required",
    }.get(passport_status, "unknown")


def _execution_status(passport_status: str) -> str:
    return {
        "draft": "not_started",
        "pending_approval": "not_started",
        "authorized": "ready",
        "executing": "in_progress",
        "completed": "completed",
        "pending_verification": "completed",
        "verified": "completed",
        "failed": "failed",
        "rejected": "blocked",
        "denied": "blocked",
    }.get(passport_status, "unknown")


def _username_for(db: Session, user_id: str, fallback: str) -> str:
    from app.models.user import UserRow

    user = db.query(UserRow).filter(UserRow.user_id == user_id).first()
    if user is not None:
        return user.username
    return fallback


def _build_item(db: Session, row) -> SupervisedTaskItem:
    from app.services.task_service import _row_to_passport

    passport = _row_to_passport(row)
    events = audit_service.get_events_for_task(row.task_id)
    latest = events[-1] if events else None
    return SupervisedTaskItem(
        task_id=row.task_id,
        title=row.title,
        purpose=row.purpose,
        status=row.status,
        security_mode=row.security_mode or "standard",
        sensitivity=row.sensitivity,
        approval_requirement=row.approval_requirement,
        requested_operation=row.requested_operation,
        allowed_tools=passport.allowed_tools,
        allowed_sources=passport.allowed_sources,
        allowed_models=passport.allowed_models,
        network_policy=row.network_policy,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
        user_id=row.user_id,
        username=_username_for(db, row.user_id, row.identity),
        role=row.role,
        execution_status=_execution_status(row.status),
        verification_status=_verification_status(
            row.status, requires_human_verification(passport)
        ),
        total_audit_events=len(events),
        latest_event_type=latest.event_type if latest else None,
        latest_event_timestamp=latest.timestamp.isoformat() if latest else None,
    )


def _record_list_view(current_user: CurrentUser, count: int) -> None:
    from app.services.audit_service import audit_service as _audit

    role = current_user.role.value
    event_type = f"{role.upper()}_SUPERVISION_LIST_VIEW"
    _audit.record(
        event_type=event_type,
        task_id="",
        user_id=current_user.user_id,
        identity=current_user.username,
        role=role,
        detail=(
            f"actor_user_id={current_user.user_id}; actor_role={role}; "
            f"action={event_type}; visible_tasks={count}"
        ),
    )


def _load_supervised_passport(
    db: Session, task_id: str, current_user: CurrentUser, *, trace: bool = False
):
    """Fetch a task, enforcing supervision scope; audit VIEW_TASK (+ VIEW_TRACE)."""
    try:
        passport = passport_service.get(db, task_id)
    except TaskPassportNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task passport not found",
        ) from exc

    if passport.user_id == current_user.user_id:
        # Own task — allowed, but supervision decisions are handled separately.
        return passport

    if passport.role not in SUPERVISED_WORKER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This task is outside your supervision scope",
        )

    record_supervisory_view(
        current_user,
        task_id=task_id,
        target_user_id=passport.user_id,
        view="task",
    )
    if trace:
        record_supervisory_view(
            current_user,
            task_id=task_id,
            target_user_id=passport.user_id,
            view="trace",
        )
    return passport


@router.get("/tasks", response_model=SupervisedTaskListResponse)
def list_supervised_tasks(
    current_user: Annotated[CurrentUser, Depends(SupervisorOnly)],
    db: Annotated[Session, Depends(get_db)],
    status_filter: str | None = None,
    worker_role: str | None = None,
) -> SupervisedTaskListResponse:
    """List worker tasks under manager/admin supervision (server-side scoped)."""
    query = db.query(TaskPassportRow).filter(
        TaskPassportRow.deleted_at.is_(None),
        TaskPassportRow.role.in_(tuple(SUPERVISED_WORKER_ROLES)),
    )
    if status_filter:
        query = query.filter(TaskPassportRow.status == status_filter)
    if worker_role:
        query = query.filter(TaskPassportRow.role == worker_role)

    rows = query.order_by(TaskPassportRow.created_at.desc()).all()
    items = [_build_item(db, r) for r in rows]
    _record_list_view(current_user, len(items))
    return SupervisedTaskListResponse(tasks=items, total=len(items))


@router.get("/tasks/{task_id}", response_model=SupervisionDetailResponse)
def get_supervised_task_detail(
    task_id: str,
    current_user: Annotated[CurrentUser, Depends(SupervisorOnly)],
    db: Annotated[Session, Depends(get_db)],
) -> SupervisionDetailResponse:
    """Open one supervised task: passport, plan, verification records, trace."""
    _load_supervised_passport(db, task_id, current_user, trace=True)

    row = db.get(TaskPassportRow, task_id)
    item = _build_item(db, row)

    plan = human_verification_service.get_plan_for_task(task_id)
    plan_response = None
    if plan is not None:
        plan_response = PlanSupervision(
            plan_id=plan.plan_id,
            task_id=plan.task_id,
            user_query=plan.user_query,
            status=plan.status.value,
            steps=[
                PlanStepSupervision(
                    step_id=s.step_id,
                    order=s.order,
                    tool_name=s.tool_name,
                    action=s.action,
                    description=s.description,
                    status=s.status.value,
                    risk=s.risk,
                    requires_approval=s.requires_approval,
                )
                for s in plan.steps
            ],
        )

    verifications = human_verification_service.get_verifications(db, task_id)
    events = audit_service.get_events_for_task(task_id)

    return SupervisionDetailResponse(
        task=item,
        plan=plan_response,
        verifications=[
            VerificationRecordResponse(
                kind=v.kind,
                decision=v.decision,
                reason=v.reason,
                actor_user_id=v.actor_user_id,
                actor_username=v.actor_identity,
                actor_role=v.actor_role,
                target_user_id=v.target_user_id,
                created_at=v.created_at.isoformat(),
            )
            for v in verifications
        ],
        audit_events=[
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
    )

def _decide(
    db: Session,
    task_id: str,
    current_user: CurrentUser,
    action: str,
    reason: str,
):
    passport = _load_supervised_passport(db, task_id, current_user)
    if passport.user_id == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot perform supervision decisions on your own task",
        )
    try:
        if action == "approve":
            return human_verification_service.approve_task(db, passport, current_user)
        if action == "reject":
            return human_verification_service.reject_task(
                db, passport, current_user, reason
            )
        if action == "verify":
            return human_verification_service.verify_completion(
                db, passport, current_user
            )
        if action == "reject_completion":
            return human_verification_service.reject_completion(
                db, passport, current_user, reason
            )
    except HumanVerificationDenied as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    except HumanVerificationConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except HumanVerificationReasonRequired as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown action")


@router.post("/tasks/{task_id}/approve")
def approve_task(
    task_id: str,
    current_user: Annotated[CurrentUser, Depends(SupervisorOnly)],
    db: Annotated[Session, Depends(get_db)],
    payload: DecisionRequest | None = None,
) -> dict:
    """Before-task human verification: Approve a task waiting for verification."""
    reason = payload.reason if payload else ""
    result = _decide(db, task_id, current_user, "approve", reason)
    return {"task_id": task_id, "status": result.status.value, "decision": "approved"}


@router.post("/tasks/{task_id}/reject")
def reject_task(
    task_id: str,
    current_user: Annotated[CurrentUser, Depends(SupervisorOnly)],
    db: Annotated[Session, Depends(get_db)],
    payload: StrictDecisionRequest,
) -> dict:
    """Before-task human verification: Reject (reason required)."""
    result = _decide(db, task_id, current_user, "reject", payload.reason)
    return {"task_id": task_id, "status": result.status.value, "decision": "rejected"}


@router.post("/tasks/{task_id}/verify-completion")
def verify_completion(
    task_id: str,
    current_user: Annotated[CurrentUser, Depends(SupervisorOnly)],
    db: Annotated[Session, Depends(get_db)],
    payload: DecisionRequest | None = None,
) -> dict:
    """After-task human verification: Verify completion."""
    reason = payload.reason if payload else ""
    result = _decide(db, task_id, current_user, "verify", reason)
    return {"task_id": task_id, "status": result.status.value, "decision": "verified"}


@router.post("/tasks/{task_id}/reject-completion")
def reject_completion(
    task_id: str,
    current_user: Annotated[CurrentUser, Depends(SupervisorOnly)],
    db: Annotated[Session, Depends(get_db)],
    payload: StrictDecisionRequest,
) -> dict:
    """After-task human verification: Reject / request review (reason required)."""
    result = _decide(db, task_id, current_user, "reject_completion", payload.reason)
    return {
        "task_id": task_id,
        "status": result.status.value,
        "decision": "completion_rejected",
    }
