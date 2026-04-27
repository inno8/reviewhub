# Dogfood Deploy Runbook (May 2026)

The exact steps to bring the LEERA dogfood instance live for the May 7
Media College Portfolio Day pitch. Built around the
`feat/grading-nakijken-copilot-v1` branch landing this push.

---

## Pre-deploy checklist

Verify each before touching production:

- [ ] PR #4 CI is green (`gh pr checks 4`)
- [ ] PR #4 has been reviewed + approved
- [ ] Production database is reachable (psql connect from deploy host)
- [ ] DNS for the dogfood domain points at the deploy host
- [ ] SSL certs are in place on the deploy host (Let's Encrypt, Caddy, or behind a reverse proxy)
- [ ] You have the env values ready (see `.env.production.example`):
  - `SECRET_KEY` — `python -c "import secrets; print(secrets.token_urlsafe(64))"`
  - `JWT_SECRET_KEY` — same generator, different value
  - `DB_PASSWORD` — set when creating the postgres user
  - `RESEND_API_KEY` — from resend.com dashboard
  - `WEBHOOK_BASE_URL` — public URL where GitHub can reach the AI engine
  - `ALLOWED_HOSTS` — your dogfood domain(s)
  - `CORS_ALLOWED_ORIGINS` — the frontend URL
  - `EMAIL_FROM` — verified sender on Resend

---

## 1. Merge PR #4 to main

```bash
gh pr merge 4 --squash
# Or via GitHub UI if you want a manual review pass
```

After merge, `main` has all 94 commits including the deploy infra from
this branch. The next deploy reads from `main`.

---

## 2. Pull on the deploy host + write the production env

SSH to the deploy host:

```bash
git clone https://github.com/inno8/reviewhub.git /srv/reviewhub
# or, if already cloned:
cd /srv/reviewhub && git fetch && git checkout main && git pull
```

Create the production env file from the template:

```bash
cd /srv/reviewhub
cp django_backend/.env.production.example django_backend/.env
# edit django_backend/.env — fill in every value the template flags as <generate-...>
```

---

## 3. Apply migrations to the production DB

The two new production-hardening migrations need to run before bringing
the app up. Order matters — batch first (changes a FK), then evaluations
(adds a field).

```bash
cd /srv/reviewhub/django_backend

# Activate venv if you have one, or use docker:
docker compose -f ../docker-compose.prod.yml run --rm django python manage.py migrate batch 0004
docker compose -f ../docker-compose.prod.yml run --rm django python manage.py migrate evaluations 0007

# Or apply ALL pending migrations in one go (safer if you've added more):
docker compose -f ../docker-compose.prod.yml run --rm django python manage.py migrate --noinput
```

Verify after:

```sql
-- in psql
\dt batch_batchjob;          -- confirms BatchJob still exists
\d evaluations_evaluation;   -- confirms prompt_version column landed
SELECT id, prompt_version FROM evaluations_evaluation LIMIT 3;
```

---

## 4. Build + bring services up

```bash
cd /srv/reviewhub
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
```

Watch logs for the first 60 seconds:

```bash
docker compose -f docker-compose.prod.yml logs -f --tail=100
```

Expect:
- django: `Listening at: http://0.0.0.0:8000 (gunicorn)`
- ai-engine: `Application startup complete` from uvicorn
- db: `database system is ready to accept connections`

---

## 5. Smoke test

Run these from your laptop (or wherever has internet) against the
dogfood domain. Replace `https://leera.example.com` with the actual URL.

### 5.1 Django responds

```bash
curl -i https://leera.example.com/api/health/   # should return 200 if you have a health endpoint
curl -i https://leera.example.com/api/users/me/  # should return 401 without auth (this is the right answer)
```

### 5.2 Frontend loads

Visit `https://leera.example.com` in a browser. Expect:
- The login page renders, dark theme, LEERA wordmark visible
- No console errors related to missing assets
- JS bundle loads (Network tab: index-*.js comes back 200)

### 5.3 Org signup flow

1. Visit `/org-signup`
2. Create a test organization with your email
3. Expect: an email arrives via Resend within ~30 seconds
4. Click the verification link, land on dashboard

### 5.4 Webhook signature verification

Trigger a test push from `inno8/codelens-test`:

```bash
cd ~/dev/codelens-test
git commit --allow-empty -m "smoke test: dogfood webhook"
git push
```

In dogfood logs, expect:
- ai-engine: webhook received, signature verified, evaluation enqueued
- django: webhook fan-out from grading webhook → ai_engine succeeded

If you see `webhook signature mismatch`, the `GITHUB_WEBHOOK_SECRET`
between the two services doesn't agree. Both must be the same value.

### 5.5 One full grading session

1. Open a PR on `inno8/codelens-test` (the test branch from the demo)
2. Within ~60s, expect a Nakijken Copilot session to appear in the teacher inbox at `/grading/inbox`
3. Open the session, verify rubric scores rendered, edit one comment, click Send
4. Confirm the comment posted to the actual PR on github.com

If steps 3-4 work end-to-end, the full pipeline is live.

---

## 6. Post-deploy notes

### Things to monitor for the first 24 hours

- Sentry / log aggregator for unhandled exceptions
- Database query times — `EXPLAIN ANALYZE` any slow page from the QA pass
- Resend dashboard for email delivery rates
- ai_engine LLM token usage (cost projection)

### Rollback plan

If anything goes wrong:

```bash
cd /srv/reviewhub
git checkout HEAD~1  # back to pre-merge main
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d --build
```

Migrations don't auto-rollback — to undo:

```bash
docker compose -f docker-compose.prod.yml run --rm django python manage.py migrate batch 0003
docker compose -f docker-compose.prod.yml run --rm django python manage.py migrate evaluations 0006
```

(Reverts to the migration before each `production_hardening` one. Verify you don't have data depending on the new column before running.)

### Known technical debt

See `docs/TODO.md` for the 44 frontend TS errors and other items
explicitly punted to ship in time for the May 7 pitch.
