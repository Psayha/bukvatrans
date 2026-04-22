#!/bin/sh
# One-shot helper to bootstrap Let's Encrypt certificates.
#
# Usage:
#   DOMAIN=bot.example.com CERTBOT_EMAIL=ops@example.com ./nginx/init-letsencrypt.sh
#
# After success, reload nginx: `docker compose exec nginx nginx -s reload`.
# Renewals run automatically via the `certbot` sidecar.
set -eu

: "${DOMAIN:?DOMAIN is required}"
: "${CERTBOT_EMAIL:?CERTBOT_EMAIL is required}"

STAGING="${CERTBOT_STAGING:-0}"
STAGING_FLAG=""
if [ "$STAGING" = "1" ]; then
    STAGING_FLAG="--staging"
fi

echo "[init-le] requesting certificate for $DOMAIN (staging=$STAGING)"

docker compose run --rm --entrypoint sh certbot -c "
    certbot certonly \
        --webroot -w /var/www/certbot \
        -d $DOMAIN \
        --email $CERTBOT_EMAIL \
        --agree-tos --no-eff-email \
        --non-interactive \
        $STAGING_FLAG
"

echo "[init-le] done. Reload nginx: docker compose exec nginx nginx -s reload"
