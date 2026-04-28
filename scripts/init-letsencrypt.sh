#!/usr/bin/env bash
# init-letsencrypt.sh — first-time Let's Encrypt cert bootstrap.
#
# Adapted from https://github.com/wmnnd/nginx-certbot — the canonical
# pattern for solving the chicken-and-egg between nginx (needs a cert
# to start on :443) and certbot (needs nginx running on :80 to serve
# the ACME HTTP-01 challenge).
#
# What this does, in order:
#
#   1. Reads DOMAIN_NAME and LETSENCRYPT_EMAIL from .env
#   2. Generates a SELF-SIGNED dummy cert at the path nginx expects
#      so the frontend container can start on :443 without erroring
#   3. Brings up the frontend (nginx) — now serving HTTP on :80 with
#      the ACME challenge passthrough route, and HTTPS on :443 with
#      the dummy cert (browsers will warn — that's fine for ~30s)
#   4. Deletes the dummy cert
#   5. Asks certbot to obtain a real cert via the HTTP-01 webroot
#      challenge (writes a token under /var/www/certbot, nginx serves
#      it back, Let's Encrypt validates, cert lands)
#   6. Reloads nginx to pick up the real cert
#
# After this script runs once successfully:
#   - The cert auto-renews every 12h via the certbot service in
#     docker-compose.prod.yml (no-op until inside 30 days of expiry)
#   - The frontend container reloads nginx every 12h to pick up
#     renewed certs — no downtime
#
# Usage:
#   ./scripts/init-letsencrypt.sh
#
# Prereqs:
#   - DOMAIN_NAME and LETSENCRYPT_EMAIL set in django_backend/.env
#   - DNS A-record for $DOMAIN_NAME points at this host
#   - Port 80 reachable from the public internet (Let's Encrypt
#     validates by hitting it)
#   - docker compose v2+ installed

set -euo pipefail

cd "$(dirname "$0")/.."

ENV_FILE="${ENV_FILE:-django_backend/.env}"
COMPOSE="docker compose -f docker-compose.prod.yml"

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: $ENV_FILE not found. Copy from .env.production.example and fill in values." >&2
    exit 1
fi

# Pull DOMAIN_NAME + LETSENCRYPT_EMAIL out of .env without sourcing
# the whole file (some keys may have characters that break shell eval).
DOMAIN_NAME="$(grep -E '^DOMAIN_NAME=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' || true)"
LETSENCRYPT_EMAIL="$(grep -E '^LETSENCRYPT_EMAIL=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' || true)"
STAGING="$(grep -E '^LETSENCRYPT_STAGING=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' || echo "0")"

if [ -z "$DOMAIN_NAME" ]; then
    echo "ERROR: DOMAIN_NAME not set in $ENV_FILE" >&2
    exit 1
fi
if [ -z "$LETSENCRYPT_EMAIL" ]; then
    echo "ERROR: LETSENCRYPT_EMAIL not set in $ENV_FILE" >&2
    exit 1
fi

# Both apex + www. Let's Encrypt issues a multi-SAN cert covering both.
DOMAINS=("$DOMAIN_NAME" "www.$DOMAIN_NAME")
RSA_KEY_SIZE=4096
DATA_PATH="./certbot-data"   # local working dir for the dummy cert step

STAGING_FLAG=""
if [ "$STAGING" = "1" ]; then
    STAGING_FLAG="--staging"
    echo "→ Running against Let's Encrypt STAGING (rate-limit-friendly; certs will not be browser-trusted)"
fi

echo "→ Domain:  $DOMAIN_NAME (+ www.$DOMAIN_NAME)"
echo "→ Email:   $LETSENCRYPT_EMAIL"
echo

# ─────────────────────────────────────────────────────────────────────
# Step 1 — Pull the certbot image so the next docker compose run isn't
#          stalled by a registry pull.
# ─────────────────────────────────────────────────────────────────────
echo "→ Pulling certbot image…"
$COMPOSE pull certbot

# ─────────────────────────────────────────────────────────────────────
# Step 2 — Drop a self-signed dummy cert at the path nginx expects so
#          the frontend container can start on :443 with SOMETHING.
# ─────────────────────────────────────────────────────────────────────
echo "→ Creating self-signed dummy cert for $DOMAIN_NAME…"

# Use a one-off openssl container to write into the certbot-conf volume.
$COMPOSE run --rm --entrypoint "\
    sh -c 'mkdir -p /etc/letsencrypt/live/$DOMAIN_NAME && \
           openssl req -x509 -nodes -newkey rsa:$RSA_KEY_SIZE -days 1 \
             -keyout /etc/letsencrypt/live/$DOMAIN_NAME/privkey.pem \
             -out    /etc/letsencrypt/live/$DOMAIN_NAME/fullchain.pem \
             -subj   /CN=localhost'" certbot

# ─────────────────────────────────────────────────────────────────────
# Step 3 — Start the frontend with the dummy cert so :80 (with the
#          ACME challenge route) is reachable for the validator.
# ─────────────────────────────────────────────────────────────────────
echo "→ Starting frontend (nginx with dummy cert)…"
$COMPOSE up --force-recreate -d frontend

# Give nginx a beat to bind ports.
sleep 4

# ─────────────────────────────────────────────────────────────────────
# Step 4 — Drop the dummy cert. Certbot won't overwrite an existing
#          live/<domain> dir without --force-renewal, so we delete it
#          so the next step's `certbot certonly` issues a fresh one.
# ─────────────────────────────────────────────────────────────────────
echo "→ Deleting dummy cert…"
$COMPOSE run --rm --entrypoint "\
    sh -c 'rm -rf /etc/letsencrypt/live/$DOMAIN_NAME && \
           rm -rf /etc/letsencrypt/archive/$DOMAIN_NAME && \
           rm -rf /etc/letsencrypt/renewal/$DOMAIN_NAME.conf'" certbot

# ─────────────────────────────────────────────────────────────────────
# Step 5 — Obtain the real cert via the HTTP-01 webroot challenge.
# ─────────────────────────────────────────────────────────────────────
echo "→ Requesting Let's Encrypt cert…"

DOMAIN_ARGS=""
for d in "${DOMAINS[@]}"; do
    DOMAIN_ARGS="$DOMAIN_ARGS -d $d"
done

$COMPOSE run --rm --entrypoint "\
    certbot certonly --webroot -w /var/www/certbot \
        --email $LETSENCRYPT_EMAIL \
        $DOMAIN_ARGS \
        --rsa-key-size $RSA_KEY_SIZE \
        --agree-tos \
        --no-eff-email \
        --non-interactive \
        $STAGING_FLAG" certbot

# ─────────────────────────────────────────────────────────────────────
# Step 6 — Reload nginx to pick up the real cert.
# ─────────────────────────────────────────────────────────────────────
echo "→ Reloading nginx…"
$COMPOSE exec frontend nginx -s reload

echo
echo "✓ Done. Test with:"
echo "    curl -I https://$DOMAIN_NAME"
echo
echo "Bring the rest of the stack up:"
echo "    $COMPOSE up -d"
