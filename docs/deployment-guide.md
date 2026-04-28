# LEERA Deployment Guide — From Zero to Live

End-to-end walkthrough: blank Ubuntu 24.04 server → `https://on-boardia.com`
serving the full LEERA dogfood with auto-renewing TLS.

If you already have a server with Docker installed, skip to **Section 3**.

---

## Table of contents

1. [Prerequisites](#1-prerequisites)
2. [Provision the server](#2-provision-the-server)
3. [Install Docker + git](#3-install-docker--git)
4. [DNS setup](#4-dns-setup)
5. [Clone the repo + write the env file](#5-clone-the-repo--write-the-env-file)
6. [Build the images + apply migrations](#6-build-the-images--apply-migrations)
7. [Bootstrap Let's Encrypt TLS](#7-bootstrap-lets-encrypt-tls)
8. [Bring the stack up](#8-bring-the-stack-up)
9. [Smoke tests](#9-smoke-tests)
10. [Set up GitHub webhooks](#10-set-up-github-webhooks)
11. [Operations](#11-operations)
12. [Troubleshooting](#12-troubleshooting)
13. [Rollback](#13-rollback)

---

## 1. Prerequisites

You need:

- **A Linux host** with a public IPv4. Ubuntu 24.04 LTS recommended.
  Anything else (Debian 12, Rocky 9, etc.) works the same way with
  apt → dnf swaps. Minimum: 2 GB RAM, 2 vCPU, 20 GB disk. The
  ai-engine alone has a 1 GB memory limit.
- **A domain.** This guide uses `on-boardia.com`. You'll need DNS
  control over both the apex and the `www` subdomain.
- **An SMTP provider** (Gmail with App Password, SendGrid, Mailgun,
  Brevo, your own mail server — anything that speaks SMTP on :587).
  Required for the org-signup verification email.
- **An LLM provider API key.** Anthropic Claude is the v1 default.
- **Anthropic / GitHub / etc. accounts ready** with the API keys
  you'll paste into `.env`.

The host needs the public internet to reach:
- `letsencrypt.org` (cert validation)
- `api.anthropic.com` (LLM calls)
- `api.resend.com` if you switch to Resend (else your SMTP host on :587)
- `api.github.com` (webhook signature checks, repo fetches)

The public internet needs to reach the host on:
- **Port 80** (Let's Encrypt HTTP-01 challenge + HTTP→HTTPS redirect)
- **Port 443** (HTTPS)

---

## 2. Provision the server

Pick any provider — DigitalOcean, Hetzner, AWS Lightsail, OVH. Spin up
an Ubuntu 24.04 LTS box with at least 2 GB RAM. SSH in:

```bash
ssh root@<your-host-ip>
```

Create a non-root deploy user (don't run Docker as root in production):

```bash
adduser leera
usermod -aG sudo leera
mkdir -p /home/leera/.ssh
cp ~/.ssh/authorized_keys /home/leera/.ssh/
chown -R leera:leera /home/leera/.ssh
chmod 700 /home/leera/.ssh
chmod 600 /home/leera/.ssh/authorized_keys
```

Log out, log back in as `leera`:

```bash
ssh leera@<your-host-ip>
```

Update + install firewall:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y ufw

# Allow SSH (don't lock yourself out!), HTTP, HTTPS only
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status verbose
```

Disable root SSH login (defense in depth):

```bash
sudo sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sudo systemctl restart ssh
```

---

## 3. Install Docker + git

```bash
# Docker (official convenience script — fine for v1 dogfood)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker leera
newgrp docker     # picks up the group without re-login

# Verify
docker --version
docker compose version
docker run --rm hello-world

# Other tools
sudo apt install -y git ufw curl jq
```

Confirm `docker compose version` is **v2.x** — we use `docker compose`
(space, not hyphen). If you see v1.x, follow the official upgrade
instructions before continuing.

---

## 4. DNS setup

In your DNS provider (Cloudflare / Namecheap / etc.), create:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | `@` (or `on-boardia.com`) | `<your-host-ip>` | 300 |
| A | `www` | `<your-host-ip>` | 300 |

If your DNS provider supports **proxying** (Cloudflare orange cloud),
**turn it off** for now — we want Let's Encrypt to hit your origin
directly. You can re-enable proxying after the cert is issued.

Verify DNS has propagated **before** running the bootstrap script:

```bash
# From your laptop or another network
dig on-boardia.com +short
dig www.on-boardia.com +short
```

Both must return `<your-host-ip>`. Wait if they don't — DNS
propagation can take anywhere from seconds to ~30 minutes depending
on the provider.

---

## 5. Clone the repo + write the env file

```bash
# Clone
sudo mkdir -p /srv
sudo chown leera:leera /srv
git clone https://github.com/inno8/reviewhub.git /srv/reviewhub
cd /srv/reviewhub
git checkout main
```

Create the production env file from the template:

```bash
cp django_backend/.env.production.example django_backend/.env
```

Now edit `django_backend/.env` and fill in every `<paste-...>` and
`<your-...>` placeholder. The file has comments explaining each value.

Generate the secrets:

```bash
# Three different secrets — copy-paste one at a time
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(64))"
python3 -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(64))"
python3 -c "import secrets; print('DB_PASSWORD=' + secrets.token_urlsafe(32))"
python3 -c "import secrets; print('GITHUB_WEBHOOK_SECRET=' + secrets.token_urlsafe(32))"
python3 -c "import secrets; print('GITLAB_WEBHOOK_SECRET=' + secrets.token_urlsafe(32))"
```

Paste each into the matching `.env` line. **Never reuse a secret across
multiple variables** — if one leaks, only one boundary is broken.

For the SMTP fields, pick a provider and fill in. Quick reference:

**Gmail (App Password — Google Account → Security → 2-Step → App Passwords):**
```
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=you@gmail.com
EMAIL_HOST_PASSWORD=<16-char-app-password-no-spaces>
```

**SendGrid:**
```
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=<your-sendgrid-api-key>
```

(Other providers are listed in the `.env.production.example` comments.)

**Don't forget:** `EMAIL_FROM=noreply@on-boardia.com` — must be a sender
address your SMTP provider has authorized.

Verify your `.env` has no remaining placeholders:

```bash
grep -nE '<[a-z-]+>' django_backend/.env
# Should print NOTHING. Any output means an unfilled placeholder.
```

---

## 6. Build the images + apply migrations

```bash
cd /srv/reviewhub
docker compose -f docker-compose.prod.yml build
```

Expect ~3-5 minutes for first build (npm + pip caches need to populate).

Apply database migrations:

```bash
docker compose -f docker-compose.prod.yml run --rm django \
  python manage.py migrate --noinput
```

This brings up the `db` container (postgres 16), creates the schema,
applies all migrations through `0011_add_project_layer_and_prompt_version`,
and exits. Subsequent `up -d` will reuse the same postgres volume
(`pgdata`) and find the schema already in place.

Verify:

```bash
docker compose -f docker-compose.prod.yml run --rm django \
  python manage.py showmigrations grading | tail -15
# Every line should show [X] (applied)
```

---

## 7. Bootstrap Let's Encrypt TLS

**Pre-flight checklist** (skipping any of these will cause the script to fail):

- [ ] `dig on-boardia.com +short` returns your host IP
- [ ] `dig www.on-boardia.com +short` returns your host IP
- [ ] `curl http://on-boardia.com` from another network reaches your host (firewall + cloud security group)
- [ ] `DOMAIN_NAME` and `LETSENCRYPT_EMAIL` set in `.env`

**Strongly recommended: staging-first dance.** Let's Encrypt's production
endpoint rate-limits to 5 cert issuances per domain per week. Test the
pipeline against staging first to avoid burning budget if you've got a
config typo:

```bash
cd /srv/reviewhub

# First pass — staging
sed -i 's/^LETSENCRYPT_STAGING=.*/LETSENCRYPT_STAGING=1/' django_backend/.env
./scripts/init-letsencrypt.sh
# expect: "✓ Done"

# Verify TLS pipeline (curl will warn about untrusted cert — that's
# the staging signature; ignore for now)
curl -kI https://on-boardia.com
# Expect: HTTP/2 200 — and a Strict-Transport-Security header

# Wipe staging cert, swap to production
docker compose -f docker-compose.prod.yml run --rm --entrypoint \
  "rm -rf /etc/letsencrypt/live/on-boardia.com /etc/letsencrypt/archive/on-boardia.com /etc/letsencrypt/renewal/on-boardia.com.conf" \
  certbot

sed -i 's/^LETSENCRYPT_STAGING=.*/LETSENCRYPT_STAGING=0/' django_backend/.env
./scripts/init-letsencrypt.sh
# expect: "✓ Done"

# Verify with browser-trusted cert
curl -I https://on-boardia.com
# Expect: HTTP/2 200, no -k flag needed
```

**One-time only.** After the production cert lands, the certbot service
in docker-compose.prod.yml runs `renew` every 12 hours and renews
automatically when within 30 days of expiry. The frontend nginx
container reloads every 12 hours to pick up renewed certs without
downtime.

---

## 8. Bring the stack up

```bash
docker compose -f docker-compose.prod.yml up -d
```

Watch the first 60 seconds:

```bash
docker compose -f docker-compose.prod.yml logs -f --tail=100
```

Expected lines:

| Service | Healthy log |
|---------|-------------|
| `db` | `database system is ready to accept connections` |
| `django` | `Listening at: http://0.0.0.0:8000 (gunicorn)` |
| `ai-engine` | `Application startup complete.` |
| `frontend` | `nginx -g daemon off` + worker process started |
| `certbot` | (silent until first 12h tick) |

`Ctrl+C` to detach (services keep running).

---

## 9. Smoke tests

### 9.1 TLS + redirect

```bash
curl -I http://on-boardia.com
# Expect: HTTP/1.1 301 Moved Permanently, Location: https://on-boardia.com/

curl -I https://on-boardia.com
# Expect: HTTP/2 200, Strict-Transport-Security present
```

### 9.2 Frontend loads

In a browser: `https://on-boardia.com` → see the LEERA landing page.
Check Dev Tools console — should be no missing-asset / 404 errors.
Network tab: `index-*.js` returns 200.

### 9.3 Backend API responds

```bash
curl -i https://on-boardia.com/api/users/me/
# Expect: HTTP/2 401 (no auth — correct answer)
```

### 9.4 Org signup + email

1. Browser → `https://on-boardia.com/org-signup`
2. Fill in name, email, password, organization name → submit
3. Check the email inbox you used. The verification email should arrive
   within ~30 seconds via your SMTP provider.
4. Click the verification link → land on the dashboard

**If the email doesn't arrive:** check the django container logs for
SMTP errors:

```bash
docker compose -f docker-compose.prod.yml logs django | grep -iE "smtp|email|mail"
```

Common causes: wrong SMTP password, EMAIL_FROM not authorized by the
provider, port 587 blocked by host firewall.

### 9.5 Webhook signature verification

```bash
# From your laptop with codelens-test cloned
cd ~/dev/codelens-test
git commit --allow-empty -m "smoke test: dogfood webhook"
git push
```

In a separate terminal on the host:

```bash
docker compose -f docker-compose.prod.yml logs -f ai-engine | grep -i webhook
```

Expected: `webhook received`, `signature verified`, `evaluation enqueued`.

If you see `signature mismatch`, the `GITHUB_WEBHOOK_SECRET` in your
`.env` doesn't match the secret configured on the GitHub repo's webhook
settings. See [Section 10](#10-set-up-github-webhooks).

### 9.6 Full grading session end-to-end

1. Open a real PR on `inno8/codelens-test` (any branch with new commits)
2. Within ~60 seconds, a Nakijken Copilot session appears in the
   teacher inbox at `https://on-boardia.com/grading`
3. Click the session, verify rubric scores rendered, edit one comment,
   click **Verstuur** (Send)
4. Check the GitHub PR — the comment should appear within seconds

If 1-4 work, the full pipeline is live.

---

## 10. Set up GitHub webhooks

For `inno8/codelens-test` (or any repo you want to monitor):

1. Repo → **Settings → Webhooks → Add webhook**
2. **Payload URL:** `https://on-boardia.com/api/ai/v1/webhook/github/<project-id>`
   (the project-id comes from the LEERA UI when you connect the repo)
3. **Content type:** `application/json`
4. **Secret:** the value of `GITHUB_WEBHOOK_SECRET` from your `.env`
5. **Which events?** "Just the push event" or "Send me everything" (we
   handle pull_request, push, pull_request_review, etc.)
6. **Active:** checked
7. Save

GitHub immediately tries a `ping` event. The webhook delivery panel
shows green ✓ if everything is wired right. Red ✗ usually means
secret mismatch, wrong URL, or your domain hasn't propagated yet.

---

## 11. Operations

### Restart the stack

```bash
cd /srv/reviewhub
docker compose -f docker-compose.prod.yml restart
```

### Update from main

```bash
cd /srv/reviewhub
git pull
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml run --rm django python manage.py migrate
docker compose -f docker-compose.prod.yml up -d
```

### View logs

```bash
# All services, follow
docker compose -f docker-compose.prod.yml logs -f

# Just django
docker compose -f docker-compose.prod.yml logs -f django

# Last 100 lines without follow
docker compose -f docker-compose.prod.yml logs --tail=100 ai-engine
```

### Backup the database

```bash
# One-off dump
docker compose -f docker-compose.prod.yml exec db \
  pg_dump -U reviewhub reviewhub | gzip > backup-$(date -u +%Y%m%d-%H%M%S).sql.gz

# Restore
gunzip -c backup-2026-04-28-120000.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T db psql -U reviewhub reviewhub
```

For real production schedule daily backups via cron + ship to S3 / a
remote store. Out of scope for v1 dogfood.

### Switch from SMTP to Resend later

Edit `.env`:

```diff
-RESEND_API_KEY=
+RESEND_API_KEY=re_<your-resend-api-key>
```

Then:

```bash
docker compose -f docker-compose.prod.yml up -d django
```

`users/emails.py` automatically prefers Resend when `RESEND_API_KEY` is
set; falls back to SMTP otherwise. No code change needed.

### Manual cert renewal (debugging)

```bash
docker compose -f docker-compose.prod.yml run --rm certbot \
  certbot renew --webroot -w /var/www/certbot --force-renewal
docker compose -f docker-compose.prod.yml exec frontend nginx -s reload
```

`--force-renewal` ignores the "within 30 days of expiry" rule. Don't
use it casually — Let's Encrypt's production rate limit is 5 issuances
per domain per week.

---

## 12. Troubleshooting

### "Could not find a suitable TLS CA certificate bundle" during build

You're behind a corporate proxy that intercepts TLS. Pass the proxy CA
into the build:

```bash
docker compose -f docker-compose.prod.yml build --build-arg HTTP_PROXY=$HTTP_PROXY ...
```

### `init-letsencrypt.sh`: "Connection refused" on port 80

Cloud security group / firewall isn't open. Verify from another
network:

```bash
nc -zv on-boardia.com 80
nc -zv on-boardia.com 443
```

Both should return "succeeded". On AWS / GCP / DigitalOcean, check the
console-side security group / firewall rules separately from the
host's `ufw`.

### Let's Encrypt: "DNS problem: NXDOMAIN looking up A for ..."

DNS hasn't propagated. Check with `dig` from a different network and
wait. Don't keep retrying the cert request — you'll burn into the rate
limit.

### Let's Encrypt: "too many failed authorizations recently"

You've hit the 5-failures-per-account-per-hour limit. Wait an hour, fix
whatever was wrong, retry. Use `LETSENCRYPT_STAGING=1` while debugging.

### django: `OperationalError: connection to server at "db" failed`

The db container hasn't finished initializing yet. `docker compose
restart` the django service or wait 30 seconds and try again. If it
persists, check `db` logs for actual postgres errors.

### Webhook: "signature mismatch"

`GITHUB_WEBHOOK_SECRET` in `.env` doesn't match the secret configured
on the GitHub repo's webhook page. Re-paste it on both ends — make
sure no trailing whitespace.

### Frontend serving with insecure / wrong cert

The nginx container is using the dummy bootstrap cert because the real
issuance step failed. Re-run `init-letsencrypt.sh`. Check certbot
container logs for the actual error.

### `docker compose` says "no such service: certbot"

You're using docker-compose v1.x (binary `docker-compose`, hyphenated)
which doesn't support v3.8 features the same way. Upgrade to v2:

```bash
sudo apt remove docker-compose
# Then reinstall via the official method
sudo apt install docker-compose-plugin
```

### Resend / SMTP: "535 Authentication failed"

Check the password — Gmail App Passwords have spaces in the UI but
must be passed without them in `EMAIL_HOST_PASSWORD`. SendGrid uses
the literal username `apikey` (not your account email) and the API
key as the password.

---

## 13. Rollback

If something goes wrong post-deploy:

```bash
cd /srv/reviewhub
git log --oneline -5      # find the last-known-good commit
git checkout <good-sha>
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
```

To roll back a migration that broke something:

```bash
docker compose -f docker-compose.prod.yml run --rm django \
  python manage.py migrate grading 0010_<previous-name>
```

Migrations from this branch (`0011_add_project_layer_and_prompt_version`)
are additive only — rolling back drops the new tables but doesn't
touch existing data. Safe to undo.

---

## Useful one-liners

```bash
# Tail just the errors across all services
docker compose -f docker-compose.prod.yml logs -f 2>&1 | grep -iE 'error|fail|traceback'

# Check disk usage
docker system df

# Clean up dangling images
docker image prune -f

# Get into a Django shell on prod
docker compose -f docker-compose.prod.yml exec django python manage.py shell

# Get into postgres
docker compose -f docker-compose.prod.yml exec db psql -U reviewhub reviewhub

# Inspect a running container
docker compose -f docker-compose.prod.yml exec frontend sh
```

---

## What's NOT in this guide (intentionally)

- **Multi-host orchestration / k8s.** v1 dogfood is one box. Scale
  later.
- **Read replicas / connection pooling.** Postgres 16 in a single
  container handles a few cohorts comfortably; revisit at ~10+
  schools.
- **Centralized log aggregation.** `docker compose logs` is enough
  for v1. Add Loki/Grafana when log volume hurts.
- **Observability dashboards.** Skip until pain. The ops dashboard
  inside LEERA covers cost + activity already.
- **Background-task workers.** ai-engine handles its own queue. No
  Celery / RQ until we need it.

These all become real concerns in v1.1+. For pre-pitch dogfood,
they're complexity we don't need to pay for yet.
