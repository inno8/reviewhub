#!/usr/bin/env bash
#
# scripts/db/restore-to-managed.sh
#
# Restore a pg_dump custom-format archive (made with scripts/db/dump.sh)
# into a target Postgres database, typically a DigitalOcean Managed
# Postgres cluster.
#
# Usage:
#   bash scripts/db/restore-to-managed.sh <dump-file> <target-database-url>
#
# Example:
#   bash scripts/db/restore-to-managed.sh \
#     backups/reviewhub-2026-04-28T1432Z.dump \
#     'postgres://doadmin:PW@db-postgresql-ams3-xxxxx.b.db.ondigitalocean.com:25060/reviewhub?sslmode=require'
#
# The target database must already exist on the managed instance.
# DO Managed Postgres ships with a "defaultdb" you can use, or create
# a dedicated one via the dashboard / doctl:
#   doctl databases db create <cluster-id> reviewhub
#
# pg_restore runs inside the in-compose db container so we get the
# right version of the client tools without installing anything on
# the host.
#
# After a successful restore:
#   1. Update django_backend/.env (set DATABASE_URL to the managed URL)
#   2. Restart django: docker compose up -d --no-deps --force-recreate django
#   3. Smoke test the app
#   4. Once happy, comment out the `db:` service in docker-compose.prod.yml
#      to stop running an unused Postgres container

set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <dump-file> <target-database-url>" >&2
  exit 1
fi

DUMP_FILE="$1"
TARGET_URL="$2"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [[ ! -f "$DUMP_FILE" ]]; then
  echo "ERROR: dump file not found: $DUMP_FILE" >&2
  exit 1
fi

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"

# Belt-and-suspenders: DO Managed Postgres requires sslmode=require.
# Bail out (or prompt) if it's missing so we don't fail mid-restore with
# a confusing TLS error.
if [[ "$TARGET_URL" != *"sslmode=require"* ]]; then
  echo "WARNING: target URL doesn't include sslmode=require." >&2
  echo "         DO Managed Postgres requires SSL — the restore will fail." >&2
  read -rp "Continue anyway? (y/N) " yn
  [[ "$yn" =~ ^[Yy] ]] || exit 1
fi

# Mask the password in the echoed connection string so the runbook log
# doesn't leak it.
SAFE_URL=$(echo "$TARGET_URL" | sed -E 's#(://[^:]+:)[^@]+(@)#\1***\2#')

cat <<EOF

==> Source : $DUMP_FILE  ($(du -h "$DUMP_FILE" | cut -f1))
==> Target : $SAFE_URL

This will:
  - Drop existing objects on the target (--clean --if-exists)
  - Restore the schema + data from the dump
  - Skip ownership / ACL changes (target runs as a different user)

EOF

read -rp "Press ENTER to continue, Ctrl-C to abort. " _

# pg_restore reads the dump from stdin so we don't need to copy the
# file into the container first. --jobs is incompatible with stdin so
# we run a single-threaded restore — fine for dogfood-scale (<500 MB).
echo ""
echo "==> Running pg_restore..."
docker compose -f "$COMPOSE_FILE" exec -T db \
  pg_restore \
    --dbname="$TARGET_URL" \
    --clean --if-exists \
    --no-owner --no-acl \
    --verbose \
  < "$DUMP_FILE"

echo ""
echo "==> Restore finished. Verifying row counts on target..."
docker compose -f "$COMPOSE_FILE" exec -T db \
  psql "$TARGET_URL" -c "
    SELECT schemaname || '.' || relname AS table, n_live_tup AS rows
    FROM pg_stat_user_tables
    WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
    ORDER BY n_live_tup DESC
    LIMIT 10;
  "

cat <<EOF

==> Done.

Next steps (manual):

  1. Update django_backend/.env:
       DATABASE_URL=$SAFE_URL
     (DATABASE_URL takes precedence over POSTGRES_HOST/PORT/etc.,
      so this is the cleanest cutover.)

  2. Bring Django back against the managed DB:
       docker compose -f $COMPOSE_FILE up -d --no-deps --force-recreate django

  3. Smoke test:
       curl -i https://your-domain/api/health/
       docker compose -f $COMPOSE_FILE logs --tail=50 django

  4. Once stable for ~24h, stop the in-compose db service:
       Comment out the 'db:' block in $COMPOSE_FILE
       docker compose -f $COMPOSE_FILE up -d --remove-orphans
       docker volume rm reviewhub_pgdata     # only when sure!

EOF
