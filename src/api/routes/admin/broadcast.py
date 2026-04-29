"""Admin broadcast — send messages to user segments."""
import asyncio
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db, require_admin
from src.db.base import async_session_factory
from src.db.models.subscription import Subscription
from src.db.models.user import User
from src.services.notification import send_message
from src.utils.logging import get_logger

router = APIRouter(prefix="/broadcast", tags=["admin-broadcast"])
logger = get_logger(__name__)

_BroadcastTarget = Literal["all", "subscribers", "non_subscribers"]


async def _fetch_user_ids(target: _BroadcastTarget) -> list[int]:
    async with async_session_factory() as session:
        if target == "all":
            stmt = select(User.id).where(User.is_banned.is_(False))
        elif target == "subscribers":
            from datetime import datetime
            stmt = (
                select(User.id)
                .join(Subscription, Subscription.user_id == User.id)
                .where(
                    User.is_banned.is_(False),
                    Subscription.status == "active",
                    Subscription.expires_at > datetime.utcnow(),
                )
                .distinct()
            )
        else:  # non_subscribers
            from datetime import datetime
            active_sub = (
                select(Subscription.user_id)
                .where(
                    Subscription.status == "active",
                    Subscription.expires_at > datetime.utcnow(),
                )
            )
            stmt = select(User.id).where(
                User.is_banned.is_(False),
                User.id.not_in(active_sub),
            )
        return list((await session.execute(stmt)).scalars().all())


async def _do_broadcast(text: str, target: _BroadcastTarget) -> None:
    user_ids = await _fetch_user_ids(target)
    logger.info("broadcast_start", target=target, count=len(user_ids))
    sent = 0
    for uid in user_ids:
        try:
            await send_message(uid, text, parse_mode="HTML")
            sent += 1
        except Exception:
            pass
        await asyncio.sleep(0.05)  # stay under Telegram's 20 msg/s limit
    logger.info("broadcast_done", sent=sent, total=len(user_ids))


class BroadcastBody(BaseModel):
    text: str
    target: _BroadcastTarget = "all"


@router.post("/preview")
async def preview_broadcast(
    body: BroadcastBody,
    _=Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """Return estimated recipient count without sending."""
    user_ids = await _fetch_user_ids(body.target)
    return {"target": body.target, "estimated_recipients": len(user_ids)}


@router.post("")
async def send_broadcast(
    body: BroadcastBody,
    background_tasks: BackgroundTasks,
    _=Depends(require_admin),
):
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    background_tasks.add_task(_do_broadcast, body.text, body.target)
    return {"ok": True, "message": "Broadcast queued"}
