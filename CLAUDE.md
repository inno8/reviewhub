# ReviewHub — Nakijken Copilot

ReviewHub is the product; **Nakijken Copilot** is the v1 scope targeting
Dutch MBO-4 ICT teachers (docenten). Teachers assign their students code
projects on GitHub; students push PRs; the copilot drafts rubric-based
comments in the teacher's voice; the teacher reviews, tweaks, and clicks
Send. Target: p50 review ≤ 5 min per PR (from ~20 min unaided), without
ceding the final word to an AI.

For the long-form deep-dive see **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

## Design System

Always read **[docs/DESIGN.md](docs/DESIGN.md)** before making any visual or UI
decision. All font choices, colors, spacing, motion, and aesthetic direction are
defined there. Do not deviate without explicit user approval. In QA mode, flag any
code that doesn't match DESIGN.md.

## Directory layout

```
reviewhub/
├── ai_engine/           FastAPI — LLM adapters, rubric grader, PII redaction
├── django_backend/      Django REST Framework API (main backend)
│   ├── grading/         Nakijken Copilot v1 — Cohort, Course, GradingSession
│   ├── skills/          Bayesian skill model (SkillMetric, LearningProof, …)
│   ├── evaluations/     Per-commit evals + findings (pre-Nakijken, reused)
│   ├── users/           Auth, Organization, GitProviderConnection
│   └── projects/        Legacy project model (being phased out)
├── frontend/            Vue 3 + Vite + Tailwind — teacher/student UI
├── docs/                Docs (you are here)
└── tests/               Integration tests
```

## Key models

| Model              | Where                    | What it is                                                                |
|--------------------|--------------------------|---------------------------------------------------------------------------|
| `Cohort`           | `grading/models.py`      | A klas (MBO-4 class). Licensing unit (€200/cohort/month).                 |
| `Course`           | `grading/models.py`      | A vak (subject) inside a cohort. One teacher, one rubric.                 |
| `CohortMembership` | `grading/models.py`      | Student ↔ cohort link. One cohort per student (OneToOne).                 |
| `Submission`       | `grading/models.py`      | One PR = one row.                                                         |
| `GradingSession`   | `grading/models.py`      | The AI-draft + docent-review state machine (FK to Submission; one per iteration). |
| `Rubric`           | `grading/models.py`      | Criteria + level definitions + docent voice calibration.                  |
| `SkillMetric`      | `skills/models.py`       | Bayesian per-skill score. Starts at 50 (uncertain), not 100 (optimistic). |
| `LearningProof`    | `skills/models.py`       | Fix & Learn → behavioral proof state (PROVEN / RELAPSED / REINFORCED).    |

## Run the stack locally

Three services — run each in its own terminal:

```bash
# 1. Django backend — http://localhost:8000
cd django_backend
python -m venv venv && source venv/bin/activate  # first time only
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

# 2. ai_engine (FastAPI) — http://localhost:8001
cd ai_engine
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001

# 3. Frontend (Vite dev server) — http://localhost:5173
cd frontend
npm install
npm run dev
```

Docker alternative (pin-compatible with prod):

```bash
docker-compose up
```

Production config example: `docker-compose.prod.yml` +
`django_backend/.env.production.example`.

## Run tests

```bash
# Django unit + integration — this is the main suite
cd django_backend
pytest

# Grading slice only
pytest grading/tests/

# A single file
pytest grading/tests/test_cohort_lifecycle.py -v

# ai_engine tests
cd ../ai_engine
pytest tests/
```

Test database uses SQLite via `pytest-django`. No fixtures needed for most
tests — they set up their own `Organization`, `User`, `Cohort` inline.
See `grading/tests/fixtures/` for the shared diff/rubric fixtures.

## API surfaces

- `/api/grading/cohorts/` · `/courses/` · `/sessions/` · `/submissions/`
- `/api/grading/students/<id>/snapshot|trajectory|pr-history/`
- `/api/grading/cohorts/<id>/recurring-errors/`
- `/api/grading/webhooks/github/` — the only unauthenticated endpoint
- `/api/grading/ops/…` — superuser-only admin dashboards

Full reference in **[docs/API.md](docs/API.md)**.
Teacher walk-through in **[docs/TEACHER_WORKFLOW.md](docs/TEACHER_WORKFLOW.md)**.

## Conventions worth knowing

- **Org isolation**: every ViewSet's `get_queryset()` starts from
  `Model.objects.for_user(user)` — the `OrgScopedManager` filters by
  `organization_id`. Cross-org access returns **404** (not 403) to avoid
  leaking row existence. See
  `grading/tests/test_security_org_isolation.py`.
- **State machine**: `GradingSession.can_transition_to()` guards every
  transition. Network I/O (GitHub, LLM) happens **outside**
  `select_for_update()` transactions — lock-while-waiting-on-network
  is the anti-pattern.
- **Idempotency**: webhook redelivery → `WebhookDelivery`; double-Send
  → `state=sending` lock; partial post → `PostedComment.client_mutation_id`.
- **Naming**: the old "Classroom" is now **Cohort + Course**. v0 UI still
  has `/courses/{id}/members/` as a shim; new integrations should prefer
  `/cohorts/{id}/members/`.

## Dogfood data

`docs/dogfood-eval/` holds templates for the May 15 validation run
(manual timing log, rubric-accuracy scoresheet, weekly reflection).

---

# gstack

Use the /browse skill from gstack for all web browsing. Never use mcp__claude-in-chrome__* tools.

## Available skills

/office-hours, /plan-ceo-review, /plan-eng-review, /plan-design-review, /design-consultation, /design-shotgun, /design-html, /review, /ship, /land-and-deploy, /canary, /benchmark, /browse, /connect-chrome, /qa, /qa-only, /design-review, /setup-browser-cookies, /setup-deploy, /retro, /investigate, /document-release, /codex, /cso, /autoplan, /plan-devex-review, /devex-review, /careful, /freeze, /guard, /unfreeze, /gstack-upgrade, /learn

## gstack (recommended)

This project uses [gstack](https://github.com/garrytan/gstack) for AI-assisted workflows.
Install it for the best experience:

```bash
git clone --depth 1 https://github.com/garrytan/gstack.git ~/.claude/skills/gstack
cd ~/.claude/skills/gstack && ./setup --team
```

Skills like /qa, /ship, /review, /investigate, and /browse become available after install.
Use /browse for all web browsing. Use ~/.claude/skills/gstack/... for gstack file paths.

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- Save progress, checkpoint, resume → invoke checkpoint
- Code quality, health check → invoke health
