"""Web auth endpoints: Telegram widget + email/password + refresh."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
    verify_telegram_widget,
)
from src.api.dependencies import get_db
from src.config import settings
from src.db.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(user: User) -> dict:
    is_admin = user.is_admin or user.id in settings.admin_ids_list
    return {
        "access_token": create_access_token(user.id, is_admin=is_admin),
        "refresh_token": create_refresh_token(user.id),
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "first_name": user.first_name,
            "username": user.username,
            "email": user.email,
            "is_admin": is_admin,
        },
    }


# ── Telegram Login Widget ──────────────────────────────────────────────────


class TelegramAuthBody(BaseModel):
    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str


@router.post("/telegram")
async def telegram_auth(body: TelegramAuthBody, session: AsyncSession = Depends(get_db)):
    data = body.model_dump()
    if not verify_telegram_widget(data):
        raise HTTPException(status_code=401, detail="Invalid Telegram auth data")

    user = (
        await session.execute(select(User).where(User.id == body.id))
    ).scalar_one_or_none()

    if not user:
        user = User(
            id=body.id,
            username=body.username,
            first_name=body.first_name,
            last_name=body.last_name,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    else:
        user.username = body.username
        user.first_name = body.first_name
        user.last_name = body.last_name
        await session.commit()

    if user.is_banned:
        raise HTTPException(status_code=403, detail="Account is banned")

    return _token_response(user)


# ── Email / password ───────────────────────────────────────────────────────


class RegisterBody(BaseModel):
    email: EmailStr
    password: str
    first_name: Optional[str] = None


@router.post("/register", status_code=201)
async def register(body: RegisterBody, session: AsyncSession = Depends(get_db)):
    if len(body.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")

    existing = (
        await session.execute(select(User).where(User.email == body.email.lower()))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_id = (await session.execute(text("SELECT nextval('web_user_id_seq')"))).scalar()
    user = User(
        id=new_id,
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        first_name=body.first_name,
        email_verified=False,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return _token_response(user)


class LoginBody(BaseModel):
    email: EmailStr
    password: str


@router.post("/login")
async def login(body: LoginBody, session: AsyncSession = Depends(get_db)):
    user = (
        await session.execute(select(User).where(User.email == body.email.lower()))
    ).scalar_one_or_none()
    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user.is_banned:
        raise HTTPException(status_code=403, detail="Account is banned")
    return _token_response(user)


# ── Refresh token ──────────────────────────────────────────────────────────


class RefreshBody(BaseModel):
    refresh_token: str


@router.post("/refresh")
async def refresh(body: RefreshBody, session: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("not a refresh token")
        user_id = int(payload["sub"])
    except (ValueError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = (
        await session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if not user or user.is_banned:
        raise HTTPException(status_code=401, detail="User not found or banned")

    return _token_response(user)


@router.get("/config")
async def public_config():
    """Non-sensitive config needed by the frontend (e.g. bot username for widget)."""
    return {"bot_username": settings.BOT_USERNAME}
