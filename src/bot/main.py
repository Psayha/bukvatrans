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
        # Webhook delivery is handled by the `api` service — nginx routes
        # /webhooks/telegram → api:8000 (see nginx/nginx.conf). The bot
        # container used to run its own uvicorn here, but it was unreachable
        # (the `bot` service has no `expose: 8000`) and just burnt ~190 MiB
        # on a 1.9 GiB host. Now we register the webhook in on_startup()
        # and block forever so the container stays up for the healthcheck.
        log.info("bot_idle_in_webhook_mode")
        await asyncio.Event().wait()
    else:
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
