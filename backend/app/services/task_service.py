"""Task Passport service with SQLAlchemy persistence and lifecycle enforcement.

Security-critical fields become immutable once the passport status leaves
'draft'.  Every status transition is recorded as a structured audit event.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.task import TaskPassportRow
from app.schemas.task import (
    SECURITY_CRITICAL_FIELDS,
    SECURITY_POLICY_VERSION,
    VALID_TRANSITIONS,
    ApprovalRequirement,
    NetworkPolicy,
    SecurityMode,
    SENSITIVITY_SECURITY_REQUIREMENTS,
    TaskCreate,
    TaskPassportRead,
    TaskSensitivity,
    TaskStatus,
    TaskStatusUpdate,
)
from app.services.audit_service import audit_service


class TaskPassportError(Exception):
    """Raised when a Task Passport operation violates policy."""


class TaskPassportNotFoundError(TaskPassportError):
    """Raised when the requested passport does not exist."""


class TaskPassportImmutableFieldError(TaskPassportError):
    """Raised when a security-critical field is mutated after execution begins."""


class TaskPassportInvalidTransitionError(TaskPassportError):
    """Raised when a status transition is not permitted."""


class TaskPassportIdentityError(TaskPassportError):
    """Raised when the requesting user does not match the passport identity."""


class TaskPassportApprovalRequiredError(TaskPassportError):
    """Raised when execution is attempted without required human approval."""


def _row_to_passport(row: TaskPassportRow) -> TaskPassportRead:
    return TaskPassportRead(
        task_id=row.task_id,
        user_id=row.user_id,
        identity=row.identity,
        role=row.role,
        title=row.title,
        purpose=row.purpose,
        sensitivity=TaskSensitivity(row.sensitivity),
        security_mode=SecurityMode(row.security_mode),
        security_policy_version=row.security_policy_version,
        requested_operation=row.requested_operation,
        allowed_sources=json.loads(row.allowed_sources),
        allowed_tools=json.loads(row.allowed_tools),
        allowed_models=json.loads(row.allowed_models),
        approval_requirement=ApprovalRequirement(row.approval_requirement),
        network_policy=NetworkPolicy(row.network_policy),
        status=TaskStatus(row.status),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class TaskPassportService:
    """Manages the full Task Passport lifecycle."""

    def create(
        self,
        db: Session,
        *,
        payload: TaskCreate,
        user_id: str,
        identity: str,
        role: str,
    ) -> TaskPassportRead:
        """Create a new Task Passport in draft status.

        Enforces automatic security mode升级: if sensitivity requires a stronger
        mode, the passport is created with the required mode regardless of
        what was requested.
        """
        now = datetime.now(timezone.utc)

        # Enforce automatic security mode based on sensitivity
        required_mode = SENSITIVITY_SECURITY_REQUIREMENTS.get(
            payload.sensitivity.value, SecurityMode.STANDARD
        )
        effective_mode = SecurityMode(
            max(payload.security_mode.value, required_mode.value, key=lambda m: _security_mode_order(m))
        )

        row = TaskPassportRow(
            task_id=str(uuid4()),
            user_id=user_id,
            identity=identity,
            role=role,
            title=payload.title,
            purpose=payload.purpose,
            sensitivity=payload.sensitivity.value,
            security_mode=effective_mode.value,
            security_policy_version=SECURITY_POLICY_VERSION,
            requested_operation=payload.requested_operation,
            allowed_sources=json.dumps(payload.allowed_sources),
            allowed_tools=json.dumps(payload.allowed_tools),
            allowed_models=json.dumps(payload.allowed_models),
            approval_requirement=payload.approval_requirement.value,
            network_policy=payload.network_policy.value,
            status=TaskStatus.DRAFT.value,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        db.commit()
        db.refresh(row)

        audit_service.record(
            event_type="passport_created",
            task_id=row.task_id,
            user_id=user_id,
            identity=identity,
            role=role,
            security_mode=effective_mode.value,
            new_status=TaskStatus.DRAFT.value,
            detail=f"Task passport created: {payload.title}",
        )

        return _row_to_passport(row)

    def get(self, db: Session, task_id: str, include_deleted: bool = False) -> TaskPassportRead:
        """Retrieve a Task Passport by ID."""
        row = db.get(TaskPassportRow, task_id)
        if row is None:
            raise TaskPassportNotFoundError(f"Task passport {task_id} not found")
        if not include_deleted and row.deleted_at is not None:
            raise TaskPassportNotFoundError(f"Task passport {task_id} not found")
        return _row_to_passport(row)

    def soft_delete(
        self,
        db: Session,
        *,
        task_id: str,
        user_id: str,
        identity: str,
        role: str,
    ) -> TaskPassportRead:
        """Soft-delete a Task Passport. Audit trail is preserved."""
        row = db.get(TaskPassportRow, task_id)
        if row is None:
            raise TaskPassportNotFoundError(f"Task passport {task_id} not found")

        if row.deleted_at is not None:
            raise TaskPassportNotFoundError(f"Task passport {task_id} not found")

        previous_status = row.status
        row.deleted_at = datetime.now(timezone.utc)
        row.deleted_by = user_id
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)

        audit_service.record(
            event_type="passport_deleted",
            task_id=task_id,
            user_id=user_id,
            identity=identity,
            role=role,
            security_mode=row.security_mode or "standard",
            previous_status=previous_status,
            new_status=None,
            detail=f"Task passport soft-deleted by {user_id}",
        )

        return _row_to_passport(row)

    def transition_status(
        self,
        db: Session,
        *,
        task_id: str,
        update: TaskStatusUpdate,
        user_id: str,
        identity: str,
        role: str,
    ) -> TaskPassportRead:
        """Transition a Task Passport to a new status with audit logging.

        Human-verification rules (server-side, non-bypassable):
        - Owners cannot transition OUT of pending_approval / pending_verification;
          only manager/admin supervision decisions may resolve those states.
        - When approval is required, entering authorized/executing demands a
          valid, unmodified manager/admin approval record.
        - Completing an approval-required task moves it into
          pending_verification for after-task human verification.
        """
        from app.services.human_verification import (
            requires_human_verification,
            human_verification_service,
        )

        row = db.get(TaskPassportRow, task_id)
        if row is None:
            raise TaskPassportNotFoundError(f"Task passport {task_id} not found")

        current_status = TaskStatus(row.status)
        new_status = update.new_status
        approval_required = requires_human_verification(_row_to_passport(row))

        # Awaiting a manager/admin decision: owners cannot bypass or self-resolve.
        if current_status in (
            TaskStatus.PENDING_APPROVAL,
            TaskStatus.PENDING_VERIFICATION,
        ):
            raise TaskPassportInvalidTransitionError(
                "This task is awaiting human verification; only a manager/admin "
                "supervision decision can change its status"
            )

        if new_status not in VALID_TRANSITIONS.get(current_status, set()):
            raise TaskPassportInvalidTransitionError(
                f"Cannot transition from {current_status.value} to {new_status.value}"
            )

        # Submitting for verification only applies to approval-required tasks.
        if new_status == TaskStatus.PENDING_APPROVAL and not approval_required:
            raise TaskPassportInvalidTransitionError(
                "This task does not require human verification"
            )

        # Approval gate: authorized/executing require a valid approval record.
        if approval_required and new_status in (
            TaskStatus.AUTHORIZED,
            TaskStatus.EXECUTING,
        ):
            ok, reason = human_verification_service.check_pre_execution(
                _row_to_passport(row)
            )
            if not ok:
                raise TaskPassportApprovalRequiredError(reason)

        previous_status = current_status.value
        row.status = new_status.value
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)

        audit_service.record(
            event_type="passport_status_transition",
            task_id=task_id,
            user_id=user_id,
            identity=identity,
            role=role,
            security_mode=row.security_mode or "standard",
            previous_status=previous_status,
            new_status=new_status.value,
            detail=update.detail,
        )

        # After-task human verification: completed approval-required tasks
        # automatically enter "waiting for completion verification".
        if new_status == TaskStatus.COMPLETED and approval_required:
            row.status = TaskStatus.PENDING_VERIFICATION.value
            row.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(row)
            audit_service.record(
                event_type="passport_status_transition",
                task_id=task_id,
                user_id=user_id,
                identity=identity,
                role=role,
                security_mode=row.security_mode or "standard",
                previous_status=TaskStatus.COMPLETED.value,
                new_status=TaskStatus.PENDING_VERIFICATION.value,
                detail="Task completed — awaiting manager/admin completion verification",
            )

        return _row_to_passport(row)

    def change_security_mode(
        self,
        db: Session,
        *,
        task_id: str,
        new_mode: SecurityMode,
        user_id: str,
        identity: str,
        role: str,
    ) -> TaskPassportRead:
        """Change the security mode on a Task Passport.

        Users can only INCREASE protection (standard → secure → sovereign).
        If policy requires sovereign, downgrade is blocked.
        Only the passport owner can change the security mode.
        """
        row = db.get(TaskPassportRow, task_id)
        if row is None:
            raise TaskPassportNotFoundError(f"Task passport {task_id} not found")

        # Ownership check — immutable user_id is the authoritative key
        if row.user_id != user_id:
            raise TaskPassportIdentityError(
                "Your identity does not match this Task Passport"
            )

        current_mode = SecurityMode(row.security_mode)
        required_mode = SENSITIVITY_SECURITY_REQUIREMENTS.get(
            row.sensitivity, SecurityMode.STANDARD
        )

        # Block downgrade if policy requires a minimum mode
        if _security_mode_order(new_mode.value) < _security_mode_order(required_mode.value):
            raise TaskPassportImmutableFieldError(
                f"Cannot downgrade to {new_mode.value}: "
                f"task sensitivity '{row.sensitivity}' requires "
                f"{required_mode.value} or stronger"
            )

        # Block downgrade in general (users can only increase)
        if _security_mode_order(new_mode.value) < _security_mode_order(current_mode.value):
            raise TaskPassportImmutableFieldError(
                f"Cannot downgrade from {current_mode.value} to {new_mode.value}: "
                f"security mode can only be increased"
            )

        previous_mode = current_mode.value
        row.security_mode = new_mode.value
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)

        audit_service.record(
            event_type="security_mode_changed",
            task_id=task_id,
            user_id=user_id,
            identity=identity,
            role=role,
            security_mode=new_mode.value,
            detail=(
                f"Security mode changed: {previous_mode} → {new_mode.value} "
                f"(policy_version={SECURITY_POLICY_VERSION})"
            ),
        )

        return _row_to_passport(row)

    def update_security_fields(
        self,
        db: Session,
        *,
        task_id: str,
        user_id: str,
        identity: str,
        role: str,
        allowed_sources: list[str] | None = None,
        allowed_tools: list[str] | None = None,
        allowed_models: list[str] | None = None,
        sensitivity: TaskSensitivity | None = None,
        network_policy: NetworkPolicy | None = None,
        security_mode: SecurityMode | None = None,
    ) -> TaskPassportRead:
        """Update security-critical fields — only allowed while in draft status."""
        row = db.get(TaskPassportRow, task_id)
        if row is None:
            raise TaskPassportNotFoundError(f"Task passport {task_id} not found")

        if row.status != TaskStatus.DRAFT.value:
            raise TaskPassportImmutableFieldError(
                "Security-critical fields cannot be modified after execution begins"
            )

        if allowed_sources is not None:
            row.allowed_sources = json.dumps(allowed_sources)
        if allowed_tools is not None:
            row.allowed_tools = json.dumps(allowed_tools)
        if allowed_models is not None:
            row.allowed_models = json.dumps(allowed_models)
        if sensitivity is not None:
            row.sensitivity = sensitivity.value
        if network_policy is not None:
            row.network_policy = network_policy.value
        if security_mode is not None:
            row.security_mode = security_mode.value

        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)

        audit_service.record(
            event_type="passport_security_fields_updated",
            task_id=task_id,
            user_id=user_id,
            identity=identity,
            role=role,
            security_mode=row.security_mode or "standard",
            detail="Security-critical fields updated in draft",
        )

        return _row_to_passport(row)


def _security_mode_order(mode: str) -> int:
    """Return numeric order for security mode comparison (higher = stricter)."""
    return {"standard": 0, "secure": 1, "sovereign": 2}.get(mode, 0)


passport_service = TaskPassportService()
