from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.user import User


async def get_user(user_id: int, session: AsyncSession) -> Optional[User]:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_or_create_user(
    user_id: int,
    username: Optional[str],
    first_name: Optional[str],
    last_name: Optional[str],
    referrer_id: Optional[int],
    session: AsyncSession,
) -> tuple[User, bool]:
    user = await get_user(user_id, session)
    if user:
        # Update name fields if changed
        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        await session.commit()
        return user, False

    user = User(
        id=user_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
        referrer_id=referrer_id,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user, True


async def add_balance(user_id: int, seconds: int, session: AsyncSession) -> User:
    user = await get_user(user_id, session)
    if not user:
        raise ValueError(f"User {user_id} not found")
    user.balance_seconds += seconds
    await session.commit()
    await session.refresh(user)
    return user


async def deduct_balance(user_id: int, seconds: int, session: AsyncSession) -> User:
    user = await get_user(user_id, session)
    if not user:
        raise ValueError(f"User {user_id} not found")
    user.balance_seconds = max(0, user.balance_seconds - seconds)
    await session.commit()
    await session.refresh(user)
    return user


async def decrement_free_uses(user_id: int, session: AsyncSession) -> User:
    user = await get_user(user_id, session)
    if not user:
        raise ValueError(f"User {user_id} not found")
    if user.free_uses_left > 0:
        user.free_uses_left -= 1
    await session.commit()
    await session.refresh(user)
    return user
