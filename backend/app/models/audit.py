"""SQLAlchemy ORM model for persistent audit events."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditEventRow(Base):
    """Persistent audit event record.

    Every consequential action is recorded here for full traceability.
    """

    __tablename__ = "audit_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    task_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    identity: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    security_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="standard")
    previous_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
