"""SQLAlchemy ORM model for the persistent task-aware Secure Analysis store."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SecureAnalysisRow(Base):
    """Persistent record of a completed secure analysis.

    The full AnalysisResult payload is stored as JSON in ``content``.  Rows are
    soft-deleted through ``deleted_at`` / ``deleted_by`` so history can never be
    retroactively wiped; audit events capture the deletion itself.
    """

    __tablename__ = "secure_analyses"

    analysis_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    owner_user_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    security_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="standard")
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    task_type: Mapped[str] = mapped_column(String(100), nullable=False, default="general")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    handover_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[str | None] = mapped_column(String(20), nullable=True)