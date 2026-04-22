#!/bin/sh
# Container entrypoint.
#
# Schema migrations are owned by the `migrate` one-shot service in
# docker-compose, which runs `alembic upgrade head` before any long-running
# role starts. This entrypoint just waits for the DB to become reachable
# (useful when `depends_on` isn't available — e.g., bare docker runs) and
# execs the target command.
set -e

# Wait for DB — cheap probe, skip if no DATABASE_URL configured (tests).
if [ -n "${DATABASE_URL:-}" ] && [ "$ROLE" != "migrate" ]; then
    python -c "
import asyncio, sys
from sqlalchemy import text
from src.db.base import async_session_factory

async def _probe():
    for _ in range(30):
        try:
            async with async_session_factory() as s:
                await s.execute(text('SELECT 1'))
            return
        except Exception:
            await asyncio.sleep(2)
    sys.exit('DB not reachable after 60s')

asyncio.run(_probe())
" || exit 1
fi

exec "$@"
