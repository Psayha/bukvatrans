"""Web payment endpoints — create YuKassa payment links."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user, get_db
from src.db.models.user import User
from src.services.billing import PLANS, TOPUP_OPTIONS

router = APIRouter(prefix="/payments", tags=["payments"])


async def _create_yukassa_payment(
    amount_rub: float,
    description: str,
    metadata: dict,
    email: Optional[str],
    return_url: str,
    vat_code: int,
) -> dict:
    """Create a YuKassa payment and return {payment_id, confirmation_url}."""
    import uuid as _uuid
    from yookassa import Configuration, Payment
    from src.config import settings

    Configuration.account_id = settings.YUKASSA_SHOP_ID
    Configuration.secret_key = settings.YUKASSA_SECRET_KEY

    receipt: dict | None = None
    if email:
        receipt = {
            "customer": {"email": email},
            "items": [
                {
                    "description": description,
                    "quantity": 1,
                    "amount": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
                    "vat_code": vat_code,
                }
            ],
        }

    payment = Payment.create(
        {
            "amount": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
            "confirmation": {"type": "redirect", "return_url": return_url},
            "capture": True,
            "description": description,
            "metadata": metadata,
            **({"receipt": receipt} if receipt else {}),
        },
        idempotency_key=str(_uuid.uuid4()),
    )
    return {
        "payment_id": payment.id,
        "confirmation_url": payment.confirmation.confirmation_url,
    }


class SubscriptionBody(BaseModel):
    plan_key: str
    return_url: str = "https://littera.site"


@router.post("/subscription")
async def create_subscription_payment(
    body: SubscriptionBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    if body.plan_key not in PLANS:
        raise HTTPException(status_code=422, detail="Unknown plan")

    plan = PLANS[body.plan_key]
    try:
        result = await _create_yukassa_payment(
            amount_rub=plan["price_rub"],
            description=plan["label"],
            metadata={"plan_key": body.plan_key, "user_id": str(user.id)},
            email=user.email,
            return_url=body.return_url,
            vat_code=__import__("src.config", fromlist=["settings"]).settings.YUKASSA_VAT_CODE,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Payment provider error: {exc}")

    return {
        "payment_id": result["payment_id"],
        "confirmation_url": result["confirmation_url"],
        "amount_rub": plan["price_rub"],
        "plan": body.plan_key,
        "label": plan["label"],
    }


class TopupBody(BaseModel):
    topup_key: str
    return_url: str = "https://littera.site"


@router.post("/topup")
async def create_topup_payment(
    body: TopupBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    if body.topup_key not in TOPUP_OPTIONS:
        raise HTTPException(status_code=422, detail="Unknown topup option")

    option = TOPUP_OPTIONS[body.topup_key]
    try:
        result = await _create_yukassa_payment(
            amount_rub=option["price_rub"],
            description=f"Пополнение баланса {option['seconds'] // 3600}ч",
            metadata={"topup_key": body.topup_key, "user_id": str(user.id)},
            email=user.email,
            return_url=body.return_url,
            vat_code=__import__("src.config", fromlist=["settings"]).settings.YUKASSA_VAT_CODE,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Payment provider error: {exc}")

    return {
        "payment_id": result["payment_id"],
        "confirmation_url": result["confirmation_url"],
        "amount_rub": option["price_rub"],
        "seconds": option["seconds"],
    }


@router.get("/plans")
async def get_plans():
    return {
        "plans": [
            {
                "key": k,
                "label": v["label"],
                "price_rub": v["price_rub"],
                "period_days": v["period_days"],
                "recommended": v.get("recommended", False),
            }
            for k, v in PLANS.items()
        ],
        "topups": [
            {
                "key": k,
                "price_rub": v["price_rub"],
                "seconds": v["seconds"],
                "hours": v["seconds"] // 3600,
            }
            for k, v in TOPUP_OPTIONS.items()
        ],
    }
