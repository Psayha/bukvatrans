import pytest

from src.db.repositories.user import (
    get_user, get_or_create_user, add_balance, deduct_balance, decrement_free_uses
)
from src.db.repositories.transcription import (
    create_transcription, get_transcription, update_transcription_status,
    get_cached_transcription, get_user_transcriptions
)
from src.db.repositories.transaction import (
    create_transaction, get_transaction_by_yukassa_id
)


class TestUserRepository:
    @pytest.mark.asyncio
    async def test_get_user_not_found(self, db_session):
        user = await get_user(999999, db_session)
        assert user is None

    @pytest.mark.asyncio
    async def test_create_user(self, db_session):
        user, created = await get_or_create_user(
            user_id=42,
            username="new_user",
            first_name="New",
            last_name="User",
            referrer_id=None,
            session=db_session,
        )
        assert created is True
        assert user.id == 42
        assert user.username == "new_user"
        assert user.free_uses_left == 3
        assert user.balance_seconds == 0

    @pytest.mark.asyncio
    async def test_get_existing_user(self, db_session, test_user):
        user, created = await get_or_create_user(
            user_id=test_user.id,
            username="updated",
            first_name="Updated",
            last_name=None,
            referrer_id=None,
            session=db_session,
        )
        assert created is False
        assert user.id == test_user.id

    @pytest.mark.asyncio
    async def test_add_balance(self, db_session, test_user):
        initial = test_user.balance_seconds
        user = await add_balance(test_user.id, 3600, db_session)
        assert user.balance_seconds == initial + 3600

    @pytest.mark.asyncio
    async def test_deduct_balance(self, db_session, test_user):
        initial = test_user.balance_seconds
        user = await deduct_balance(test_user.id, 3600, db_session)
        assert user.balance_seconds == initial - 3600

    @pytest.mark.asyncio
    async def test_deduct_balance_no_negative(self, db_session, test_user):
        """Balance should not go below 0."""
        user = await deduct_balance(test_user.id, 999999, db_session)
        assert user.balance_seconds == 0

    @pytest.mark.asyncio
    async def test_decrement_free_uses(self, db_session, user_with_free_uses):
        initial = user_with_free_uses.free_uses_left
        user = await decrement_free_uses(user_with_free_uses.id, db_session)
        assert user.free_uses_left == initial - 1

    @pytest.mark.asyncio
    async def test_decrement_free_uses_no_negative(self, db_session, test_user):
        """free_uses_left should not go below 0."""
        test_user.free_uses_left = 0
        await db_session.commit()
        user = await decrement_free_uses(test_user.id, db_session)
        assert user.free_uses_left == 0


class TestTranscriptionRepository:
    @pytest.mark.asyncio
    async def test_create_transcription(self, db_session, test_user):
        t = await create_transcription(
            user_id=test_user.id,
            source_type="voice",
            session=db_session,
        )
        assert t.id is not None
        assert t.status == "pending"
        assert t.user_id == test_user.id

    @pytest.mark.asyncio
    async def test_get_transcription(self, db_session, test_user):
        t = await create_transcription(
            user_id=test_user.id,
            source_type="audio",
            session=db_session,
            file_name="test.mp3",
        )
        fetched = await get_transcription(t.id, db_session)
        assert fetched is not None
        assert fetched.id == t.id

    @pytest.mark.asyncio
    async def test_get_transcription_not_found(self, db_session):
        result = await get_transcription("nonexistent-uuid", db_session)
        assert result is None

    @pytest.mark.asyncio
    async def test_update_status_to_done(self, db_session, test_user):
        t = await create_transcription(
            user_id=test_user.id,
            source_type="voice",
            session=db_session,
        )
        updated = await update_transcription_status(
            t.id, "done", db_session,
            result_text="Текст",
            duration_seconds=120,
            seconds_charged=120,
        )
        assert updated.status == "done"
        assert updated.result_text == "Текст"
        assert updated.duration_seconds == 120
        assert updated.completed_at is not None

    @pytest.mark.asyncio
    async def test_cache_returns_done_transcription(self, db_session, test_user):
        t = await create_transcription(
            user_id=test_user.id,
            source_type="audio",
            session=db_session,
            file_unique_id="unique_abc123",
        )
        await update_transcription_status(
            t.id, "done", db_session,
            result_text="Кэшированный текст",
        )
        cached = await get_cached_transcription("unique_abc123", db_session)
        assert cached is not None
        assert cached.result_text == "Кэшированный текст"

    @pytest.mark.asyncio
    async def test_cache_miss_for_different_file(self, db_session, test_user):
        t = await create_transcription(
            user_id=test_user.id,
            source_type="audio",
            session=db_session,
            file_unique_id="file_one",
        )
        await update_transcription_status(t.id, "done", db_session, result_text="Text")

        cached = await get_cached_transcription("file_two", db_session)
        assert cached is None

    @pytest.mark.asyncio
    async def test_get_user_transcriptions_limit(self, db_session, test_user):
        for i in range(15):
            await create_transcription(
                user_id=test_user.id,
                source_type="voice",
                session=db_session,
            )
        transcriptions = await get_user_transcriptions(test_user.id, db_session, limit=10)
        assert len(transcriptions) == 10


class TestTransactionRepository:
    @pytest.mark.asyncio
    async def test_create_transaction(self, db_session, test_user):
        t = await create_transaction(
            user_id=test_user.id,
            type_="topup",
            status="success",
            amount_rub=99.0,
            seconds_added=7200,
            session=db_session,
        )
        assert t.id is not None
        assert t.type == "topup"
        assert t.status == "success"

    @pytest.mark.asyncio
    async def test_get_by_yukassa_id(self, db_session, test_user):
        t = await create_transaction(
            user_id=test_user.id,
            type_="subscription",
            status="success",
            yukassa_id="yk_payment_123",
            session=db_session,
        )
        found = await get_transaction_by_yukassa_id("yk_payment_123", db_session)
        assert found is not None
        assert found.id == t.id

    @pytest.mark.asyncio
    async def test_yukassa_id_not_found(self, db_session):
        result = await get_transaction_by_yukassa_id("nonexistent", db_session)
        assert result is None
