#!/bin/sh
# External health probe for UptimeRobot / Pingdom / cronned monitors.
#
# Exits 0 if:
#   1. HTTPS /health returns 200 (DB and Redis reachable from the API pod)
#   2. Telegram getMe succeeds with our BOT_TOKEN
#
# Usage:
#   DOMAIN=bot.example.com BOT_TOKEN=... ./scripts/uptime_check.sh
set -eu

: "${DOMAIN:?DOMAIN is required}"
: "${BOT_TOKEN:?BOT_TOKEN is required}"

API="https://$DOMAIN/health"
TG="https://api.telegram.org/bot${BOT_TOKEN}/getMe"

echo "[uptime] checking $API"
if ! curl -fsS --max-time 10 "$API" > /tmp/health.json; then
    echo "[uptime] FAIL: $API did not return 200"
    cat /tmp/health.json 2>/dev/null || true
    exit 1
fi
grep -q '"status":"ok"' /tmp/health.json || {
    echo "[uptime] FAIL: /health reports degraded"
    cat /tmp/health.json
    exit 1
}

echo "[uptime] checking Telegram getMe"
# Mask the token so the log line is safe to ship.
if ! curl -fsS --max-time 10 "$TG" > /tmp/getme.json; then
    echo "[uptime] FAIL: Telegram getMe failed"
    exit 1
fi
grep -q '"ok":true' /tmp/getme.json || {
    echo "[uptime] FAIL: Telegram getMe returned non-ok"
    exit 1
}

echo "[uptime] OK"
