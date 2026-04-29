"""FastAPI dependencies shared across all route modules."""
from typing import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import decode_token
from src.config import settings
from src.db.base import async_session_factory
from src.db.models.user import User
from src.db.repositories.user import get_user

_bearer = HTTPBearer()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    session: AsyncSession = Depends(get_db),
) -> User:
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise ValueError("not an access token")
        user_id = int(payload["sub"])
    except (ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_user(user_id, session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_banned:
        raise HTTPException(status_code=403, detail="Account is banned")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if not (user.is_admin or user.id in settings.admin_ids_list):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
