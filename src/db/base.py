import os

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from src.config import settings


class Base(DeclarativeBase):
    pass


# Celery workers call `asyncio.new_event_loop()` per task (see src/worker/tasks/
# *_run_async). A pooled asyncpg connection stays bound to the loop it was
# opened on, so the next task picks it up and raises "Future attached to a
# different loop". NullPool opens and closes a connection per session, which
# sidesteps the issue. Bot/API/beat run a single persistent loop and keep the
# normal pool.
_is_worker = os.environ.get("ROLE", "").startswith("worker")

_engine_kwargs: dict = {"echo": False, "pool_pre_ping": True}
if _is_worker:
    _engine_kwargs["poolclass"] = NullPool
elif not settings.DATABASE_URL.startswith("sqlite"):
    # SQLite does not support pool_size / max_overflow
    _engine_kwargs.update(
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_recycle=1800,
    )

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with async_session_factory() as session:
        yield session
