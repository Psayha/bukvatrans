from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.referral import Referral
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
        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        await session.commit()
        return user, False

    # Validate referrer exists, isn't self, and isn't banned. Banned users
    # shouldn't be able to keep farming referral bonuses through new signups.
    if referrer_id is not None:
        referrer = await get_user(referrer_id, session)
        if not referrer or referrer.id == user_id or referrer.is_banned:
            referrer_id = None

    user = User(
        id=user_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
        referrer_id=referrer_id,
    )
    session.add(user)

    if referrer_id is not None:
        # Referral row uses UniqueConstraint(referred_id) — duplicates swallowed.
        session.add(Referral(referrer_id=referrer_id, referred_id=user_id))

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        user = await get_user(user_id, session)
        return (user, False) if user else (await _refetch(user_id, session), False)

    await session.refresh(user)
    return user, True


async def _refetch(user_id: int, session: AsyncSession) -> User:
    user = await get_user(user_id, session)
    if user is None:
        raise ValueError(f"User {user_id} not found after create")
    return user


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
