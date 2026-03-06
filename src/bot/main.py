import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from src.config import settings
from src.bot.middlewares.database import DatabaseMiddleware
from src.bot.middlewares.user import UserMiddleware
from src.bot.middlewares.ban import BanMiddleware
from src.bot.middlewares.rate_limit import RateLimitMiddleware
from src.bot.handlers import start, profile, media, links, payment, referral, promo, admin, callbacks

logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=settings.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

storage = RedisStorage.from_url(settings.REDIS_URL)
dp = Dispatcher(storage=storage)

# Middlewares (order matters)
dp.update.middleware(DatabaseMiddleware())
dp.update.middleware(UserMiddleware())
dp.update.middleware(BanMiddleware())
dp.update.middleware(RateLimitMiddleware())

# Routers
dp.include_router(start.router)
dp.include_router(profile.router)
dp.include_router(payment.router)
dp.include_router(referral.router)
dp.include_router(promo.router)
dp.include_router(admin.router)
dp.include_router(links.router)
dp.include_router(media.router)
dp.include_router(callbacks.router)


async def on_startup():
    from src.db.base import engine
    from src.db.models import *  # noqa: ensure models are registered
    from src.db.base import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    if settings.WEBHOOK_HOST:
        await bot.set_webhook(
            url=f"{settings.WEBHOOK_HOST}/webhooks/telegram",
            secret_token=settings.WEBHOOK_SECRET,
        )
        logging.info("Webhook set.")
    else:
        await bot.delete_webhook()
        logging.info("Running in polling mode.")


async def main():
    await on_startup()
    if settings.WEBHOOK_HOST:
        # Webhook mode — FastAPI handles incoming updates
        from src.api.main import app
        import uvicorn
        config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()
    else:
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
