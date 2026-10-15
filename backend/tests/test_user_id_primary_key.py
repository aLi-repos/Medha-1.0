"""Focused tests: users.user_id is the PRIMARY KEY / authoritative identity.

Covers the 16 required verifications:
   1  user_id is the actual database primary key
   2  user_id is unique
   3  duplicate usernames are allowed
   4  user_id cannot be changed after creation
   5  existing users are preserved (migration)
   6  existing tasks are preserved (migration)
   7  existing audit records are preserved (migration)
   8  task ownership still works
   9  manager supervision still works
  10  admin supervision still works
  11  authentication still works
  12  signup role + user_id validation still works
  13  username changes preserve user_id
  14  no existing data is lost (migration counts)
  15  backend starts successfully
  16  frontend build succeeds (verified separately via `npm run build`)
"""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal, engine
from app.models.task import TaskPassportRow
from app.models.user import UserRow
from app.schemas.auth import Role
from app.services.user_service import user_service

BACKEND_DIR = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# 1. user_id is the actual database primary key
# ---------------------------------------------------------------------------

def test_user_id_is_database_primary_key():
    pk_cols = [c.name for c in UserRow.__table__.primary_key]
    assert pk_cols == ["user_id"]
    assert UserRow.__table__.c.user_id.primary_key is True

    insp = inspect(engine)
    pk = insp.get_pk_constraint("users")
    assert pk["constrained_columns"] == ["user_id"]
    assert "id" not in {c["name"] for c in insp.get_columns("users")}


# ---------------------------------------------------------------------------
# 2. user_id is unique
# ---------------------------------------------------------------------------

def test_user_id_is_unique():
    db = SessionLocal()
    try:
        user_service.register(db, "unique-a", "password123", Role.OPERATOR, user_id="ZZ000001")
        with pytest.raises(IntegrityError):
            user_service.register(db, "unique-b", "password123", Role.OPERATOR, user_id="ZZ000001")
        db.rollback()
        assert db.query(UserRow).filter(UserRow.user_id == "ZZ000001").count() == 1
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 3. duplicate usernames are allowed
# ---------------------------------------------------------------------------

def test_duplicate_usernames_allowed():
    db = SessionLocal()
    try:
        u1 = user_service.register(db, "dupename", "password123", Role.OPERATOR, user_id="DU000001")
        u2 = user_service.register(db, "dupename", "password123", Role.MONITOR, user_id="DU000002")
        assert u1.user_id != u2.user_id
        assert u1.role != u2.role
        count = db.query(UserRow).filter(UserRow.username == "dupename").count()
        assert count == 2
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 4. user_id cannot be changed after creation
# ---------------------------------------------------------------------------

def test_user_id_immutable_after_creation():
    db = SessionLocal()
    try:
        user = user_service.register(db, "immuser", "password123", Role.OPERATOR, user_id="IM000001")
        original = user.user_id
        user.user_id = "IM000002"
        with pytest.raises(ValueError, match="immutable"):
            db.flush()
        db.rollback()
        db.expire_all()
        assert db.query(UserRow).filter(UserRow.user_id == original).count() == 1
        assert db.query(UserRow).filter(UserRow.user_id == "IM000002").count() == 0
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 11. authentication still works
# ---------------------------------------------------------------------------

def test_authentication_still_works(client: TestClient):
    resp = client.post(
        "/api/auth/login",
        json={"username": "operator", "password": "medha-operator-2026"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    me = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["user_id"] == "USR-00000001"
    assert body["role"] == "operator"


# ---------------------------------------------------------------------------
# 12. signup role + user_id validation still works
# ---------------------------------------------------------------------------

def test_signup_role_and_user_id_validation(client: TestClient):
    # Unknown user_id → 403
    r = client.post("/api/auth/register", json={
        "username": "bogus.user", "password": "secret123",
        "user_id": "XX99999", "role": "operator",
    })
    assert r.status_code == 403, r.text

    # user_id + wrong role → 403
    r = client.post("/api/auth/register", json={
        "username": "wrong.role", "password": "secret123",
        "user_id": "OP00303", "role": "admin",
    })
    assert r.status_code == 403, r.text

    # user_id already registered (seeded) → 409
    r = client.post("/api/auth/register", json={
        "username": "already.used", "password": "secret123",
        "user_id": "OP00303", "role": "operator",
    })
    assert r.status_code == 409, r.text


# ---------------------------------------------------------------------------
# 13. username changes preserve user_id
# ---------------------------------------------------------------------------

def test_username_change_preserves_user_id(client: TestClient, auth_headers: dict):
    me1 = client.get("/api/auth/me", headers=auth_headers)
    assert me1.status_code == 200, me1.text
    original_uid = me1.json()["user_id"]
    assert original_uid == "USR-00000001"

    r = client.patch(
        "/api/auth/username",
        json={"username": "operator.renamed"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["user_id"] == original_uid
    assert r.json()["username"] == "operator.renamed"

    me2 = client.get("/api/auth/me", headers=auth_headers)
    assert me2.json()["user_id"] == original_uid
    assert me2.json()["username"] == "operator.renamed"

    # Restore so other tests / seeding stay consistent within this test DB
    client.patch(
        "/api/auth/username",
        json={"username": "operator"},
        headers=auth_headers,
    )


# ---------------------------------------------------------------------------
# 8. task ownership still works (owner keyed by user_id)
# ---------------------------------------------------------------------------

def test_task_ownership_by_user_id(client: TestClient, auth_headers: dict):
    r = client.post("/api/tasks", json={
        "title": "Ownership check",
        "purpose": "verify task ownership resolves via user_id",
        "allowed_tools": ["document_reader"],
    }, headers=auth_headers)
    assert r.status_code == 201, r.text
    task = r.json()
    assert task["user_id"] == "USR-00000001"

    listing = client.get("/api/tasks", headers=auth_headers)
    assert listing.status_code == 200, listing.text
    ids = [t["task_id"] for t in listing.json()]
    assert task["task_id"] in ids

    # Another worker must not see it
    other = client.post("/api/auth/login", json={
        "username": "engineer", "password": "medha-engineer-2026",
    })
    other_h = {"Authorization": f"Bearer {other.json()['access_token']}"}
    detail = client.get(f"/api/tasks/{task['task_id']}", headers=other_h)
    assert detail.status_code == 403, detail.text


# ---------------------------------------------------------------------------
# 9 + 10. manager / admin supervision still works (resolved via user_id)
# ---------------------------------------------------------------------------

def _login(client: TestClient, username: str, password: str) -> dict:
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_manager_supervision_via_user_id(client: TestClient):
    balaji = _login(client, "Balaji", "medha-balaji-2026")
    ali = _login(client, "Ali", "medha-ali-2026")

    r = client.post("/api/tasks", json={
        "title": "Supervised by manager",
        "purpose": "manager supervision resolves through user_id",
        "approval_requirement": "reviewer",
        "allowed_tools": ["document_reader"],
    }, headers=balaji)
    assert r.status_code == 201, r.text
    task_id = r.json()["task_id"]
    assert r.json()["user_id"] == "OP00303"

    listing = client.get("/api/supervision/tasks", headers=ali)
    assert listing.status_code == 200, listing.text
    supervised_ids = [t["task_id"] for t in listing.json()["tasks"]]
    assert task_id in supervised_ids

    detail = client.get(f"/api/supervision/tasks/{task_id}", headers=ali)
    assert detail.status_code == 200, detail.text
    assert detail.json()["task"]["user_id"] == "OP00303"

    # Manager (MD00574) can approve the supervised worker task
    me = client.get("/api/auth/me", headers=ali).json()
    assert me["user_id"] == "MD00574"

    r = client.patch(f"/api/tasks/{task_id}/status",
                     json={"new_status": "pending_approval", "detail": "submit"},
                     headers=balaji)
    assert r.status_code == 200, r.text
    approve = client.post(f"/api/supervision/tasks/{task_id}/approve", headers=ali)
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "authorized"


def test_admin_supervision_via_user_id(client: TestClient):
    keerthi = _login(client, "keerthi", "medha-keerthi-2026")
    lokesh = _login(client, "lokesh", "medha-lokesh-2026")

    r = client.post("/api/tasks", json={
        "title": "Supervised by admin",
        "purpose": "admin supervision resolves through user_id",
        "approval_requirement": "reviewer",
        "allowed_tools": ["document_reader"],
    }, headers=keerthi)
    assert r.status_code == 201, r.text
    task_id = r.json()["task_id"]
    assert r.json()["user_id"] == "JE00589"

    listing = client.get("/api/supervision/tasks", headers=lokesh)
    assert listing.status_code == 200, listing.text
    supervised_ids = [t["task_id"] for t in listing.json()["tasks"]]
    assert task_id in supervised_ids

    me = client.get("/api/auth/me", headers=lokesh).json()
    assert me["user_id"] == "AD00637"
    assert me["role"] == "admin"


# ---------------------------------------------------------------------------
# 15. backend starts successfully
# ---------------------------------------------------------------------------

def test_backend_starts_successfully(client: TestClient):
    r = client.get("/")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "running"
    # Startup ran init_db + seed: the six demo users must exist
    db = SessionLocal()
    try:
        for uid in ("SE00503", "AD00637", "MD00574", "OP00303", "JE00589", "MO00579"):
            assert user_service.get_by_user_id(db, uid) is not None, uid
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 5 + 6 + 7 + 14. migration preserves existing users/tasks/audit records
# ---------------------------------------------------------------------------

_LEGACY_USERS = [
    # (legacy id, user_id, username, role)
    (1, "USR-00000001", "operator", "operator"),
    (2, "USR-00000004", "ali", "admin"),
    (3, "MD00574", "Ali", "manager"),
    (4, "OP00303", "Balaji", "operator"),
    (5, "JE00589", "keerthi", "junior_engineer"),
]

_LEGACY_TASKS = [
    ("task-legacy-1", "USR-00000001", "Legacy task one"),
    ("task-legacy-2", "OP00303", "Legacy task two"),
]

_LEGACY_AUDITS = [
    ("evt-legacy-1", "passport_created", "task-legacy-1", "USR-00000001"),
    ("evt-legacy-2", "passport_status_transition", "task-legacy-2", "OP00303"),
]


def _seed_legacy_db(path: Path, with_unique_username_index: bool) -> None:
    con = sqlite3.connect(path)
    cur = con.cursor()
    cur.execute(
        "CREATE TABLE users ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " username VARCHAR(100) NOT NULL,"
        " password_hash VARCHAR(200) NOT NULL,"
        " role VARCHAR(30) NOT NULL DEFAULT 'operator',"
        " user_id VARCHAR(20),"
        " preferred_security_mode VARCHAR(20) DEFAULT 'standard'"
        ")"
    )
    if with_unique_username_index:
        cur.execute("CREATE UNIQUE INDEX ix_users_username ON users (username)")
    for uid, user_id, username, role in _LEGACY_USERS:
        cur.execute(
            "INSERT INTO users (id, user_id, username, password_hash, role) "
            "VALUES (?, ?, ?, ?, ?)",
            (uid, user_id, username, "legacy-hash", role),
        )

    cur.execute(
        "CREATE TABLE task_passports ("
        " task_id VARCHAR(36) PRIMARY KEY,"
        " user_id VARCHAR(100) NOT NULL,"
        " identity VARCHAR(100) NOT NULL,"
        " role VARCHAR(30) NOT NULL,"
        " title VARCHAR(200) NOT NULL,"
        " purpose VARCHAR(500) NOT NULL,"
        " status VARCHAR(20) NOT NULL DEFAULT 'draft'"
        ")"
    )
    for task_id, user_id, title in _LEGACY_TASKS:
        cur.execute(
            "INSERT INTO task_passports (task_id, user_id, identity, role, title, purpose, status) "
            "VALUES (?, ?, ?, ?, ?, ?, 'draft')",
            (task_id, user_id, "legacy", "operator", title, "legacy purpose"),
        )

    cur.execute(
        "CREATE TABLE audit_events ("
        " event_id VARCHAR(36) PRIMARY KEY,"
        " timestamp DATETIME,"
        " event_type VARCHAR(100) NOT NULL,"
        " task_id VARCHAR(36) NOT NULL,"
        " user_id VARCHAR(100) NOT NULL,"
        " identity VARCHAR(100) NOT NULL,"
        " role VARCHAR(30) NOT NULL,"
        " previous_status VARCHAR(20),"
        " new_status VARCHAR(20),"
        " detail TEXT"
        ")"
    )
    for event_id, event_type, task_id, user_id in _LEGACY_AUDITS:
        cur.execute(
            "INSERT INTO audit_events (event_id, event_type, task_id, user_id, identity, role, detail) "
            "VALUES (?, ?, ?, ?, ?, ?, '')",
            (event_id, event_type, task_id, user_id, "legacy", "operator"),
        )

    cur.execute(
        "CREATE TABLE conversations ("
        " id VARCHAR(36) PRIMARY KEY,"
        " task_id VARCHAR(36) NOT NULL,"
        " user_id VARCHAR(100) NOT NULL,"
        " title VARCHAR(200) NOT NULL DEFAULT 'New Conversation',"
        " created_at DATETIME,"
        " updated_at DATETIME"
        ")"
    )
    cur.execute(
        "INSERT INTO conversations (id, task_id, user_id, title) "
        "VALUES ('conv-1', 'task-legacy-1', 'USR-00000001', 'Legacy chat')"
    )
    con.commit()
    con.close()


def _run_migration(db_path: Path) -> None:
    env = os.environ.copy()
    env["MEDHA_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    env["MEDHA_JWT_SECRET"] = "test-only-jwt-secret-not-for-production"
    env["MEDHA_ENV"] = "test"
    result = subprocess.run(
        [sys.executable, "-c", "from app.core.database import init_db; init_db()"],
        cwd=str(BACKEND_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"migration failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def _assert_migrated(db_path: Path) -> None:
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    # 1. user_id is the primary key; legacy numeric id is gone
    cols = {row[1]: row for row in cur.execute("PRAGMA table_info(users)").fetchall()}
    assert "id" not in cols, "legacy numeric users.id must be dropped"
    assert "user_id" in cols
    assert cols["user_id"][5] == 1, "user_id must be the primary key column"

    # 5 + 14. existing users preserved (counts + values)
    users = cur.execute(
        "SELECT user_id, username, role FROM users ORDER BY user_id"
    ).fetchall()
    expected_users = sorted((u[1], u[2], u[3]) for u in _LEGACY_USERS)
    assert users == expected_users, f"users mismatch: {users} != {expected_users}"

    # 6. existing tasks preserved and still owned by the same user_id
    tasks = cur.execute(
        "SELECT task_id, user_id FROM task_passports ORDER BY task_id"
    ).fetchall()
    expected_tasks = sorted((t[0], t[1]) for t in _LEGACY_TASKS)
    assert tasks == expected_tasks, f"tasks mismatch: {tasks} != {expected_tasks}"

    # 7. existing audit records preserved with same actor user_id
    audits = cur.execute(
        "SELECT event_id, user_id FROM audit_events ORDER BY event_id"
    ).fetchall()
    expected_audits = sorted((a[0], a[3]) for a in _LEGACY_AUDITS)
    assert audits == expected_audits, f"audits mismatch: {audits} != {expected_audits}"

    # conversations preserved
    conv = cur.execute(
        "SELECT id, user_id FROM conversations ORDER BY id"
    ).fetchall()
    assert conv == [("conv-1", "USR-00000001")]

    # No orphaned task owners: every owner resolves to a users row
    orphans = cur.execute(
        "SELECT COUNT(*) FROM task_passports tp "
        "WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.user_id = tp.user_id)"
    ).fetchone()[0]
    assert orphans == 0

    con.close()


@pytest.mark.parametrize("with_unique_username_index", [False, True])
def test_migration_preserves_existing_data(tmp_path: Path, with_unique_username_index: bool):
    db_path = tmp_path / f"legacy_{'uniq' if with_unique_username_index else 'plain'}.db"
    _seed_legacy_db(db_path, with_unique_username_index)
    _run_migration(db_path)
    _assert_migrated(db_path)
    # Idempotent: a second startup migration must not alter or lose data
    _run_migration(db_path)
    _assert_migrated(db_path)
