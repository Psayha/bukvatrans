"""Entry point: `python -m src.bot.main`.

Intentionally thin — all bot wiring lives in `src.bot.dispatcher` so it can
be imported by the api webhook handler without re-executing module-level
`include_router` calls. See dispatcher.py for the rationale.
"""
import asyncio

from src.bot.dispatcher import bot, dp, log
from src.config import settings


async def on_startup():
    # Schema is managed by alembic in the container entrypoint; this hook
    # only handles Telegram-side setup.
    from src.bot.commands import sync_bot_commands
    await sync_bot_commands(bot)

    if settings.WEBHOOK_HOST:
        if not settings.WEBHOOK_SECRET:
            raise RuntimeError(
                "WEBHOOK_SECRET must be set when WEBHOOK_HOST is configured"
            )
        await bot.set_webhook(
            url=f"{settings.WEBHOOK_HOST}/webhooks/telegram",
            secret_token=settings.WEBHOOK_SECRET,
        )
        log.info("webhook_set", host=settings.WEBHOOK_HOST)
    else:
        await bot.delete_webhook()
        log.info("polling_mode")


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
