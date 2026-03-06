import ipaddress
from datetime import datetime, timedelta
from typing import Any

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.base import async_session_factory
from src.db.repositories.transaction import get_transaction_by_yukassa_id, create_transaction
from src.db.repositories.user import add_balance, get_user
from src.db.models.subscription import Subscription
from src.services.billing import PLANS, TOPUP_OPTIONS
from src.services.referral import process_referral_bonus
from src.services.notification import send_message
from src.bot.texts.ru import PAYMENT_SUCCESS

YUKASSA_IPS = [
    ipaddress.ip_network("185.71.76.0/27"),
    ipaddress.ip_network("185.71.77.0/27"),
    ipaddress.ip_network("77.75.153.0/25"),
    ipaddress.ip_network("77.75.154.128/25"),
    ipaddress.ip_network("2a02:5180::/32"),
]
YUKASSA_SINGLE_IPS = {"77.75.156.11", "77.75.156.35"}


def _is_yukassa_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if ip in YUKASSA_SINGLE_IPS:
        return True
    return any(addr in net for net in YUKASSA_IPS)


async def handle_yukassa_webhook(request: Request) -> JSONResponse:
    # Check client IP
    client_ip = request.headers.get("X-Real-IP") or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if not _is_yukassa_ip(client_ip):
        raise HTTPException(status_code=403, detail="Forbidden")

    data: dict[str, Any] = await request.json()
    event = data.get("event")
    obj = data.get("object", {})

    payment_id = obj.get("id")
    idempotency_key = request.headers.get("X-Request-Id")

    async with async_session_factory() as session:
        # Idempotency: check if already processed
        existing = await get_transaction_by_yukassa_id(payment_id, session)
        if existing and existing.status == "success":
            return JSONResponse({"ok": True})

        if event == "payment.succeeded":
            await _handle_payment_succeeded(obj, idempotency_key, session)
        elif event == "payment.canceled":
            await _handle_payment_cancelled(obj, session)

    return JSONResponse({"ok": True})


async def _handle_payment_succeeded(obj: dict, idempotency_key: str, session: AsyncSession) -> None:
    payment_id = obj["id"]
    amount_rub = float(obj["amount"]["value"])
    metadata = obj.get("metadata", {})
    user_id = int(metadata.get("user_id", 0))
    if not user_id:
        return

    user = await get_user(user_id, session)
    if not user:
        return

    plan_key = metadata.get("plan_key")
    topup_key = metadata.get("topup_key")

    seconds_added = 0

    if plan_key and plan_key in PLANS:
        plan = PLANS[plan_key]
        seconds_added = plan["seconds"] if plan["seconds"] != -1 else 0
        period_days = plan["period_days"]
        plan_name = plan_key.replace("_", " ").title()

        # Create subscription
        sub = Subscription(
            user_id=user_id,
            plan=plan_key.split("_")[0],  # 'basic' or 'pro'
            status="active",
            seconds_limit=plan["seconds"],
            started_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=period_days),
            yukassa_sub_id=payment_id,
        )
        session.add(sub)

        if seconds_added > 0:
            await add_balance(user_id, seconds_added, session)

        expires_str = (datetime.utcnow() + timedelta(days=period_days)).strftime("%d.%m.%Y")
        await send_message(
            user_id,
            PAYMENT_SUCCESS.format(plan_name=plan_name, expires_at=expires_str),
            parse_mode="HTML",
        )

    elif topup_key and topup_key in TOPUP_OPTIONS:
        option = TOPUP_OPTIONS[topup_key]
        seconds_added = option["seconds"]
        await add_balance(user_id, seconds_added, session)
        await send_message(
            user_id,
            f"✅ Баланс пополнен на {seconds_added // 3600} ч!",
        )

    # Record transaction
    await create_transaction(
        user_id=user_id,
        type_=plan_key and "subscription" or "topup",
        status="success",
        amount_rub=amount_rub,
        seconds_added=seconds_added,
        yukassa_id=payment_id,
        description=f"Оплата {plan_key or topup_key}",
        session=session,
    )

    # Referral bonus
    if user.referrer_id:
        await process_referral_bonus(user.referrer_id, amount_rub, session)

    await session.commit()


async def _handle_payment_cancelled(obj: dict, session: AsyncSession) -> None:
    payment_id = obj["id"]
    metadata = obj.get("metadata", {})
    user_id = int(metadata.get("user_id", 0))
    if user_id:
        await send_message(user_id, "❌ Оплата отменена.")
    await create_transaction(
        user_id=user_id,
        type_="subscription",
        status="failed",
        yukassa_id=payment_id,
        session=session,
    )
    await session.commit()


async def activate_subscription(user_id: int, plan_key: str, session: AsyncSession) -> None:
    """Activate subscription (extracted for testability)."""
    if plan_key not in PLANS:
        return
    plan = PLANS[plan_key]
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
        await add_balance(user_id, plan["seconds"], session)
    await session.commit()
