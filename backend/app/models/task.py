"""SQLAlchemy ORM model for the Task Passport."""

import json
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaskPassportRow(Base):
    """Persistent Task Passport record.

    Security-critical fields are: user_id, identity, role, sensitivity,
    allowed_sources, allowed_tools, allowed_models, network_policy.
    These become immutable once status leaves 'draft'.
    """

    __tablename__ = "task_passports"

    task_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    identity: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    purpose: Mapped[str] = mapped_column(String(500), nullable=False)
    sensitivity: Mapped[str] = mapped_column(String(20), nullable=False, default="internal")
    requested_operation: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    allowed_sources: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    allowed_tools: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    allowed_models: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    approval_requirement: Mapped[str] = mapped_column(String(50), nullable=False, default="none")
    network_policy: Mapped[str] = mapped_column(String(50), nullable=False, default="deny_external")
    security_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="standard")
    security_policy_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    deleted_by: Mapped[str | None] = mapped_column(String(100), nullable=True, default=None)

    def get_allowed_sources(self) -> list[str]:
        return json.loads(self.allowed_sources)

    def set_allowed_sources(self, value: list[str]) -> None:
        self.allowed_sources = json.dumps(value)

    def get_allowed_tools(self) -> list[str]:
        return json.loads(self.allowed_tools)

    def set_allowed_tools(self, value: list[str]) -> None:
        self.allowed_tools = json.dumps(value)

    def get_allowed_models(self) -> list[str]:
        return json.loads(self.allowed_models)

    def set_allowed_models(self, value: list[str]) -> None:
        self.allowed_models = json.dumps(value)
