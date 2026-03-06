import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from src.db.base import Base
from src.db.models.user import User
from src.db.models.subscription import Subscription
from datetime import datetime, timedelta


@pytest_asyncio.fixture
async def db_session():
    """In-memory SQLite test database."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def mock_groq_client():
    mock = AsyncMock()
    mock.audio.transcriptions.create.return_value = MagicMock(
        text="Тестовый текст транскрибации.",
        segments=[{"start": 0.0, "end": 5.0, "text": "Тестовый текст транскрибации."}],
    )
    return mock


@pytest.fixture
def mock_claude_client():
    mock = AsyncMock()
    mock.messages.create.return_value = MagicMock(
        content=[MagicMock(text="## 📌 Ключевая мысль\nТестовый конспект.")]
    )
    return mock


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    user = User(
        id=123456789,
        username="testuser",
        first_name="Test",
        balance_seconds=7200,
        free_uses_left=0,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def user_with_free_uses(db_session: AsyncSession) -> User:
    user = User(
        id=111111111,
        username="freeuser",
        first_name="Free",
        balance_seconds=0,
        free_uses_left=3,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def banned_user(db_session: AsyncSession) -> User:
    user = User(
        id=222222222,
        username="banned",
        first_name="Banned",
        balance_seconds=9999,
        free_uses_left=0,
        is_banned=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def user_with_unlimited_sub(db_session: AsyncSession) -> User:
    user = User(
        id=333333333,
        username="prouser",
        first_name="Pro",
        balance_seconds=0,
        free_uses_left=0,
    )
    db_session.add(user)
    await db_session.commit()

    sub = Subscription(
        user_id=user.id,
        plan="pro",
        status="active",
        seconds_limit=-1,
        started_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=30),
    )
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(user)
    return user
