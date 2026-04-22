import asyncio
import logging

import sentry_sdk

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from src.config import settings
from src.utils.logging import _sentry_before_send, setup_logging

setup_logging()

from src.bot.handlers import (  # noqa: E402  (must follow setup_logging)
    admin,
    callbacks,
    links,
    media,
    payment,
    profile,
    promo,
    referral,
    settings as settings_handler,
    start,
)
from src.bot.middlewares.ban import BanMiddleware  # noqa: E402
from src.bot.middlewares.database import DatabaseMiddleware  # noqa: E402
from src.bot.middlewares.rate_limit import RateLimitMiddleware  # noqa: E402
from src.bot.middlewares.user import UserMiddleware  # noqa: E402

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENV,
        traces_sample_rate=0.1,
        send_default_pii=False,
        before_send=_sentry_before_send,
    )

bot = Bot(
    token=settings.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

# FSM on a dedicated Redis DB so broker back-pressure cannot evict user state.
storage = RedisStorage.from_url(settings.redis_fsm_url)
dp = Dispatcher(storage=storage)

# Middleware order:
#  1. DatabaseMiddleware — opens a session all later steps reuse.
#  2. UserMiddleware — loads/creates the User row.
#  3. BanMiddleware — stops banned users before rate-limit counters tick up.
#  4. RateLimitMiddleware — last so genuine rate-limit rejections are observable.
dp.update.middleware(DatabaseMiddleware())
dp.update.middleware(UserMiddleware())
dp.update.middleware(BanMiddleware())
dp.update.middleware(RateLimitMiddleware())

dp.include_router(start.router)
dp.include_router(profile.router)
dp.include_router(payment.router)
dp.include_router(referral.router)
dp.include_router(promo.router)
dp.include_router(admin.router)
dp.include_router(settings_handler.router)
dp.include_router(links.router)
dp.include_router(media.router)
dp.include_router(callbacks.router)


async def on_startup():
    from src.db import models as _models  # noqa: F401  — register models on Base
    from src.db.base import Base, engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    if settings.WEBHOOK_HOST:
        if not settings.WEBHOOK_SECRET:
            raise RuntimeError(
                "WEBHOOK_SECRET must be set when WEBHOOK_HOST is configured"
            )
        await bot.set_webhook(
            url=f"{settings.WEBHOOK_HOST}/webhooks/telegram",
            secret_token=settings.WEBHOOK_SECRET,
        )
        logging.info("webhook_set")
    else:
        await bot.delete_webhook()
        logging.info("polling_mode")


async def main():
    await on_startup()
    if settings.WEBHOOK_HOST:
        from src.api.main import app
        import uvicorn
        config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()
    else:
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
