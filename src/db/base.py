from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from src.config import settings


class Base(DeclarativeBase):
    pass


_engine_kwargs: dict = {"echo": False, "pool_pre_ping": True}
# SQLite does not support pool_size / max_overflow
if not settings.DATABASE_URL.startswith("sqlite"):
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
