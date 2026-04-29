"""JWT auth utilities + Telegram Login Widget verification."""
import hashlib
import hmac
from datetime import datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from src.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── passwords ──────────────────────────────────────────────────────────────


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


# ── JWT tokens ─────────────────────────────────────────────────────────────


def create_access_token(user_id: int, is_admin: bool = False) -> str:
    expire = datetime.utcnow() + timedelta(
        minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return jwt.encode(
        {"sub": str(user_id), "exp": expire, "type": "access", "adm": is_admin},
        settings.JWT_SECRET_KEY,
        algorithm="HS256",
    )


def create_refresh_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(
        days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
    )
    return jwt.encode(
        {"sub": str(user_id), "exp": expire, "type": "refresh"},
        settings.JWT_SECRET_KEY,
        algorithm="HS256",
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc


# ── Telegram Login Widget ───────────────────────────────────────────────────


def verify_telegram_widget(data: dict) -> bool:
    """Verify Telegram Login Widget hash (HMAC-SHA256 over sorted key=value pairs).

    https://core.telegram.org/widgets/login#checking-authorization
    """
    check_hash = data.get("hash")
    if not check_hash:
        return False

    auth_date = int(data.get("auth_date", 0))
    if datetime.utcnow().timestamp() - auth_date > 86400:
        return False

    entries = sorted(
        (f"{k}={v}" for k, v in data.items() if k != "hash"),
    )
    data_check_string = "\n".join(entries)
    secret_key = hashlib.sha256(settings.BOT_TOKEN.encode()).digest()
    computed = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, check_hash)
