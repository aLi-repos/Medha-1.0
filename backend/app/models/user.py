"""SQLAlchemy ORM model for the User table."""

from sqlalchemy import String, event
from sqlalchemy.orm import Mapped, Session, mapped_column
from sqlalchemy.orm.attributes import get_history

from app.core.database import Base


class UserRow(Base):
    """Persistent User record for authentication.

    user_id is the primary key: a stable, unique identifier that never
    changes and is the authoritative account identity. username is
    editable by the user and is NOT globally unique — duplicate usernames
    are allowed; accounts remain separate via user_id (and role).
    """

    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False, default="operator")
    preferred_security_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="standard")


@event.listens_for(Session, "before_flush")
def _guard_user_id_immutability(session: Session, flush_context, instances) -> None:
    """user_id is immutable after account creation — reject any update."""
    for obj in session.dirty:
        if isinstance(obj, UserRow):
            history = get_history(obj, "user_id")
            if history.has_changes():
                raise ValueError("user_id is immutable and cannot be changed after account creation")
