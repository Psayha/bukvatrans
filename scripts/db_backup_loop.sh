#!/bin/sh
# Busybox-compatible scheduler loop: sleep until next BACKUP_HOUR_UTC:00,
# then invoke db_backup.sh. Repeat forever.
set -eu

BACKUP_HOUR_UTC="${BACKUP_HOUR_UTC:-3}"

chmod +x /usr/local/bin/db_backup.sh 2>/dev/null || true

while :; do
    now_h=$(date -u +%-H 2>/dev/null || date -u +%H | sed 's/^0//')
    now_m=$(date -u +%-M 2>/dev/null || date -u +%M | sed 's/^0//')
    now_s=$(date -u +%-S 2>/dev/null || date -u +%S | sed 's/^0//')

    # Hours remaining until the target hour (wrap around midnight).
    hours_delta=$(( (BACKUP_HOUR_UTC - now_h + 24) % 24 ))
    if [ "$hours_delta" = "0" ]; then
        # Already past target this hour? Push to tomorrow.
        if [ "$now_m" -gt 0 ] || [ "$now_s" -gt 0 ]; then
            hours_delta=24
        fi
    fi

    seconds_until=$(( hours_delta * 3600 - now_m * 60 - now_s ))
    if [ "$seconds_until" -le 0 ]; then
        seconds_until=60   # belt and braces
    fi

    echo "[$(date -u +%FT%TZ)] next backup in ${seconds_until}s (target ${BACKUP_HOUR_UTC}:00 UTC)"
    sleep "$seconds_until"

    /usr/local/bin/db_backup.sh || echo "[$(date -u +%FT%TZ)] backup failed (non-fatal)"
done
