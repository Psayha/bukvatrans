"""FastAPI integration tests for auth and admin routes."""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db, require_admin
from src.api.main import app
from src.db.models.user import User


# ── helpers ────────────────────────────────────────────────────────────────


def _make_admin_user() -> User:
    return User(
        id=999999999,
        username="admin",
        first_name="Admin",
        is_admin=True,
        balance_seconds=0,
        free_uses_left=0,
    )


@pytest_asyncio.fixture
async def admin_client(db_session: AsyncSession):
    """AsyncClient with get_db and require_admin overridden for test session."""
    admin = _make_admin_user()

    async def override_db():
        yield db_session

    async def override_admin():
        return admin

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_admin] = override_admin

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_admin, None)


@pytest_asyncio.fixture
async def authed_client(db_session: AsyncSession, test_user: User):
    """AsyncClient with get_db overridden; test_user injected as current user."""
    from src.api.dependencies import get_current_user

    async def override_db():
        yield db_session

    async def override_user():
        return test_user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


# ── auth config ────────────────────────────────────────────────────────────


class TestAuthConfig:
    @pytest.mark.asyncio
    async def test_config_returns_bot_username(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/auth/config")
        assert resp.status_code == 200
        assert "bot_username" in resp.json()


# ── login / refresh ────────────────────────────────────────────────────────


class TestEmailAuth:
    @pytest.mark.asyncio
    async def test_login_success(self, db_session: AsyncSession):
        from src.api.auth import hash_password

        user = User(
            id=20000000000001,
            email="test@example.com",
            password_hash=hash_password("Password1!"),
            first_name="LoginTest",
            balance_seconds=0,
            free_uses_left=0,
        )
        db_session.add(user)
        await db_session.commit()

        async def override_db():
            yield db_session

        app.dependency_overrides[get_db] = override_db
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/v1/auth/login",
                    json={"email": "test@example.com", "password": "Password1!"},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert "access_token" in data
            assert "refresh_token" in data
            assert data["user"]["email"] == "test@example.com"
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, db_session: AsyncSession):
        from src.api.auth import hash_password

        user = User(
            id=20000000000002,
            email="wrong@example.com",
            password_hash=hash_password("correct"),
            first_name="Wrong",
            balance_seconds=0,
            free_uses_left=0,
        )
        db_session.add(user)
        await db_session.commit()

        async def override_db():
            yield db_session

        app.dependency_overrides[get_db] = override_db
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/v1/auth/login",
                    json={"email": "wrong@example.com", "password": "badpassword"},
                )
            assert resp.status_code == 401
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_login_unknown_email(self, db_session: AsyncSession):
        async def override_db():
            yield db_session

        app.dependency_overrides[get_db] = override_db
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/v1/auth/login",
                    json={"email": "nobody@example.com", "password": "somepass"},
                )
            assert resp.status_code == 401
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_refresh_valid_token(self, db_session: AsyncSession):
        from src.api.auth import create_refresh_token, hash_password

        user = User(
            id=20000000000003,
            email="refresh@example.com",
            password_hash=hash_password("somepass"),
            first_name="RefreshTest",
            balance_seconds=0,
            free_uses_left=0,
        )
        db_session.add(user)
        await db_session.commit()

        async def override_db():
            yield db_session

        app.dependency_overrides[get_db] = override_db
        try:
            token = create_refresh_token(user_id=user.id)
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/v1/auth/refresh",
                    json={"refresh_token": token},
                )
            assert resp.status_code == 200
            assert "access_token" in resp.json()
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": "garbage.token.here"},
            )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_banned_user_cannot_login(self, db_session: AsyncSession):
        from src.api.auth import hash_password

        user = User(
            id=20000000000004,
            email="banned@example.com",
            password_hash=hash_password("pass"),
            first_name="Banned",
            is_banned=True,
            balance_seconds=0,
            free_uses_left=0,
        )
        db_session.add(user)
        await db_session.commit()

        async def override_db():
            yield db_session

        app.dependency_overrides[get_db] = override_db
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/v1/auth/login",
                    json={"email": "banned@example.com", "password": "pass"},
                )
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(get_db, None)


# ── admin stats ────────────────────────────────────────────────────────────


class TestAdminStats:
    @pytest.mark.asyncio
    async def test_stats_returns_structure(self, admin_client):
        resp = await admin_client.get("/api/admin/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "users" in data
        assert "transcriptions" in data
        assert "revenue" in data
        assert "total" in data["users"]
        assert "done_24h" in data["transcriptions"]

    @pytest.mark.asyncio
    async def test_revenue_chart_returns_data_key(self, admin_client):
        resp = await admin_client.get("/api/admin/stats/revenue?days=7")
        assert resp.status_code == 200
        assert "data" in resp.json()

    @pytest.mark.asyncio
    async def test_users_growth_chart(self, admin_client):
        resp = await admin_client.get("/api/admin/stats/users-growth?days=7")
        assert resp.status_code == 200
        assert "data" in resp.json()

    @pytest.mark.asyncio
    async def test_stats_without_auth_rejected(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/admin/stats")
        assert resp.status_code in (401, 403, 422)


# ── admin users ────────────────────────────────────────────────────────────


class TestAdminUsers:
    @pytest.mark.asyncio
    async def test_list_users_empty(self, admin_client):
        resp = await admin_client.get("/api/admin/users")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_list_users_with_test_user(self, admin_client, test_user):
        resp = await admin_client.get("/api/admin/users")
        assert resp.status_code == 200
        ids = [u["id"] for u in resp.json()["items"]]
        assert test_user.id in ids

    @pytest.mark.asyncio
    async def test_get_user_detail(self, admin_client, test_user):
        resp = await admin_client.get(f"/api/admin/users/{test_user.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == test_user.id
        assert "recent_transcriptions" in data
        assert "recent_transactions" in data

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, admin_client):
        resp = await admin_client.get("/api/admin/users/9999999999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_patch_user_ban(self, admin_client, test_user):
        resp = await admin_client.patch(
            f"/api/admin/users/{test_user.id}",
            json={"is_banned": True},
        )
        assert resp.status_code == 200
        assert resp.json()["is_banned"] is True

    @pytest.mark.asyncio
    async def test_patch_user_add_balance(self, admin_client, test_user):
        initial = test_user.balance_seconds
        resp = await admin_client.patch(
            f"/api/admin/users/{test_user.id}",
            json={"add_balance_seconds": 3600},
        )
        assert resp.status_code == 200
        assert resp.json()["balance_seconds"] == initial + 3600

    @pytest.mark.asyncio
    async def test_list_users_search(self, admin_client, test_user):
        resp = await admin_client.get(f"/api/admin/users?q={test_user.username}")
        assert resp.status_code == 200
        data = resp.json()
        assert any(u["username"] == test_user.username for u in data["items"])


# ── admin promo codes ──────────────────────────────────────────────────────


class TestAdminPromoCodes:
    @pytest.mark.asyncio
    async def test_list_empty(self, admin_client):
        resp = await admin_client.get("/api/admin/promo-codes")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_create_promo_code(self, admin_client):
        resp = await admin_client.post(
            "/api/admin/promo-codes",
            json={"code": "TESTCODE2025", "type": "free_seconds", "value": 3600},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["code"] == "TESTCODE2025"
        assert data["value"] == 3600
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_create_duplicate_fails(self, admin_client):
        await admin_client.post(
            "/api/admin/promo-codes",
            json={"code": "DUPCODE", "type": "free_seconds", "value": 1800},
        )
        resp = await admin_client.post(
            "/api/admin/promo-codes",
            json={"code": "DUPCODE", "type": "free_seconds", "value": 1800},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_patch_deactivate(self, admin_client):
        create_resp = await admin_client.post(
            "/api/admin/promo-codes",
            json={"code": "DEACTIVATE", "type": "free_seconds", "value": 7200},
        )
        promo_id = create_resp.json()["id"]

        resp = await admin_client.patch(
            f"/api/admin/promo-codes/{promo_id}",
            json={"is_active": False},
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    @pytest.mark.asyncio
    async def test_patch_nonexistent(self, admin_client):
        resp = await admin_client.patch(
            "/api/admin/promo-codes/999999",
            json={"is_active": False},
        )
        assert resp.status_code == 404


# ── v1 transcriptions ──────────────────────────────────────────────────────


class TestV1Transcriptions:
    @pytest.mark.asyncio
    async def test_list_empty(self, authed_client):
        resp = await authed_client.get("/api/v1/transcriptions")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_get_not_found(self, authed_client):
        resp = await authed_client.get("/api/v1/transcriptions/nonexistent-id")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_url_submission_blocked_url(self, authed_client):
        resp = await authed_client.post(
            "/api/v1/transcriptions/url",
            json={"url": "http://192.168.1.1/evil.mp3"},
        )
        assert resp.status_code == 422


# ── admin transactions ─────────────────────────────────────────────────────


class TestAdminTransactions:
    @pytest.mark.asyncio
    async def test_list_empty(self, admin_client):
        resp = await admin_client.get("/api/admin/transactions")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_with_type_filter(self, admin_client):
        resp = await admin_client.get("/api/admin/transactions?type=subscription")
        assert resp.status_code == 200
        assert "items" in resp.json()

    @pytest.mark.asyncio
    async def test_list_with_status_filter(self, admin_client):
        resp = await admin_client.get("/api/admin/transactions?status=success")
        assert resp.status_code == 200
        assert "items" in resp.json()

    @pytest.mark.asyncio
    async def test_list_with_user_filter(self, admin_client, test_user):
        resp = await admin_client.get(f"/api/admin/transactions?user_id={test_user.id}")
        assert resp.status_code == 200
        assert "items" in resp.json()


# ── admin transcriptions ───────────────────────────────────────────────────


class TestAdminTranscriptions:
    @pytest.mark.asyncio
    async def test_list_empty(self, admin_client):
        resp = await admin_client.get("/api/admin/transcriptions")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_with_status_filter(self, admin_client):
        resp = await admin_client.get("/api/admin/transcriptions?status=done")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_with_source_type_filter(self, admin_client):
        resp = await admin_client.get("/api/admin/transcriptions?source_type=youtube")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_not_found(self, admin_client):
        resp = await admin_client.get("/api/admin/transcriptions/nonexistent-id")
        assert resp.status_code == 404


# ── v1 profile ─────────────────────────────────────────────────────────────


class TestV1Profile:
    @pytest.mark.asyncio
    async def test_get_profile(self, authed_client, test_user):
        resp = await authed_client.get("/api/v1/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == test_user.id
        assert "balance_seconds" in data
        assert "gamification" in data
        assert "active_subscription" in data

    @pytest.mark.asyncio
    async def test_profile_gamification_fields(self, authed_client):
        resp = await authed_client.get("/api/v1/profile")
        assert resp.status_code == 200
        gam = resp.json()["gamification"]
        assert "level_name" in gam
        assert "progress_ratio" in gam


# ── v1 promo code apply ────────────────────────────────────────────────────


class TestV1Promo:
    @pytest.mark.asyncio
    async def test_apply_invalid_code(self, authed_client):
        resp = await authed_client.post(
            "/api/v1/promo",
            json={"code": "DOESNOTEXIST"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_apply_valid_code(self, authed_client, db_session, test_user):
        from src.db.models.promo_code import PromoCode

        pc = PromoCode(
            code="VALIDCODE",
            type="free_seconds",
            value=3600,
            is_active=True,
        )
        db_session.add(pc)
        await db_session.commit()

        resp = await authed_client.post(
            "/api/v1/promo",
            json={"code": "VALIDCODE"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["seconds_added"] == 3600

    @pytest.mark.asyncio
    async def test_apply_same_code_twice_rejected(self, authed_client, db_session, test_user):
        from src.db.models.promo_code import PromoCode

        pc = PromoCode(
            code="ONCECODE",
            type="free_seconds",
            value=1800,
            is_active=True,
        )
        db_session.add(pc)
        await db_session.commit()

        await authed_client.post("/api/v1/promo", json={"code": "ONCECODE"})
        resp = await authed_client.post("/api/v1/promo", json={"code": "ONCECODE"})
        assert resp.status_code == 400


# ── admin broadcast ────────────────────────────────────────────────────────


class TestAdminBroadcast:
    @pytest.mark.asyncio
    async def test_send_queues_background_task(self, admin_client):
        """POST /broadcast should accept and queue without hitting the DB."""
        resp = await admin_client.post(
            "/api/admin/broadcast",
            json={"text": "Hello everyone!", "target": "all"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    @pytest.mark.asyncio
    async def test_send_empty_text_rejected(self, admin_client):
        resp = await admin_client.post(
            "/api/admin/broadcast",
            json={"text": "   ", "target": "all"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_send_without_auth_rejected(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/admin/broadcast",
                json={"text": "Hi", "target": "all"},
            )
        assert resp.status_code in (401, 403, 422)
