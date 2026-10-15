import base64
import hashlib
import hmac
import os
import re
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import security_mode_for_role, security_mode_order, settings
from app.models.user import UserRow
from app.schemas.auth import Role
from app.services.audit_service import audit_service

_PBKDF2_ITERATIONS = 600_000
_SALT_LENGTH = 16


def _hash_password(password: str) -> str:
    salt = os.urandom(_SALT_LENGTH)
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return base64.urlsafe_b64encode(salt + h).decode("ascii")


def _verify_password(password: str, encoded_hash: str) -> bool:
    try:
        decoded = base64.urlsafe_b64decode(encoded_hash.encode("ascii"))
        salt, expected_hash = decoded[:_SALT_LENGTH], decoded[_SALT_LENGTH:]
        actual_hash = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
        )
    except (ValueError, UnicodeEncodeError):
        return False
    return hmac.compare_digest(actual_hash, expected_hash)


def _generate_user_id() -> str:
    """Generate a stable, unique user_id (USR-XXXXXXXX format)."""
    return f"USR-{uuid4().hex[:8].upper()}"


def _validate_username(username: str) -> str | None:
    """Validate username format. Returns error message or None if valid."""
    if not re.match(r"^[a-zA-Z0-9._-]+$", username):
        return "Username must contain only letters, numbers, dots, hyphens, and underscores"
    if len(username) < 3:
        return "Username must be at least 3 characters"
    if len(username) > 100:
        return "Username must be at most 100 characters"
    return None


class UserService:
    """Database-backed user store."""

    def get_by_username(self, db: Session, username: str) -> UserRow | None:
        return db.query(UserRow).filter(UserRow.username == username).first()

    def get_by_user_id(self, db: Session, user_id: str) -> UserRow | None:
        return db.query(UserRow).filter(UserRow.user_id == user_id).first()

    def authenticate(
        self,
        db: Session,
        username: str,
        password: str,
        user_id: str | None = None,
    ) -> UserRow | None:
        """Resolve and verify login identity.

        user_id is authoritative when provided: the account must match
        user_id + username + password (role is loaded from the DB, never
        from the client). Without user_id, username + password must
        identify exactly one account (ambiguous duplicates are rejected).
        """
        if user_id is not None:
            user = self.get_by_user_id(db, user_id)
            if (
                user is None
                or user.username != username
                or not _verify_password(password, user.password_hash)
            ):
                return None
            return user

        candidates = db.query(UserRow).filter(UserRow.username == username).all()
        matches = [u for u in candidates if _verify_password(password, u.password_hash)]
        if len(matches) == 1:
            return matches[0]
        # Zero matches, or multiple accounts share username AND password —
        # caller must supply user_id to disambiguate.
        return None

    def register(self, db: Session, username: str, password: str, role: Role, user_id: str | None = None) -> UserRow | None:
        # Duplicate usernames are allowed — each registration is a new
        # account with its own user_id. Default security mode comes from
        # the configurable role → security-mode mapping.
        user = UserRow(
            user_id=user_id or _generate_user_id(),
            username=username,
            password_hash=_hash_password(password),
            role=role.value,
            preferred_security_mode=security_mode_for_role(role.value),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def change_password(
        self,
        db: Session,
        *,
        user_id: str,
        current_password: str,
        new_password: str,
    ) -> UserRow:
        """Change the user's password. user_id and role are untouched."""
        user = self.get_by_user_id(db, user_id)
        if user is None:
            raise ValueError("User not found")
        if not _verify_password(current_password, user.password_hash):
            raise ValueError("Current password is incorrect")
        if len(new_password) < 6:
            raise ValueError("New password must be at least 6 characters")
        user.password_hash = _hash_password(new_password)
        db.commit()
        db.refresh(user)
        audit_service.record(
            event_type="password_changed",
            task_id="",
            user_id=user_id,
            identity=user.username,
            role=user.role,
            detail="Password changed",
        )
        return user

    def edit_username(
        self,
        db: Session,
        *,
        user_id: str,
        new_username: str,
    ) -> UserRow:
        """Edit a user's username. Validates uniqueness and format.

        The user_id remains stable — only the username changes.
        """
        error = _validate_username(new_username)
        if error:
            raise ValueError(error)

        user = self.get_by_user_id(db, user_id)
        if user is None:
            raise ValueError("User not found")

        old_username = user.username
        if old_username == new_username:
            return user

        # Duplicate usernames are allowed — only this account's username
        # changes; user_id and all owned data are untouched.
        user.username = new_username
        db.commit()
        db.refresh(user)

        # Record audit event
        audit_service.record(
            event_type="username_changed",
            task_id="",
            user_id=user_id,
            identity=new_username,
            role=user.role,
            detail=f"Username changed: {old_username} → {new_username}",
        )

        return user

    def get_preferred_security_mode(self, db: Session, user_id: str) -> str:
        """Get the user's effective security mode (never below the role floor)."""
        user = self.get_by_user_id(db, user_id)
        if user is None:
            return "standard"
        current = getattr(user, "preferred_security_mode", None) or "standard"
        floor = security_mode_for_role(user.role)
        if security_mode_order(floor) > security_mode_order(current):
            return floor
        return current

    def ensure_role_security_floor(self, db: Session, user: UserRow) -> None:
        """Persist the role's minimum security mode if the stored value is lower.

        Called on login so the backend determines the effective default
        security mode from the user's (organization-controlled) role.
        """
        floor = security_mode_for_role(user.role)
        current = getattr(user, "preferred_security_mode", None) or "standard"
        if security_mode_order(floor) > security_mode_order(current):
            user.preferred_security_mode = floor
            db.commit()
            db.refresh(user)

    def set_preferred_security_mode(self, db: Session, user_id: str, mode: str) -> str:
        """Set the user's preferred security mode.

        Rejects modes below the role-required floor (users cannot lower
        protection required by their role). Increases above the floor are allowed.
        """
        if mode not in ("standard", "secure", "sovereign"):
            raise ValueError(f"Invalid security mode: {mode}")
        user = self.get_by_user_id(db, user_id)
        if user is None:
            raise ValueError("User not found")
        floor = security_mode_for_role(user.role)
        if security_mode_order(mode) < security_mode_order(floor):
            raise ValueError(
                f"Security mode cannot be lowered below '{floor}' required by your role"
            )
        user.preferred_security_mode = mode
        db.commit()
        db.refresh(user)
        return user.preferred_security_mode

    def seed_demo_users(self, db: Session) -> None:
        """Ensure the documented demo credentials work.

        Idempotent and non-destructive. user_id is the permanent
        identity, so seeding keys off user_id first:
        - Missing demo users are created with their stable user_id.
        - A documented user_id that already exists (e.g. because the
          username was renamed) is NEVER replaced: no replacement account
          is created, and username edits are preserved across restarts.
        - Existing users are never deleted, renamed, or re-roled.
        - Passwords are re-hashed only in development and only when the
          documented demo password fails to verify, so a healthy database
          is never rewritten on startup.
        """
        demo_users = [
            ("USR-00000001", "operator", "medha-operator-2026", Role.OPERATOR),
            ("USR-00000002", "engineer", "medha-engineer-2026", Role.ENGINEER),
            ("USR-00000003", "reviewer", "medha-reviewer-2026", Role.REVIEWER),
            ("USR-00000004", "admin", "medha-admin-2026", Role.ADMIN),
            ("USR-00000005", "arun.maintenance", "medha-arun-2026", Role.ENGINEER),
            ("SE00503", "nagarjuna", "medha-nagarjuna-2026", Role.SENIOR_ENGINEER),
            ("AD00637", "lokesh", "medha-lokesh-2026", Role.ADMIN),
            ("MD00574", "Ali", "medha-ali-2026", Role.MANAGER),
            ("OP00303", "Balaji", "medha-balaji-2026", Role.OPERATOR),
            ("JE00589", "keerthi", "medha-keerthi-2026", Role.JUNIOR_ENGINEER),
            ("MO00579", "saniya", "medha-saniya-2026", Role.MONITOR),
        ]

        is_development = settings.environment == "development"

        for uid, uname, pw, role in demo_users:
            existing_by_uid = self.get_by_user_id(db, uid)
            if existing_by_uid is not None:
                # The documented user_id already exists. It may have been
                # renamed, so never create a replacement account. Only
                # refresh the demo password in development when it no
                # longer verifies.
                if is_development and not _verify_password(pw, existing_by_uid.password_hash):
                    existing_by_uid.password_hash = _hash_password(pw)
                continue

            # user_id is authoritative: create the demo account even if another
            # account already holds the documented username (duplicates allowed).
            try:
                user = UserRow(
                    user_id=uid,
                    username=uname,
                    password_hash=_hash_password(pw),
                    role=role.value,
                    preferred_security_mode=security_mode_for_role(role.value),
                )
                db.add(user)
                db.flush()
            except Exception:
                db.rollback()
                continue
        db.commit()


user_service = UserService()
