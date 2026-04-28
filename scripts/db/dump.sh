#!/usr/bin/env bash
#
# scripts/db/dump.sh
#
# Take a snapshot of the in-compose Postgres database. Output is a
# pg_dump custom-format archive (-Fc), restorable with pg_restore.
#
# Safe to run while Django is up — pg_dump takes a consistent MVCC
# snapshot without locking writes. For a real migration cutover, stop
# the django + ai-engine containers first so there are no in-flight
# webhook handlers writing during the dump (see scripts/db/README.md).
#
# Run from the repo root on the droplet:
#   bash scripts/db/dump.sh
#
# Output:
#   backups/<dbname>-<UTC-timestamp>.dump
#   backups/<dbname>-<UTC-timestamp>.log     (pg_dump verbose log)
#
# Tested with the docker-compose.prod.yml `db` service (postgres:16-alpine).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"

if [[ ! -f django_backend/.env ]]; then
  echo "ERROR: django_backend/.env not found. Run this on the droplet, from the repo root." >&2
  exit 1
fi

# Pull DB name + user from .env without sourcing the whole file (which
# would also set ANTHROPIC_API_KEY etc. into our shell — not what we want).
DB_NAME=$(grep -E '^POSTGRES_DB=' django_backend/.env | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")
DB_USER=$(grep -E '^POSTGRES_USER=' django_backend/.env | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")
DB_NAME="${DB_NAME:-reviewhub}"
DB_USER="${DB_USER:-reviewhub}"

OUT_DIR="backups"
mkdir -p "$OUT_DIR"

TS=$(date -u +%Y-%m-%dT%H%MZ)
OUT="$OUT_DIR/${DB_NAME}-${TS}.dump"
LOG="$OUT_DIR/${DB_NAME}-${TS}.log"

echo "==> Dumping ${DB_NAME} (user: ${DB_USER}) from in-compose db service..."
echo "    Output: $OUT"

# pg_dump runs inside the db container so we get the matching binary
# version. -T avoids tty allocation so we can pipe the output cleanly.
# --format=custom: compressed, restorable with pg_restore, supports
# selective restore.
# --no-owner --no-acl: skip ownership reassignment so the dump can be
# loaded into a Managed Postgres where the user names differ.
docker compose -f "$COMPOSE_FILE" exec -T db \
  pg_dump \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --format=custom \
    --no-owner \
    --no-acl \
    --verbose \
  > "$OUT" 2> "$LOG"

SIZE=$(du -h "$OUT" | cut -f1)
echo "==> Wrote $OUT ($SIZE)"

# Sanity check: row counts per table from the *running* db so the user
# can compare after restore. pg_stat_user_tables is approximate (autovacuum
# stats) but good enough for a smoke check.
echo ""
echo "==> Top 10 tables by row count (in source db):"
docker compose -f "$COMPOSE_FILE" exec -T db \
  psql -U "$DB_USER" -d "$DB_NAME" -c "
    SELECT schemaname || '.' || relname AS table, n_live_tup AS rows
    FROM pg_stat_user_tables
    WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
    ORDER BY n_live_tup DESC
    LIMIT 10;
  " 2>/dev/null || true

echo ""
echo "==> Done."
echo "    Restore with:"
echo "      bash scripts/db/restore-to-managed.sh \\"
echo "        $OUT \\"
echo "        'postgres://doadmin:PW@HOST:25060/DBNAME?sslmode=require'"
