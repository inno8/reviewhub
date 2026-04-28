# Database scripts

Operational scripts for the LEERA Postgres database.

## Files

- **`dump.sh`** — Take a `pg_dump` snapshot of the in-compose Postgres database. Output goes to `backups/<dbname>-<UTC-timestamp>.dump`. Safe to run while the app is up.
- **`restore-to-managed.sh`** — Restore a dump file into a target Postgres database (typically DO Managed Postgres). Used for the migration from Option A (in-compose) to Option B (managed).

Both scripts run `pg_dump` / `pg_restore` inside the existing `db` Docker container so you don't need PostgreSQL client tools installed on the host droplet, and the binary versions match.

## Migration runbook: in-compose → DO Managed Postgres

Estimated downtime: **~5 minutes** for a single-cohort dogfood dataset.

### Prerequisites

- A DigitalOcean Managed Postgres cluster created in the **same region as your droplet** (AMS3 ↔ AMS3).
  - 1 GB / 10 GB plan is fine for one cohort (~€15/month).
  - DO dashboard → Databases → Create → PostgreSQL 16 → AMS3 → 1 GB Basic.
- The connection details from the DO dashboard:
  - Host: `db-postgresql-ams3-xxxxx-do-user-xxxxx-0.b.db.ondigitalocean.com`
  - Port: `25060`
  - Username: `doadmin`
  - Password: copy from dashboard (shown once)
  - Database: `defaultdb`, or create a dedicated `reviewhub` DB:
    ```bash
    # On your laptop, with doctl installed + authed:
    doctl databases db create <cluster-id> reviewhub
    ```

### The runbook

```bash
# 0. SSH onto the droplet
ssh root@your-droplet-ip
cd /srv/reviewhub

# 1. Make the scripts executable (first time only)
chmod +x scripts/db/dump.sh scripts/db/restore-to-managed.sh

# 2. Take a defensive snapshot first (nothing is stopped — just a backup
#    in case the migration goes sideways). This is your rollback point.
bash scripts/db/dump.sh
# →  backups/reviewhub-2026-04-28T1430Z.dump

# 3. Stop Django and ai-engine so no new writes happen during the cutover.
#    The db container keeps running because we still need to dump from it.
docker compose -f docker-compose.prod.yml stop django ai-engine

# 4. Take the *real* migration dump (consistent with the stopped app)
bash scripts/db/dump.sh
# →  backups/reviewhub-2026-04-28T1432Z.dump

# 5. Restore into the managed instance.
#    Replace HOST + PASSWORD with values from the DO dashboard.
bash scripts/db/restore-to-managed.sh \
  backups/reviewhub-2026-04-28T1432Z.dump \
  'postgres://doadmin:THE_DO_PASSWORD@db-postgresql-ams3-xxxx.b.db.ondigitalocean.com:25060/reviewhub?sslmode=require'

# 6. Update django_backend/.env to point at the managed DB.
nano django_backend/.env
#    Set:
#      DATABASE_URL=postgres://doadmin:PW@HOST:25060/reviewhub?sslmode=require
#    DATABASE_URL takes precedence over POSTGRES_HOST/PORT/USER/DB/PW so
#    this single line is enough. You can leave the POSTGRES_* lines
#    untouched (they become unused).

# 7. Bring Django + ai-engine back up against the new DB
docker compose -f docker-compose.prod.yml up -d

# 8. Smoke test — give Django a few seconds to boot, then:
curl -i https://your-domain.com/api/health/
docker compose -f docker-compose.prod.yml logs --tail=80 django

# 9. Once stable for ~24 hours, stop running the unused in-compose db
#    container so you stop paying for the RAM + disk it holds.
nano docker-compose.prod.yml
#    Comment out the entire `db:` service block.
#    Comment out `pgdata` from the `volumes:` section if you want.
docker compose -f docker-compose.prod.yml up -d --remove-orphans

# 10. (Optional, irreversible) Delete the local pgdata volume to free disk.
#     Only do this when you're 100% sure the managed DB has the data.
docker volume rm reviewhub_pgdata
```

### Rollback

If step 8 (the smoke test) fails, you can roll back to the in-compose database in under a minute:

```bash
# Revert .env
nano django_backend/.env
#  Remove the DATABASE_URL line (or comment it out). The POSTGRES_HOST=db
#  variables will compose the original in-compose URL again.

# Restart
docker compose -f docker-compose.prod.yml up -d
```

The `pgdata` volume on the droplet stays untouched until you run step 10. You can roll back any time before that.

### Why these flags

- `pg_dump --format=custom` (`-Fc`) — compressed binary archive, restorable with `pg_restore`. Smaller than plain SQL and supports selective restore later if you ever need to recover a single table.
- `pg_dump --no-owner --no-acl` — strip ownership reassignment commands. The target Managed Postgres user is `doadmin`, not `reviewhub`, so the dump's `OWNER TO reviewhub` lines would fail.
- `pg_restore --clean --if-exists` — drop existing objects on the target before restoring. Safe to re-run; safe even when the target schema is empty.
- `pg_restore --no-owner --no-acl` — same reason as above.
- No `--jobs N` parallelism because we're streaming via stdin (incompatible with parallel restore). For dogfood-scale data (<500 MB) the speedup wouldn't matter anyway.

### When NOT to use this

- **Datasets >100 GB**: the dump-and-restore window gets long. Switch to logical replication (subscribe Managed Postgres to the in-compose primary, cut over with zero downtime).
- **Schema changes mid-migration**: don't deploy migrations between the dump and the cutover. Either freeze deploys, or deploy first then dump-and-restore.
- **Major version upgrade**: this script assumes Postgres 16 ↔ Postgres 16. Upgrading versions across the migration adds risk; do the version upgrade as a separate step.
