#!/bin/sh
# Container entrypoint: apply DB migrations, then exec the target command.
#
# Only the primary "migrator" roles (api, bot) run alembic. Workers and beat
# skip the migration step to avoid races when multiple replicas boot
# simultaneously.
set -e

case "$ROLE" in
    api|bot|migrate)
        echo "[entrypoint] applying alembic migrations..."
        alembic upgrade head
        ;;
    *)
        # For worker / beat: best-effort wait for migrations to settle.
        # Primary will have run alembic; we just ensure DB is reachable.
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
        ;;
esac

exec "$@"
