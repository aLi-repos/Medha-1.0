"""Tests for startup behavior, SQLite persistence, demo user seeding,
CORS, and frontend/backend integration correctness.
"""

import os

import pytest
from fastapi.testclient import TestClient


# ── 1. Backend starts successfully with valid .env ──


def test_backend_starts_and_health_check(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── 2. Missing MEDHA_JWT_SECRET fails safely ──


def test_missing_jwt_secret_raises_runtime_error() -> None:
    """Verify _required_environment_value raises when MEDHA_JWT_SECRET is missing."""
    from app.core.config import _required_environment_value

    saved = os.environ.pop("MEDHA_JWT_SECRET", None)
    try:
        with pytest.raises(RuntimeError, match="MEDHA_JWT_SECRET"):
            _required_environment_value("MEDHA_JWT_SECRET")
    finally:
        if saved is not None:
            os.environ["MEDHA_JWT_SECRET"] = saved


# ── 3. CORS preflight succeeds ──


def test_cors_preflight_succeeds() -> None:
    """OPTIONS preflight from the frontend origin must return 200 with CORS headers."""
    with TestClient(app=__import__("app.main", fromlist=["app"]).app) as c:
        resp = c.options(
            "/api/auth/login",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type,Authorization",
            },
        )
        # CORS middleware should respond with 200 or 204 and CORS headers
        assert resp.status_code in (200, 204)
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
        assert resp.headers.get("access-control-allow-credentials") == "true"


def test_cors_preflight_127_0_0_1() -> None:
    """OPTIONS preflight from 127.0.0.1 origin must also succeed."""
    with TestClient(app=__import__("app.main", fromlist=["app"]).app) as c:
        resp = c.options(
            "/api/auth/login",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        assert resp.status_code in (200, 204)
        assert resp.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"


def test_cors_rejects_unknown_origin() -> None:
    """Requests from an unknown origin should NOT get CORS headers."""
    with TestClient(app=__import__("app.main", fromlist=["app"]).app) as c:
        resp = c.options(
            "/api/auth/login",
            headers={
                "Origin": "http://evil.example.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        # The middleware should not include allow-origin for unknown origins
        assert resp.headers.get("access-control-allow-origin") != "http://evil.example.com"


# ── 4/5/6. Demo user login succeeds ──


def test_operator_login_succeeds(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/login",
        json={"username": "operator", "password": "medha-operator-2026"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()
    assert resp.json()["token_type"] == "bearer"


def test_engineer_login_succeeds(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/login",
        json={"username": "engineer", "password": "medha-engineer-2026"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_reviewer_login_succeeds(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/login",
        json={"username": "reviewer", "password": "medha-reviewer-2026"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_admin_login_succeeds(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "medha-admin-2026"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


# ── 7. Wrong password returns proper error ──


def test_wrong_password_returns_401(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/login",
        json={"username": "operator", "password": "wrong-password"},
    )
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid username or password"}


# ── 8. Unknown user returns proper error ──


def test_unknown_user_returns_401(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/login",
        json={"username": "nonexistent-user", "password": "any-password"},
    )
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid username or password"}


# ── 9. JWT token authenticates a protected endpoint ──


def test_jwt_authenticates_protected_endpoint(client: TestClient) -> None:
    login_resp = client.post(
        "/api/auth/login",
        json={"username": "operator", "password": "medha-operator-2026"},
    )
    token = login_resp.json()["access_token"]

    me_resp = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "operator"
    assert me_resp.json()["role"] == "operator"


# ── 10/11. SQLite data persists across restart ──


def test_sqlite_data_persists_across_backend_restart() -> None:
    """Create a user via one TestClient instance, verify they exist in another.

    Simulates a backend restart by creating two separate TestClient instances
    that share the same file-based SQLite database.
    """
    import tempfile
    import shutil

    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "persist_test.db")
    db_url = f"sqlite:///{db_path}"

    # Save and override env
    saved_url = os.environ.get("MEDHA_DATABASE_URL")
    saved_secret = os.environ.get("MEDHA_JWT_SECRET")
    os.environ["MEDHA_DATABASE_URL"] = db_url
    os.environ.setdefault("MEDHA_JWT_SECRET", "persistence-test-secret")

    try:
        # First backend instance: start, seed users, create a task
        from app.core.database import Base, engine as fresh_engine
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        test_engine = create_engine(db_url, connect_args={"check_same_thread": False})
        TestSession = sessionmaker(bind=test_engine)

        # Create tables
        Base.metadata.create_all(bind=test_engine)

        # Seed a user manually (simulating startup)
        from app.services.user_service import user_service
        from app.schemas.auth import Role

        db = TestSession()
        try:
            user_service.seed_demo_users(db)
            assert user_service.get_by_username(db, "operator") is not None
        finally:
            db.close()

        # Second backend instance: verify users still exist (simulates restart)
        db2 = TestSession()
        try:
            user = user_service.get_by_username(db2, "operator")
            assert user is not None
            assert user.username == "operator"
            assert user.role == "operator"

            # Verify password still works
            from app.services.user_service import _verify_password
            assert _verify_password("medha-operator-2026", user.password_hash)
        finally:
            db2.close()
    finally:
        # Restore env
        if saved_url is not None:
            os.environ["MEDHA_DATABASE_URL"] = saved_url
        elif "MEDHA_DATABASE_URL" in os.environ:
            del os.environ["MEDHA_DATABASE_URL"]
        if saved_secret is not None:
            os.environ["MEDHA_JWT_SECRET"] = saved_secret
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── 12. Duplicate seeding does not create duplicate users ──


def test_duplicate_seeding_does_not_create_duplicates(client: TestClient) -> None:
    """Calling seed_demo_users multiple times should not create duplicates."""
    from app.services.user_service import user_service
    from app.core.database import SessionLocal

    # Seed is called on startup; call it again manually
    db = SessionLocal()
    try:
        # Count users before
        from app.models.user import UserRow
        count_before = db.query(UserRow).count()

        # Seed again
        user_service.seed_demo_users(db)

        # Count should not change
        count_after = db.query(UserRow).count()
        assert count_after == count_before

        # Verify the operator user is still unique
        from sqlalchemy import text
        result = db.execute(
            text("SELECT COUNT(*) FROM users WHERE username = 'operator'")
        ).scalar()
        assert result == 1
    finally:
        db.close()


# ── 13. All 4 demo users exist with correct roles ──


def test_all_demo_users_exist_with_correct_roles(client: TestClient) -> None:
    from app.services.user_service import user_service
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        for uname, expected_role in [
            ("operator", "operator"),
            ("engineer", "engineer"),
            ("reviewer", "reviewer"),
            ("admin", "admin"),
        ]:
            user = user_service.get_by_username(db, uname)
            assert user is not None, f"Demo user '{uname}' not found"
            assert user.role == expected_role, (
                f"User '{uname}' has role '{user.role}', expected '{expected_role}'"
            )
    finally:
        db.close()


# ── 14. First startup creates missing demo users ──


def test_first_startup_creates_missing_demo_users() -> None:
    """Seed on an empty DB creates all 5 demo users with correct IDs."""
    from app.services.user_service import user_service
    from app.models.user import UserRow
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.database import Base

    eng = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    TestSession = sessionmaker(bind=eng)
    db = TestSession()
    try:
        user_service.seed_demo_users(db)
        for uid, uname, role_val in [
            ("USR-00000001", "operator", "operator"),
            ("USR-00000002", "engineer", "engineer"),
            ("USR-00000003", "reviewer", "reviewer"),
            ("USR-00000004", "admin", "admin"),
            ("USR-00000005", "arun.maintenance", "engineer"),
            ("SE00503", "nagarjuna", "senior_engineer"),
            ("AD00637", "lokesh", "admin"),
            ("MD00574", "Ali", "manager"),
            ("OP00303", "Balaji", "operator"),
            ("JE00589", "keerthi", "junior_engineer"),
            ("MO00579", "saniya", "monitor"),
        ]:
            row = db.query(UserRow).filter(UserRow.user_id == uid).first()
            assert row is not None, f"User {uid} not created"
            assert row.username == uname
            assert row.role == role_val
    finally:
        db.close()


# ── 15. Second startup does not create duplicates ──


def test_second_startup_does_not_create_duplicates() -> None:
    """Calling seed_demo_users twice does not create duplicate rows."""
    from app.services.user_service import user_service
    from app.models.user import UserRow
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.database import Base

    eng = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    TestSession = sessionmaker(bind=eng)
    db = TestSession()
    try:
        user_service.seed_demo_users(db)
        count_after_first = db.query(UserRow).count()
        user_service.seed_demo_users(db)
        count_after_second = db.query(UserRow).count()
        assert count_after_second == count_after_first
    finally:
        db.close()


# ── 16. Existing USR-00000004/admin is preserved ──


def test_existing_admin_user_preserved_on_reseed() -> None:
    """If admin user already exists with USR-00000004, re-seeding preserves it."""
    from app.services.user_service import user_service
    from app.models.user import UserRow
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.database import Base

    eng = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    TestSession = sessionmaker(bind=eng)
    db = TestSession()
    try:
        user_service.seed_demo_users(db)
        admin = db.query(UserRow).filter(UserRow.user_id == "USR-00000004").first()
        assert admin is not None
        assert admin.username == "admin"
        assert admin.role == "admin"
        original_hash = admin.password_hash

        user_service.seed_demo_users(db)
        admin2 = db.query(UserRow).filter(UserRow.user_id == "USR-00000004").first()
        assert admin2.password_hash == original_hash
        assert admin2.role == "admin"
    finally:
        db.close()


# ── 17. Existing user data is not overwritten ──


def test_existing_user_data_not_overwritten() -> None:
    """If a demo user was renamed, re-seeding does not overwrite the new username."""
    from app.services.user_service import user_service
    from app.models.user import UserRow
    from app.schemas.auth import Role
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.database import Base

    eng = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    TestSession = sessionmaker(bind=eng)
    db = TestSession()
    try:
        user_service.seed_demo_users(db)
        admin = db.query(UserRow).filter(UserRow.user_id == "USR-00000004").first()
        admin.username = "superadmin"
        db.commit()

        user_service.seed_demo_users(db)
        admin2 = db.query(UserRow).filter(UserRow.user_id == "USR-00000004").first()
        assert admin2.username == "superadmin", "Renamed username was overwritten"
    finally:
        db.close()


# ── 17b. Reseeding after a username rename never creates a replacement user ──


def test_reseed_after_rename_never_creates_replacement_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Renaming a demo user and restarting (reseed) must not mint a new user.

    Regression: in development, the old seeder treated a renamed demo
    username as "missing" and created a brand-new account at the next free
    user_id, so admin → ali produced a second 'admin' user on the next
    startup.
    """
    from app.services.user_service import user_service
    from app.models.user import UserRow
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.database import Base

    # Force development so the password-refresh branch is exercised.
    class _DevSettings:
        environment = "development"

    monkeypatch.setattr("app.services.user_service.settings", _DevSettings())

    eng = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    TestSession = sessionmaker(bind=eng)
    db = TestSession()
    try:
        user_service.seed_demo_users(db)

        # Simulate the user renaming admin → ali via the account endpoint.
        admin = db.query(UserRow).filter(UserRow.user_id == "USR-00000004").first()
        admin.username = "ali"
        db.commit()

        # Restart: reseed exactly as startup does.
        user_service.seed_demo_users(db)

        # No replacement 'admin' account may be created; the renamed user
        # keeps its permanent user_id and the total user count is unchanged.
        assert db.query(UserRow).filter(UserRow.username == "admin").count() == 0
        ali = db.query(UserRow).filter(UserRow.user_id == "USR-00000004").first()
        assert ali is not None and ali.username == "ali"
        assert db.query(UserRow).count() == 11
    finally:
        db.close()


# ── 18. Seed can run repeatedly without IntegrityError ──


def test_seed_runs_repeatedly_without_integrity_error() -> None:
    """Calling seed_demo_users many times never raises IntegrityError."""
    from app.services.user_service import user_service
    from app.models.user import UserRow
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.database import Base

    eng = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    TestSession = sessionmaker(bind=eng)
    db = TestSession()
    try:
        for _ in range(5):
            user_service.seed_demo_users(db)
        assert db.query(UserRow).count() == 11
    finally:
        db.close()


# ── 19. Frontend API base URL is consistent ──


def test_frontend_uses_correct_api_base_url() -> None:
    """Verify the frontend api.js has a single API_BASE definition and no hardcoded URLs in App.jsx."""
    import re

    api_js_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "frontend", "src", "api.js"
    )
    if os.path.exists(api_js_path):
        content = open(api_js_path, encoding="utf-8").read()

        # Should have exactly one API_BASE definition
        matches = re.findall(r'const API_BASE\s*=', content)
        assert len(matches) == 1, (
            f"Expected 1 API_BASE definition, found {len(matches)}"
        )

        # Must reference 127.0.0.1:8000 somewhere (either direct or in ternary)
        assert "127.0.0.1:8000" in content, "API_BASE must reference 127.0.0.1:8000"

        # No hardcoded http://localhost:8000 URLs should remain in App.jsx
        app_jsx_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "frontend", "src", "App.jsx"
        )
        if os.path.exists(app_jsx_path):
            app_content = open(app_jsx_path, encoding="utf-8").read()
            hardcoded = re.findall(
                r'fetch\(\s*["`]http://localhost:8000', app_content
            )
            assert len(hardcoded) == 0, (
                f"App.jsx still contains {len(hardcoded)} hardcoded localhost:8000 URLs"
            )
