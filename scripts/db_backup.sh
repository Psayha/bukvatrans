#!/bin/sh
# Dump the database to /backups and prune dumps older than RETENTION_DAYS.
# Called by a cron inside the db_backup sidecar container.
set -eu

DEST="/backups"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
TS=$(date -u +%Y%m%dT%H%M%SZ)
OUT="$DEST/transcribe_bot_${TS}.sql.gz"

mkdir -p "$DEST"

echo "[$(date -u +%FT%TZ)] pg_dump -> $OUT"
pg_dump -h db -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=plain --no-owner --no-privileges \
    | gzip -9 > "$OUT"

# Sanity check.
if [ ! -s "$OUT" ]; then
    echo "[$(date -u +%FT%TZ)] ERROR: dump empty, removing"
    rm -f "$OUT"
    exit 1
fi

# Rotate: keep only the last N days.
find "$DEST" -name 'transcribe_bot_*.sql.gz' -mtime +"$RETENTION_DAYS" -delete
echo "[$(date -u +%FT%TZ)] done; ${RETENTION_DAYS}d retention enforced"
