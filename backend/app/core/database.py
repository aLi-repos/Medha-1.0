"""SQLAlchemy engine and session management.

Uses SQLite by default for development. PostgreSQL is the production target;
the database URL is configurable through the MEDHA_DATABASE_URL environment
variable.
"""

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


# For in-memory SQLite, use StaticPool so all connections share the same
# database.  For file-based databases and PostgreSQL, use the default pool.
_is_in_memory = settings.database_url == "sqlite://" or settings.database_url == "sqlite:///:memory:"

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
    poolclass=StaticPool if _is_in_memory else None,
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _migrate_sqlite_columns() -> None:
    """Add missing columns to existing SQLite tables.

    SQLite's CREATE TABLE IF NOT EXISTS never adds columns to an existing
    table.  After schema changes, ALTER TABLE is the safest approach for a
    local prototype database.

    Migration order:
    1. Add new columns as nullable (safe, no data loss).
    2. Backfill generated values for rows that need them.
    3. Seed demo users will handle final user_id assignment via register().
    """
    if "sqlite" not in settings.database_url:
        return
    from uuid import uuid4

    with engine.connect() as conn:
        # --- task_passports: add security_mode, security_policy_version ---
        cursor = conn.execute(
            text("PRAGMA table_info(task_passports)")
        )
        tp_cols = {row[1] for row in cursor.fetchall()}
        if "security_mode" not in tp_cols:
            conn.execute(text(
                "ALTER TABLE task_passports ADD COLUMN security_mode VARCHAR(20) DEFAULT 'standard'"
            ))
        if "security_policy_version" not in tp_cols:
            conn.execute(text(
                "ALTER TABLE task_passports ADD COLUMN security_policy_version VARCHAR(20) DEFAULT '1.0'"
            ))

        # --- users: add user_id, preferred_security_mode ---
        cursor = conn.execute(
            text("PRAGMA table_info(users)")
        )
        user_cols = {row[1] for row in cursor.fetchall()}
        if "user_id" not in user_cols:
            # Add nullable first — backfill below
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN user_id VARCHAR(20)"
            ))
        if "preferred_security_mode" not in user_cols:
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN preferred_security_mode VARCHAR(20) DEFAULT 'standard'"
            ))

        # Backfill any users with NULL user_id (newly added column or fresh
        # migration). Keyed off the legacy numeric id while it still exists;
        # the migrated table has user_id as PRIMARY KEY (never NULL).
        if "id" in user_cols:
            rows = conn.execute(text("SELECT id, user_id FROM users WHERE user_id IS NULL")).fetchall()
            for row in rows:
                uid = f"USR-{uuid4().hex[:8].upper()}"
                conn.execute(
                    text("UPDATE users SET user_id = :uid WHERE id = :id"),
                    {"uid": uid, "id": row[0]},
                )

        # Backfill any users with NULL preferred_security_mode
        conn.execute(text(
            "UPDATE users SET preferred_security_mode = 'standard' WHERE preferred_security_mode IS NULL"
        ))

        # --- Username is no longer globally unique ---
        # Older schemas declared UNIQUE(username) AND used the numeric id as
        # primary key. Rebuild the users table (data-preserving, not a
        # database recreation) so duplicate usernames are allowed and
        # user_id is the authoritative primary key.
        has_unique_username = False
        cursor = conn.execute(text("PRAGMA index_list(users)"))
        for row in cursor.fetchall():
            if not row[2]:  # not a unique index
                continue
            info = conn.execute(
                text(f'PRAGMA index_info("{row[1]}")')
            ).fetchall()
            if [col[2] for col in info] == ["username"]:
                has_unique_username = True
                break
        if has_unique_username:
            old_count = conn.execute(text("SELECT COUNT(*) FROM users")).fetchone()[0]
            null_uids = conn.execute(
                text("SELECT COUNT(*) FROM users WHERE user_id IS NULL OR user_id = ''")
            ).fetchone()[0]
            if null_uids:
                raise RuntimeError(
                    "users rebuild aborted: rows with empty user_id exist; original table kept"
                )
            dupes = conn.execute(text(
                "SELECT user_id, COUNT(*) AS c FROM users GROUP BY user_id HAVING c > 1"
            )).fetchall()
            if dupes:
                raise RuntimeError(
                    f"users rebuild aborted: duplicate user_id values {dupes}; original table kept"
                )
            conn.execute(text(
                "CREATE TABLE users_rebuild ("
                " user_id VARCHAR(20) PRIMARY KEY,"
                " username VARCHAR(100) NOT NULL,"
                " password_hash VARCHAR(200) NOT NULL,"
                " role VARCHAR(30) NOT NULL DEFAULT 'operator',"
                " preferred_security_mode VARCHAR(20) DEFAULT 'standard'"
                ")"
            ))
            conn.execute(text(
                "INSERT INTO users_rebuild (user_id, username, password_hash, role, preferred_security_mode) "
                "SELECT user_id, username, password_hash, role, preferred_security_mode FROM users"
            ))
            new_count = conn.execute(text("SELECT COUNT(*) FROM users_rebuild")).fetchone()[0]
            if new_count != old_count:
                conn.execute(text("DROP TABLE users_rebuild"))
                raise RuntimeError(
                    f"users rebuild aborted: count mismatch {old_count} != {new_count}; "
                    "original table kept"
                )
            conn.execute(text("DROP TABLE users"))
            conn.execute(text("ALTER TABLE users_rebuild RENAME TO users"))

        # --- Make user_id the PRIMARY KEY (safe, data-preserving migration) ---
        # SQLite cannot alter a primary key in place. Validate first, then:
        # create migrated structure → copy → validate counts → swap.
        # No child table has a FOREIGN KEY to users.id (verified), and all
        # owner columns already store string user_id values — so dropping the
        # legacy numeric id cannot orphan tasks, audit records, conversations,
        # verifications, or analyses.
        cursor = conn.execute(text("PRAGMA table_info(users)"))
        pk_cols = [row[1] for row in cursor.fetchall() if row[5] > 0]
        if pk_cols != ["user_id"]:
            null_uids = conn.execute(
                text("SELECT COUNT(*) FROM users WHERE user_id IS NULL OR user_id = ''")
            ).fetchone()[0]
            if null_uids:
                raise RuntimeError(
                    "users PK migration aborted: rows with empty user_id exist; original table kept"
                )
            dupes = conn.execute(text(
                "SELECT user_id, COUNT(*) AS c FROM users GROUP BY user_id HAVING c > 1"
            )).fetchall()
            if dupes:
                raise RuntimeError(
                    f"users PK migration aborted: duplicate user_id values {dupes}; "
                    "original table kept"
                )
            old_count = conn.execute(text("SELECT COUNT(*) FROM users")).fetchone()[0]
            conn.execute(text(
                "CREATE TABLE users_pk_migrate ("
                " user_id VARCHAR(20) PRIMARY KEY,"
                " username VARCHAR(100) NOT NULL,"
                " password_hash VARCHAR(200) NOT NULL,"
                " role VARCHAR(30) NOT NULL DEFAULT 'operator',"
                " preferred_security_mode VARCHAR(20) DEFAULT 'standard'"
                ")"
            ))
            conn.execute(text(
                "INSERT INTO users_pk_migrate (user_id, username, password_hash, role, preferred_security_mode) "
                "SELECT user_id, username, password_hash, role, preferred_security_mode FROM users"
            ))
            new_count = conn.execute(text("SELECT COUNT(*) FROM users_pk_migrate")).fetchone()[0]
            if new_count != old_count:
                conn.execute(text("DROP TABLE users_pk_migrate"))
                raise RuntimeError(
                    f"users PK migration aborted: count mismatch {old_count} != {new_count}; "
                    "original table kept"
                )
            # Preserve relationship values: every task owner must still
            # resolve to a users row after the swap — either as an existing
            # user_id or as a username snapshot that the username→user_id
            # backfill (runs below) will map to a real user_id.
            existing_tables = {
                t[0]
                for t in conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                ).fetchall()
            }
            orphaned = 0
            if "task_passports" in existing_tables:
                orphaned = conn.execute(text(
                    "SELECT COUNT(*) FROM task_passports tp "
                    "WHERE tp.user_id IS NOT NULL AND tp.user_id <> '' "
                    "AND NOT EXISTS ("
                    "  SELECT 1 FROM users_pk_migrate u WHERE u.user_id = tp.user_id"
                    ") AND NOT EXISTS ("
                    "  SELECT 1 FROM users_pk_migrate u WHERE u.username = tp.user_id"
                    ")"
                )).fetchone()[0]
            if orphaned:
                conn.execute(text("DROP TABLE users_pk_migrate"))
                raise RuntimeError(
                    f"users PK migration aborted: {orphaned} task owners would be orphaned; "
                    "original table kept"
                )
            conn.execute(text("DROP TABLE users"))
            conn.execute(text("ALTER TABLE users_pk_migrate RENAME TO users"))

        # Unique index on user_id (idempotent — the primary key already
        # enforces uniqueness; kept for compatibility with existing queries).
        try:
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_user_id ON users (user_id)"
            ))
        except Exception:
            pass  # index may already exist

        # --- audit_events: add security_mode ---
        cursor = conn.execute(
            text("PRAGMA table_info(audit_events)")
        )
        ae_cols = {row[1] for row in cursor.fetchall()}
        if "security_mode" not in ae_cols:
            conn.execute(text(
                "ALTER TABLE audit_events ADD COLUMN security_mode VARCHAR(20) DEFAULT 'standard'"
            ))
        # Backfill existing audit events with security_mode from their task's passport
        rows = conn.execute(text(
            "SELECT ae.event_id, tp.security_mode FROM audit_events ae "
            "LEFT JOIN task_passports tp ON ae.task_id = tp.task_id "
            "WHERE ae.security_mode IS NULL"
        )).fetchall()
        for row in rows:
            sm = row[1] or "standard"
            conn.execute(
                text("UPDATE audit_events SET security_mode = :sm WHERE event_id = :eid"),
                {"sm": sm, "eid": row[0]},
            )

        # --- Backfill owner "user_id" columns ----------------
        # Historically task_passports.user_id, conversations.user_id and
        # audit_events.user_id stored the owning user's USERNAME (e.g. 'admin')
        # rather than the immutable users.user_id (USR-XXXXXXXX).  Migration maps
        # those username snapshots to the real user_id so that ownership and
        # audit queries can key on the immutable identifier.
        for table in ("task_passports", "conversations", "audit_events"):
            conn.execute(text(
                f"UPDATE {table} SET user_id = "
                f"(SELECT u.user_id FROM users u WHERE u.username = {table}.user_id) "
                f"WHERE user_id IS NOT NULL AND user_id <> '' "
                f"AND user_id LIKE 'USR-%' = 0 "
                f"AND EXISTS (SELECT 1 FROM users u WHERE u.username = {table}.user_id)"
            ))

        # Ensure an index exists on conversations.user_id for the conversations-
        # after-rename visibility query.
        try:
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_conversations_user_id ON conversations (user_id)"
            ))
        except Exception:
            pass  # index may already exist

        conn.commit()


def init_db() -> None:
    """Create all tables defined by ORM models."""
    Base.metadata.create_all(bind=engine)
    _migrate_sqlite_columns()
