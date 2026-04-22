import hashlib
import hmac
import ipaddress
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.base import async_session_factory
from src.db.models.subscription import Subscription
from src.db.models.transaction import Transaction
from src.db.models.user import User
from src.db.repositories.transaction import get_transaction_by_yukassa_id
from src.services.billing import PLANS, TOPUP_OPTIONS
from src.services.notification import send_message
from src.services.referral import process_referral_bonus
from src.bot.texts.ru import PAYMENT_SUCCESS
from src.utils import metrics
from src.utils.logging import get_logger

logger = get_logger(__name__)

YUKASSA_IPS = [
    ipaddress.ip_network("185.71.76.0/27"),
    ipaddress.ip_network("185.71.77.0/27"),
    ipaddress.ip_network("77.75.153.0/25"),
    ipaddress.ip_network("77.75.154.128/25"),
    ipaddress.ip_network("2a02:5180::/32"),
]
YUKASSA_SINGLE_IPS = {"77.75.156.11", "77.75.156.35"}


def _is_yukassa_ip(ip: str) -> bool:
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if ip in YUKASSA_SINGLE_IPS:
        return True
    return any(addr in net for net in YUKASSA_IPS)


def _verify_yukassa_signature(body: bytes, signature: Optional[str]) -> bool:
    """Verify HMAC-SHA256 signature over raw body using YUKASSA_SECRET_KEY.

    YuKassa по стандартной подписке не подписывает вебхуки, но если в настройках
    shop включена подпись (или используется свой reverse-proxy, добавляющий HMAC),
    мы проверяем её. При отсутствии заголовка — полагаемся на IP-whitelist.
    """
    if not signature or not settings.YUKASSA_SECRET_KEY:
        return False
    expected = hmac.new(
        settings.YUKASSA_SECRET_KEY.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    # Signature may come with an algo prefix ("sha256=<hex>")
    if signature.startswith("sha256="):
        signature = signature[len("sha256="):]
    return hmac.compare_digest(expected, signature)


async def handle_yukassa_webhook(request: Request) -> JSONResponse:
    body = await request.body()

    signature = request.headers.get("X-Yookassa-Signature") or request.headers.get("X-YooKassa-Signature")
    client_ip = (
        request.headers.get("X-Real-IP")
        or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    )

    # Accept if EITHER signature matches OR IP is in YuKassa allow-list.
    signature_ok = _verify_yukassa_signature(body, signature)
    ip_ok = _is_yukassa_ip(client_ip)
    if not (signature_ok or ip_ok):
        logger.warning("yukassa_webhook_rejected", ip=client_ip, has_signature=bool(signature))
        raise HTTPException(status_code=403, detail="Forbidden")

    import json
    try:
        data: dict[str, Any] = json.loads(body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event = data.get("event")
    obj = data.get("object", {})
    payment_id = obj.get("id")
    if not payment_id:
        return JSONResponse({"ok": True})

    idempotency_key = request.headers.get("X-Request-Id")

    async with async_session_factory() as session:
        # Cheap pre-check — the authoritative idempotency guard is inside
        # _handle_payment_succeeded, wrapped in a DB transaction.
        existing = await get_transaction_by_yukassa_id(payment_id, session)
        if existing and existing.status == "success":
            return JSONResponse({"ok": True})
        # SQLAlchemy autobegins a transaction on the SELECT above. Roll it
        # back so the inner handler can open a fresh `session.begin()` block
        # without tripping "SessionTransaction is already active".
        await session.rollback()

        if event == "payment.succeeded":
            await _handle_payment_succeeded(obj, idempotency_key, session)
        elif event == "payment.canceled":
            await _handle_payment_cancelled(obj, session)

    return JSONResponse({"ok": True})


async def _lock_user(user_id: int, session: AsyncSession) -> Optional[User]:
    """SELECT ... FOR UPDATE the user row to serialise balance updates."""
    stmt = select(User).where(User.id == user_id).with_for_update()
    try:
        result = await session.execute(stmt)
    except Exception:
        # SQLite/other backends without row-level locks — fall back to plain select.
        result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def _handle_payment_succeeded(
    obj: dict, idempotency_key: Optional[str], session: AsyncSession
) -> None:
    """All state changes happen inside a single transaction with a row lock.

    Idempotency: the Transaction row is inserted first with a unique yukassa_id;
    a duplicate webhook therefore hits the existing row and short-circuits.
    """
    payment_id = obj["id"]
    amount_rub = float(obj["amount"]["value"])
    metadata = obj.get("metadata", {})
    user_id = int(metadata.get("user_id", 0))
    if not user_id:
        return

    plan_key: Optional[str] = metadata.get("plan_key")
    topup_key: Optional[str] = metadata.get("topup_key")

    # Atomic block — commit happens at the end; a duplicate webhook that
    # races us will see the already-inserted Transaction and bail out.
    try:
        async with session.begin():
            existing = await get_transaction_by_yukassa_id(payment_id, session)
            if existing and existing.status == "success":
                return

            user = await _lock_user(user_id, session)
            if not user:
                return

            seconds_added = 0
            plan_name = ""
            expires_str = ""

            if plan_key and plan_key in PLANS:
                plan = PLANS[plan_key]
                seconds_added = plan["seconds"] if plan["seconds"] != -1 else 0
                period_days = plan["period_days"]
                plan_name = plan_key.replace("_", " ").title()

                sub = Subscription(
                    user_id=user_id,
                    plan=plan_key.split("_")[0],
                    status="active",
                    seconds_limit=plan["seconds"],
                    started_at=datetime.utcnow(),
                    expires_at=datetime.utcnow() + timedelta(days=period_days),
                    yukassa_sub_id=payment_id,
                )
                session.add(sub)
                expires_str = (datetime.utcnow() + timedelta(days=period_days)).strftime("%d.%m.%Y")

            elif topup_key and topup_key in TOPUP_OPTIONS:
                option = TOPUP_OPTIONS[topup_key]
                seconds_added = option["seconds"]

            if seconds_added > 0:
                user.balance_seconds = (user.balance_seconds or 0) + seconds_added

            import uuid as _uuid
            tx = Transaction(
                id=str(_uuid.uuid4()),
                user_id=user_id,
                type="subscription" if plan_key else "topup",
                status="success",
                amount_rub=amount_rub,
                seconds_added=seconds_added,
                yukassa_id=payment_id,
                description=f"Оплата {plan_key or topup_key}",
            )
            session.add(tx)

            # Referral bonus — same transaction, with its own row lock inside.
            if user.referrer_id:
                await process_referral_bonus(
                    user.referrer_id, amount_rub, session, autocommit=False
                )

    except Exception:
        # The session is rolled back by begin() context. Re-raise so YuKassa
        # gets 5xx and retries rather than losing money silently.
        metrics.payments_total.labels(event="succeeded", type="error").inc()
        logger.error("payment_webhook_failed", payment_id=payment_id, exc_info=True)
        raise

    tx_type = "subscription" if plan_key else "topup"
    metrics.payments_total.labels(event="succeeded", type=tx_type).inc()
    metrics.payment_amount_rub.labels(type=tx_type).inc(amount_rub)

    # User-facing notifications happen only after the DB commit succeeded.
    try:
        if plan_key:
            await send_message(
                user_id,
                PAYMENT_SUCCESS.format(plan_name=plan_name, expires_at=expires_str),
                parse_mode="HTML",
            )
        elif topup_key:
            await send_message(
                user_id,
                f"✅ Баланс пополнен на {seconds_added // 3600} ч!",
            )
    except Exception:
        logger.warning("payment_notification_failed", user_id=user_id, exc_info=True)


async def _handle_payment_cancelled(obj: dict, session: AsyncSession) -> None:
    import uuid as _uuid
    payment_id = obj["id"]
    metadata = obj.get("metadata", {})
    user_id = int(metadata.get("user_id", 0))

    try:
        async with session.begin():
            existing = await get_transaction_by_yukassa_id(payment_id, session)
            if existing:
                return
            tx = Transaction(
                id=str(_uuid.uuid4()),
                user_id=user_id or 0,
                type="subscription",
                status="failed",
                yukassa_id=payment_id,
            )
            session.add(tx)
    except Exception:
        logger.error("payment_cancelled_failed", payment_id=payment_id, exc_info=True)
        raise

    if user_id:
        try:
            await send_message(user_id, "❌ Оплата отменена.")
        except Exception:
            pass


async def activate_subscription(user_id: int, plan_key: str, session: AsyncSession) -> None:
    """Activate subscription (extracted for testability)."""
    if plan_key not in PLANS:
        return
    plan = PLANS[plan_key]
    async with session.begin():
        user = await _lock_user(user_id, session)
        if not user:
            return
        sub = Subscription(
            user_id=user_id,
            plan=plan_key.split("_")[0],
            status="active",
            seconds_limit=plan["seconds"],
            started_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=plan["period_days"]),
        )
        session.add(sub)
        if plan["seconds"] > 0:
            user.balance_seconds = (user.balance_seconds or 0) + plan["seconds"]
