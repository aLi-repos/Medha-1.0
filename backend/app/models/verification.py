"""SQLAlchemy ORM model for human verification decisions (before/after execution)."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaskVerificationRow(Base):
    """Persistent human verification decision for a Task Passport.

    kind:
      - "pre_execution": before-task approval (Approve / Reject)
      - "completion": after-task verification (Verify Completion / Reject)
    decision: "approved" | "rejected"

    passport_fingerprint binds an approval to the exact task plan it
    reviewed; plan_fingerprint (nullable) additionally binds it to the
    agent execution plan when one existed at approval time.
    """

    __tablename__ = "task_verifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    actor_user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    actor_identity: Mapped[str] = mapped_column(String(100), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(30), nullable=False)
    target_user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    passport_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    plan_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
