#!/bin/sh
# Bootstrap Let's Encrypt certificates on a clean server.
#
# Problem: the production nginx config references ssl_certificate paths that
# don't exist on first boot, so nginx fails to start. Let's Encrypt's
# http-01 challenge needs a running webserver, so we're in a chicken-and-egg.
#
# Solution: start nginx with nginx.bootstrap.conf (HTTP-only, just serves
# /.well-known/acme-challenge), run certbot once to get the cert, then
# switch to nginx.conf and reload.
#
# Usage:
#   DOMAIN=bot.example.com CERTBOT_EMAIL=ops@example.com ./nginx/init-letsencrypt.sh
#
# Idempotent: safe to re-run. After the first success, renewals are handled
# automatically by the certbot sidecar.
set -eu

: "${DOMAIN:?DOMAIN is required}"
: "${CERTBOT_EMAIL:?CERTBOT_EMAIL is required}"

STAGING="${CERTBOT_STAGING:-0}"
STAGING_FLAG=""
if [ "$STAGING" = "1" ]; then
    STAGING_FLAG="--staging"
    echo "[init-le] using Let's Encrypt STAGING (invalid certs, relaxed limits)"
fi

echo "[init-le] 1/4 starting nginx in bootstrap mode (HTTP-only)"
docker compose run --rm -d --name bukvatrans_nginx_bootstrap \
    --service-ports \
    -v "$(pwd)/nginx/nginx.bootstrap.conf:/etc/nginx/nginx.conf:ro" \
    -v bukvatrans_letsencrypt_www:/var/www/certbot \
    --entrypoint nginx nginx \
    -g 'daemon off;' >/dev/null

# Give nginx a moment to accept connections.
sleep 2

cleanup() {
    echo "[init-le] stopping bootstrap nginx"
    docker rm -f bukvatrans_nginx_bootstrap >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "[init-le] 2/4 requesting certificate for $DOMAIN"
docker compose run --rm --entrypoint sh certbot -c "
    certbot certonly \
        --webroot -w /var/www/certbot \
        -d $DOMAIN \
        --email $CERTBOT_EMAIL \
        --agree-tos --no-eff-email \
        --non-interactive \
        $STAGING_FLAG
"

echo "[init-le] 3/4 stopping bootstrap nginx"
cleanup
trap - EXIT

echo "[init-le] 4/4 starting full stack"
docker compose up -d

echo ""
echo "[init-le] done. Certificate installed for $DOMAIN."
echo "         Renewals run automatically via the certbot sidecar."
echo "         Verify: curl -I https://$DOMAIN/health"
