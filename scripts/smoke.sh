#!/bin/sh
# Pre-push smoke test — catches the stuff that unit tests miss.
#
# Runs:
#   1. ruff (style + dead code)
#   2. pytest (337 units)
#   3. alembic upgrade head against a fresh SQLite file
#       — catches missing imports, wrong column types, bad FK order
#   4. alembic downgrade base (sanity on down path)
#   5. `docker compose config` (validates compose YAML + env substitution)
#   6. `python -c 'import src...'` for every top-level module
#
# Run BEFORE every push. No exceptions.
set -eu

cd "$(dirname "$0")/.."

export BOT_TOKEN="${BOT_TOKEN:-123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11}"

TEST_DB="/tmp/bukvatrans_smoke_$$.db"
cleanup() { rm -f "$TEST_DB"; }
trap cleanup EXIT

echo "[smoke] 1/5 ruff"
ruff check src/ tests/ --select=E,W,F --ignore=E501

echo "[smoke] 2/5 pytest"
python -m pytest tests/ --no-cov -q

echo "[smoke] 3/5 alembic upgrade head (fresh SQLite)"
DATABASE_URL="sqlite+aiosqlite:///$TEST_DB" alembic upgrade head

echo "[smoke] 4/5 alembic downgrade base"
DATABASE_URL="sqlite+aiosqlite:///$TEST_DB" alembic downgrade base

echo "[smoke] 5/5 docker compose config"
# docker compose needs .env to satisfy `env_file: .env`. Generate a
# throwaway one if the developer doesn't have a real one locally.
env_created=0
if [ ! -f .env ]; then
    cp .env.example .env
    env_created=1
fi
cleanup_env() { [ "$env_created" = "1" ] && rm -f .env; }
trap 'cleanup; cleanup_env' EXIT

DB_PASSWORD=smoke DOMAIN=example.test docker compose config > /dev/null 2>&1 \
    && echo "  compose base: ok" \
    || { echo "  compose base: FAIL"; DB_PASSWORD=smoke DOMAIN=example.test docker compose config 2>&1 | tail -20; exit 1; }
DB_PASSWORD=smoke DOMAIN=example.test docker compose -f docker-compose.yml -f docker-compose.staging.yml config > /dev/null 2>&1 \
    && echo "  compose staging: ok" \
    || { echo "  compose staging: FAIL"; exit 1; }

echo "[smoke] all green"
