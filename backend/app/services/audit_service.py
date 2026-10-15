"""Structured audit event service for Task Passport lifecycle.

Uses SQLite/SQLAlchemy for persistent audit storage. Events survive server
restarts. Each event is a structured dict suitable for future replacement
with PostgreSQL/OpenTelemetry storage.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.audit import AuditEventRow


class AuditEvent:
    """A single immutable audit event."""

    __slots__ = (
        "event_id",
        "timestamp",
        "event_type",
        "task_id",
        "user_id",
        "identity",
        "role",
        "security_mode",
        "previous_status",
        "new_status",
        "detail",
    )

    def __init__(
        self,
        *,
        event_id: str,
        timestamp: datetime,
        event_type: str,
        task_id: str,
        user_id: str,
        identity: str,
        role: str,
        security_mode: str = "standard",
        previous_status: str | None = None,
        new_status: str | None = None,
        detail: str = "",
    ) -> None:
        self.event_id = event_id
        self.timestamp = timestamp
        self.event_type = event_type
        self.task_id = task_id
        self.user_id = user_id
        self.identity = identity
        self.role = role
        self.security_mode = security_mode
        self.previous_status = previous_status
        self.new_status = new_status
        self.detail = detail

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "task_id": self.task_id,
            "user_id": self.user_id,
            "identity": self.identity,
            "role": self.role,
            "security_mode": self.security_mode,
            "previous_status": self.previous_status,
            "new_status": self.new_status,
            "detail": self.detail,
        }


class AuditService:
    """Persists audit events to SQLite via SQLAlchemy.

    Events are stored in the database and survive server restarts.
    """

    def record(
        self,
        *,
        event_type: str,
        task_id: str,
        user_id: str,
        identity: str,
        role: str,
        security_mode: str = "standard",
        previous_status: str | None = None,
        new_status: str | None = None,
        detail: str = "",
    ) -> AuditEvent:
        event_id = str(uuid4())
        timestamp = datetime.now(timezone.utc)

        row = AuditEventRow(
            event_id=event_id,
            timestamp=timestamp,
            event_type=event_type,
            task_id=task_id,
            user_id=user_id,
            identity=identity,
            role=role,
            security_mode=security_mode,
            previous_status=previous_status,
            new_status=new_status,
            detail=detail,
        )

        db = SessionLocal()
        try:
            db.add(row)
            db.commit()
        finally:
            db.close()

        return AuditEvent(
            event_id=event_id,
            timestamp=timestamp,
            event_type=event_type,
            task_id=task_id,
            user_id=user_id,
            identity=identity,
            role=role,
            security_mode=security_mode,
            previous_status=previous_status,
            new_status=new_status,
            detail=detail,
        )

    def _row_to_event(self, r: AuditEventRow) -> AuditEvent:
        return AuditEvent(
            event_id=r.event_id,
            timestamp=r.timestamp,
            event_type=r.event_type,
            task_id=r.task_id,
            user_id=r.user_id,
            identity=r.identity,
            role=r.role,
            security_mode=getattr(r, "security_mode", "standard") or "standard",
            previous_status=r.previous_status,
            new_status=r.new_status,
            detail=r.detail,
        )

    def get_events_for_task(self, task_id: str) -> list[AuditEvent]:
        db = SessionLocal()
        try:
            rows = (
                db.query(AuditEventRow)
                .filter(AuditEventRow.task_id == task_id)
                .order_by(AuditEventRow.timestamp)
                .all()
            )
            return [self._row_to_event(r) for r in rows]
        finally:
            db.close()

    def get_events_for_identity_by_security_mode(
        self, user_id: str, security_mode: str
    ) -> list[AuditEvent]:
        """Return audit events for a user filtered by security domain.

        Only returns events whose task has the specified security_mode,
        OR events that are global (task_id == '') like security_mode_changed.

        Ownership is matched on the immutable user_id so events remain
        associated with the user even after a username edit.
        """
        db = SessionLocal()
        try:
            rows = (
                db.query(AuditEventRow)
                .filter(
                    AuditEventRow.user_id == user_id,
                    AuditEventRow.security_mode == security_mode,
                )
                .order_by(AuditEventRow.timestamp)
                .all()
            )
            return [self._row_to_event(r) for r in rows]
        finally:
            db.close()

    def get_all_events(self) -> list[AuditEvent]:
        db = SessionLocal()
        try:
            rows = (
                db.query(AuditEventRow)
                .order_by(AuditEventRow.timestamp)
                .all()
            )
            return [self._row_to_event(r) for r in rows]
        finally:
            db.close()

    def clear(self) -> None:
        """Clear all events; used only by isolated tests."""
        db = SessionLocal()
        try:
            db.query(AuditEventRow).delete()
            db.commit()
        finally:
            db.close()


audit_service = AuditService()
