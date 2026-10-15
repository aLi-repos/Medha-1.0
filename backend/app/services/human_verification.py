"""Human Verification service — server-side before/after task verification.

Manager/Admin decisions are persisted as TaskVerificationRow records and
audited through the existing audit service. Execution authorization (via
the Action Gate and task lifecycle) consults this service, so frontend
buttons alone can never bypass verification.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.task import TaskPassportRow
from app.models.verification import TaskVerificationRow
from app.schemas.auth import CurrentUser
from app.schemas.task import TaskPassportRead, TaskStatus
from app.services.audit_service import audit_service

# Roles allowed to make supervision decisions (page + endpoints).
SUPERVISOR_DECISION_ROLES = {"manager", "admin"}

# Worker roles under manager/admin supervision.
SUPERVISED_WORKER_ROLES = {"operator", "junior_engineer", "monitor"}

# Verification kinds
KIND_PRE_EXECUTION = "pre_execution"
KIND_COMPLETION = "completion"


class HumanVerificationError(Exception):
    """Base error for human verification policy violations."""


class HumanVerificationDenied(HumanVerificationError):
    """Actor is not authorized for this verification decision."""


class HumanVerificationConflict(HumanVerificationError):
    """Decision is not valid for the task's current state (or is a replay)."""


class HumanVerificationReasonRequired(HumanVerificationError):
    """A rejection was submitted without a reason."""


def requires_human_verification(passport: TaskPassportRead) -> bool:
    """True when the passport requires manager/admin human verification."""
    return passport.approval_requirement.value != "none"


def _passport_fingerprint_payload(passport: TaskPassportRead) -> dict:
    return {
        "task_id": passport.task_id,
        "user_id": passport.user_id,
        "title": passport.title,
        "purpose": passport.purpose,
        "requested_operation": passport.requested_operation,
        "allowed_sources": passport.allowed_sources,
        "allowed_tools": passport.allowed_tools,
        "allowed_models": passport.allowed_models,
        "sensitivity": passport.sensitivity.value,
        "security_mode": passport.security_mode.value,
        "network_policy": passport.network_policy.value,
        "approval_requirement": passport.approval_requirement.value,
    }


def fingerprint_passport(passport: TaskPassportRead) -> str:
    """Stable hash of the task plan the supervisor reviewed."""
    payload = json.dumps(_passport_fingerprint_payload(passport), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def fingerprint_plan(plan) -> str:
    """Stable hash of an agent execution plan (id + ordered steps)."""
    payload = {
        "plan_id": plan.plan_id,
        "task_id": plan.task_id,
        "steps": [
            {"order": s.order, "tool_name": s.tool_name, "action": s.action}
            for s in plan.steps
        ],
    }
    raw = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _role_str(role) -> str:
    return role.value if hasattr(role, "value") else str(role)


class HumanVerificationService:
    """Persists and enforces manager/admin human verification decisions."""

    # ---- lookups -----------------------------------------------------------

    def get_verifications(self, db: Session, task_id: str) -> list[TaskVerificationRow]:
        return (
            db.query(TaskVerificationRow)
            .filter(TaskVerificationRow.task_id == task_id)
            .order_by(TaskVerificationRow.created_at, TaskVerificationRow.id)
            .all()
        )

    def get_latest(
        self, db: Session, task_id: str, kind: str
    ) -> TaskVerificationRow | None:
        return (
            db.query(TaskVerificationRow)
            .filter(
                TaskVerificationRow.task_id == task_id,
                TaskVerificationRow.kind == kind,
            )
            .order_by(TaskVerificationRow.created_at.desc(), TaskVerificationRow.id.desc())
            .first()
        )

    def get_plan_for_task(self, task_id: str):
        """Latest agent plan for a task, if any (in-memory agent store)."""
        from app.services.agent.service import agent_service

        plans = [
            p for p in agent_service._plans.values() if p.task_id == task_id
        ]
        if not plans:
            return None
        return max(plans, key=lambda p: p.created_at)

    # ---- authorization -----------------------------------------------------

    def _authorize_decision(self, passport: TaskPassportRead, actor: CurrentUser) -> None:
        actor_role = _role_str(actor.role)
        if actor_role not in SUPERVISOR_DECISION_ROLES:
            raise HumanVerificationDenied(
                "Only manager or admin roles may perform human verification decisions"
            )
        if actor.user_id == passport.user_id:
            raise HumanVerificationDenied(
                "You cannot approve or verify your own task"
            )
        if passport.role not in SUPERVISED_WORKER_ROLES:
            raise HumanVerificationDenied(
                f"Tasks owned by role '{passport.role}' are outside your supervision scope"
            )

    # ---- execution authorization (called by Action Gate / task lifecycle) --

    def check_pre_execution(self, passport: TaskPassportRead) -> tuple[bool, str]:
        """Return (allowed, reason) for executing a task that may require approval."""
        if not requires_human_verification(passport):
            return True, ""

        row = self._session_latest(KIND_PRE_EXECUTION, passport.task_id)
        if row is None or row.decision != "approved":
            return (
                False,
                "Task requires human verification: a manager/admin must approve "
                "this task before execution",
            )
        if row.passport_fingerprint != fingerprint_passport(passport):
            return (
                False,
                "Approval is no longer valid: the task plan changed after "
                "approval and requires re-verification",
            )
        return True, ""

    def check_plan_approval(self, passport: TaskPassportRead, plan) -> tuple[bool, str]:
        """Additionally bind execution to the plan the supervisor approved."""
        ok, reason = self.check_pre_execution(passport)
        if not ok:
            return ok, reason
        if not requires_human_verification(passport):
            return True, ""
        row = self._session_latest(KIND_PRE_EXECUTION, passport.task_id)
        if row is not None and row.plan_fingerprint:
            if fingerprint_plan(plan) != row.plan_fingerprint:
                return (
                    False,
                    "Approval is no longer valid: this execution plan does not "
                    "match the plan approved by the supervisor",
                )
        return True, ""

    def _session_latest(self, kind: str, task_id: str) -> TaskVerificationRow | None:
        from app.core.database import SessionLocal

        db = SessionLocal()
        try:
            return (
                db.query(TaskVerificationRow)
                .filter(
                    TaskVerificationRow.task_id == task_id,
                    TaskVerificationRow.kind == kind,
                )
                .order_by(
                    TaskVerificationRow.created_at.desc(), TaskVerificationRow.id.desc()
                )
                .first()
            )
        finally:
            db.close()

    def assert_execution_allowed(self, passport: TaskPassportRead) -> None:
        ok, reason = self.check_pre_execution(passport)
        if not ok:
            raise HumanVerificationDenied(reason)

    # ---- decisions ---------------------------------------------------------

    def _record_audit(
        self,
        *,
        event_type: str,
        passport: TaskPassportRead,
        actor: CurrentUser,
        previous_status: str,
        new_status: str,
        reason: str = "",
    ) -> None:
        detail = (
            f"actor_user_id={actor.user_id}; "
            f"actor_role={_role_str(actor.role)}; "
            f"target_user_id={passport.user_id}; "
            f"task_id={passport.task_id}; "
            f"action={event_type}"
        )
        if reason:
            detail += f"; reason={reason}"
        audit_service.record(
            event_type=event_type,
            task_id=passport.task_id,
            user_id=actor.user_id,
            identity=actor.username,
            role=_role_str(actor.role),
            security_mode=passport.security_mode.value,
            previous_status=previous_status,
            new_status=new_status,
            detail=detail,
        )

    def _set_status(
        self,
        db: Session,
        passport: TaskPassportRead,
        new_status: TaskStatus,
    ) -> TaskPassportRead:
        row = db.get(TaskPassportRow, passport.task_id)
        row.status = new_status.value
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
        from app.services.task_service import _row_to_passport

        return _row_to_passport(row)

    def approve_task(
        self, db: Session, passport: TaskPassportRead, actor: CurrentUser
    ) -> TaskPassportRead:
        """Manager/Admin approve a task waiting for human verification."""
        self._authorize_decision(passport, actor)
        if passport.status != TaskStatus.PENDING_APPROVAL:
            raise HumanVerificationConflict(
                "Task is not waiting for human verification "
                f"(current status: {passport.status.value})"
            )
        latest = self.get_latest(db, passport.task_id, KIND_PRE_EXECUTION)
        if latest is not None and latest.decision == "approved":
            raise HumanVerificationConflict("Approval has already been recorded")

        plan = self.get_plan_for_task(passport.task_id)
        row = TaskVerificationRow(
            task_id=passport.task_id,
            kind=KIND_PRE_EXECUTION,
            decision="approved",
            reason="",
            actor_user_id=actor.user_id,
            actor_identity=actor.username,
            actor_role=_role_str(actor.role),
            target_user_id=passport.user_id,
            passport_fingerprint=fingerprint_passport(passport),
            plan_fingerprint=fingerprint_plan(plan) if plan is not None else None,
            created_at=datetime.now(timezone.utc),
        )
        db.add(row)
        db.commit()

        event = f"{_role_str(actor.role).upper()}_APPROVE_TASK"
        self._record_audit(
            event_type=event,
            passport=passport,
            actor=actor,
            previous_status=passport.status.value,
            new_status=TaskStatus.AUTHORIZED.value,
        )
        return self._set_status(db, passport, TaskStatus.AUTHORIZED)

    def reject_task(
        self, db: Session, passport: TaskPassportRead, actor: CurrentUser, reason: str
    ) -> TaskPassportRead:
        """Manager/Admin reject a task waiting for human verification."""
        self._authorize_decision(passport, actor)
        if passport.status != TaskStatus.PENDING_APPROVAL:
            raise HumanVerificationConflict(
                "Task is not waiting for human verification "
                f"(current status: {passport.status.value})"
            )
        if not reason or not reason.strip():
            raise HumanVerificationReasonRequired(
                "A rejection reason is required"
            )

        row = TaskVerificationRow(
            task_id=passport.task_id,
            kind=KIND_PRE_EXECUTION,
            decision="rejected",
            reason=reason.strip(),
            actor_user_id=actor.user_id,
            actor_identity=actor.username,
            actor_role=_role_str(actor.role),
            target_user_id=passport.user_id,
            passport_fingerprint=fingerprint_passport(passport),
            plan_fingerprint=None,
            created_at=datetime.now(timezone.utc),
        )
        db.add(row)
        db.commit()

        event = f"{_role_str(actor.role).upper()}_REJECT_TASK"
        self._record_audit(
            event_type=event,
            passport=passport,
            actor=actor,
            previous_status=passport.status.value,
            new_status=TaskStatus.REJECTED.value,
            reason=reason.strip(),
        )
        return self._set_status(db, passport, TaskStatus.REJECTED)

    def verify_completion(
        self, db: Session, passport: TaskPassportRead, actor: CurrentUser
    ) -> TaskPassportRead:
        """Manager/Admin verify a completed task's outcome."""
        self._authorize_decision(passport, actor)
        if passport.status != TaskStatus.PENDING_VERIFICATION:
            raise HumanVerificationConflict(
                "Task is not waiting for completion verification "
                f"(current status: {passport.status.value})"
            )
        latest = self.get_latest(db, passport.task_id, KIND_COMPLETION)
        if latest is not None and latest.decision == "approved":
            raise HumanVerificationConflict(
                "Completion verification has already been recorded"
            )

        row = TaskVerificationRow(
            task_id=passport.task_id,
            kind=KIND_COMPLETION,
            decision="approved",
            reason="",
            actor_user_id=actor.user_id,
            actor_identity=actor.username,
            actor_role=_role_str(actor.role),
            target_user_id=passport.user_id,
            passport_fingerprint=fingerprint_passport(passport),
            plan_fingerprint=None,
            created_at=datetime.now(timezone.utc),
        )
        db.add(row)
        db.commit()

        event = f"{_role_str(actor.role).upper()}_VERIFY_COMPLETION"
        self._record_audit(
            event_type=event,
            passport=passport,
            actor=actor,
            previous_status=passport.status.value,
            new_status=TaskStatus.VERIFIED.value,
        )
        return self._set_status(db, passport, TaskStatus.VERIFIED)

    def reject_completion(
        self, db: Session, passport: TaskPassportRead, actor: CurrentUser, reason: str
    ) -> TaskPassportRead:
        """Manager/Admin reject a completed task and request review."""
        self._authorize_decision(passport, actor)
        if passport.status != TaskStatus.PENDING_VERIFICATION:
            raise HumanVerificationConflict(
                "Task is not waiting for completion verification "
                f"(current status: {passport.status.value})"
            )
        if not reason or not reason.strip():
            raise HumanVerificationReasonRequired(
                "A rejection reason is required"
            )

        row = TaskVerificationRow(
            task_id=passport.task_id,
            kind=KIND_COMPLETION,
            decision="rejected",
            reason=reason.strip(),
            actor_user_id=actor.user_id,
            actor_identity=actor.username,
            actor_role=_role_str(actor.role),
            target_user_id=passport.user_id,
            passport_fingerprint=fingerprint_passport(passport),
            plan_fingerprint=None,
            created_at=datetime.now(timezone.utc),
        )
        db.add(row)
        db.commit()

        event = f"{_role_str(actor.role).upper()}_REJECT_COMPLETION"
        self._record_audit(
            event_type=event,
            passport=passport,
            actor=actor,
            previous_status=passport.status.value,
            new_status=TaskStatus.REJECTED.value,
            reason=reason.strip(),
        )
        return self._set_status(db, passport, TaskStatus.REJECTED)


human_verification_service = HumanVerificationService()
