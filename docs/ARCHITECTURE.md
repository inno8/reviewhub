# ReviewHub Architecture — Nakijken Copilot v1

This document is the "deep dive" for the grading subsystem shipped under
Scope B1 (Workstreams A–D + Bucket 1). It assumes you've skimmed
`CLAUDE.md` and read `docs/README.md`.

Companion docs:
- [API reference](./API.md) — every endpoint, body shapes, examples
- [Teacher workflow](./TEACHER_WORKFLOW.md) — daily flow walkthrough
- [Learning algorithm](./LEARNING_ALGORITHM.md) — the Bayesian skill model in detail
- [ARCHITECTURE_V2.md](./ARCHITECTURE_V2.md) — pre-Nakijken historical design

---

## Domain model

### Hybrid state: old "Classroom" → new "Cohort + Course"

v1 Scope B1 (Workstream A) introduced the **Cohort / Course** split that
mirrors Dutch MBO-4 ICT education structure:

| Dutch (MBO-4) | English model | Notes                                                           |
|---------------|---------------|-----------------------------------------------------------------|
| Klas          | `Cohort`      | Group of ~20 students who study together for a year.            |
| Vak           | `Course`      | One subject taught by one teacher (primary docent) in a cohort. |
| Leerling      | `User` (role=student) | One student belongs to ONE cohort at a time.            |
| Docent        | `User` (role=teacher) | Owns one or more courses; can co-teach others.          |

The licensing unit is the **Cohort** (€200/cohort/month). A cohort
typically has 3–6 courses (Frontend, Backend, Databases, DevOps, …) each
with a different teacher and rubric.

```
                         ┌─────────────────┐
                         │  Organization   │  (the school / bootcamp)
                         └────┬────────────┘
                              │ 1..N
              ┌───────────────┼────────────────┐
              │               │                │
              ▼               ▼                ▼
         ┌────────┐     ┌──────────┐     ┌──────────┐
         │ Cohort │◀────│  Course  │────▶│  Rubric  │
         │ (klas) │ 1..N│  (vak)   │ N..1│          │
         └───┬────┘     └────┬─────┘     └──────────┘
             │               │
             │ 1..N          │ 1..N
             ▼               ▼
   ┌──────────────────┐   ┌────────────┐
   │ CohortMembership │   │ Submission │ (one PR = one row)
   └───┬──────────────┘   └─────┬──────┘
       │ 1..1                   │ 1..1
       ▼                        ▼
   ┌────────┐             ┌─────────────────┐
   │  User  │             │ GradingSession  │ (the AI draft + review state)
   │ (student)            └─────┬───────────┘
   └────────┘                   │ 1..N
                                ▼
                        ┌────────────────┐
                        │ PostedComment  │ (idempotent GitHub post ledger)
                        └────────────────┘
```

**Key invariants**
- `CohortMembership.student` is a `OneToOneField` — a student is in exactly one cohort.
- `Submission` is the PR-level grouping; a PR with N commits = 1 Submission with N Evaluations.
- `GradingSession` is a `ForeignKey` to `Submission` — one session per iteration. The PR (not the commit) is what gets graded; teacher regrades after a student push spawn a new session linked back via `superseded_by`.
- `Course.owner` must have `role=teacher` (or admin). `Course.secondary_docent` is optional.

### Auxiliary models

| Model              | Purpose                                                                           |
|--------------------|-----------------------------------------------------------------------------------|
| `Rubric`           | Criteria + level definitions + docent voice calibration. Org-scoped or `is_template=True`. |
| `WebhookDelivery`  | Idempotency ledger for GitHub webhook re-delivery. Keyed by `X-GitHub-Delivery`.  |
| `PostedComment`    | Idempotency ledger for GitHub PR review comments. Keyed by `client_mutation_id`.  |
| `LLMCostLog`       | Append-only cost metering. Admin-internal only; never shown to teachers.          |
| `SessionEvaluation`| Through-table linking `GradingSession` to existing `Evaluation` commits.          |

See `django_backend/grading/models.py` for the canonical definitions.

---

## Permissions

The grading app uses a layered permission matrix. Cross-org access always
returns 404 (not 403) to avoid leaking row existence — see
`test_security_org_isolation.py` for the full matrix.

### Permission classes

| Class                       | Applied to                                             | Who passes?                                                                                   |
|-----------------------------|--------------------------------------------------------|-----------------------------------------------------------------------------------------------|
| `IsTeacher` / `IsTeacherOrAdmin` | Most grading writes (rubrics, sessions)            | `role=teacher` or `role=admin` or `is_superuser`                                              |
| `IsOrgAdmin`                | Cohort CRUD, course reassign                           | `role=admin` or `is_superuser`                                                                |
| `IsCourseOwnerOrAdmin`      | Course update / archive                                | Admin OR teacher where `course.owner_id == user.id`                                           |
| `IsCohortVisible`           | Cohort detail visibility                               | Admin in same org OR teacher of a course in cohort OR enrolled student                        |
| `IsTeacherOrReadOnlyStudent`| Submission viewset                                     | Teachers: full access. Students: read-only, own rows only.                                    |
| `CanViewStudent` / `can_view_student()` | Student intelligence endpoints            | Self OR admin in same org OR teacher who owns/co-teaches a course in the student's cohort     |
| `_can_view_cohort_intelligence()` | Cohort aggregated intel (recurring errors)       | Same as `IsCohortVisible` except: students enrolled in the cohort get **403**, not 200.       |

### The org-isolation floor

Every ViewSet's `get_queryset()` starts from
`Model.objects.for_user(user)` — the `OrgScopedManager` filters by
`organization_id` and is the single place a cross-org leak could
happen. It is the ONE invariant that protects every tenant.

### The "why 404 instead of 403" pattern

Returning 403 for "exists but you can't see it" leaks which cohort /
student IDs are real. Every grading endpoint that could leak raises
`Http404` instead. The lone exception is `CohortRecurringErrorsView`
which returns **403** for students enrolled in a cohort — there, the
student already knows the cohort exists (they're in it), so 403 is
honest and 404 would be a lie.

---

## Grading pipeline

```
┌───────────────┐      ┌──────────────┐      ┌─────────────────┐
│ GitHub PR     │      │ webhooks.py  │      │  Submission     │
│ opened / sync │─────▶│  github_     │─────▶│   (upserted)    │
│               │  POST│  webhook     │      │                 │
└───────────────┘      └──────────────┘      └────────┬────────┘
                              │                       │
                              ▼                       ▼
                      ┌──────────────┐        ┌─────────────────┐
                      │  Webhook-    │        │ GradingSession  │
                      │  Delivery    │        │  state=pending  │
                      │  (dedupe)    │        └────────┬────────┘
                      └──────────────┘                 │
                                                       │  teacher clicks
                                                       │  "Generate draft"
                                                       ▼
                                              ┌─────────────────┐
                                              │  state=drafting │
                                              └────────┬────────┘
                                                       │  ai_engine call
                                                       ▼
                                              ┌─────────────────┐
                                              │  state=drafted  │
                                              └────────┬────────┘
                                                       │  teacher opens
                                                       ▼
                                              ┌─────────────────┐
                                              │ state=reviewing │  ← stopwatch starts
                                              └────────┬────────┘
                                                       │  teacher edits + Send
                                                       ▼
                                              ┌─────────────────┐
                                              │  state=sending  │  ← lock
                                              └────┬──────────┬─┘
                                         success  │          │ partial failure
                                                  ▼          ▼
                                          ┌──────────┐  ┌──────────┐
                                          │  posted  │  │ partial  │ → Resume → sending
                                          └──────────┘  └──────────┘
```

### State machine

`GradingSession.state` transitions are enforced by `can_transition_to()`
in `models.py`. Allowed edges:

```
pending     → drafting, discarded
drafting    → drafted, failed, discarded
drafted     → reviewing, drafting (regenerate), discarded
reviewing   → sending, drafting, discarded
sending     → posted, partial
partial     → sending (resume), posted, discarded
failed      → drafting (retry), discarded
posted      (terminal)
discarded   (terminal)
```

Every state flip happens under `select_for_update()` inside a short
transaction — network I/O to GitHub / the LLM happens **outside** the
transaction to avoid lock-while-waiting-on-network.

### Idempotency invariants

1. **Webhook re-delivery** → `WebhookDelivery.unique(provider, delivery_id)` rejects dupes in <5ms.
2. **Double-click Send** → the first click flips state to `sending`; the second sees `sending` and returns 202 without re-posting.
3. **Partial Send + Resume** → each comment's `client_mutation_id` hash is checked against `PostedComment`; duplicates skip silently.

---

## Skill intelligence layer

The `skills` app (separate from `grading`) maintains a Bayesian model of
each student's per-skill mastery. Teachers see this data via the
Workstream D student-intelligence endpoints; students see their own
aggregate on the Developer Journey.

| Model              | Layer | Purpose                                                                        |
|--------------------|-------|--------------------------------------------------------------------------------|
| `SkillCategory`    | taxonomy | 8 categories (Code Quality, Security, Testing, …).                          |
| `Skill`            | taxonomy | 32 individual skills (4 per category).                                      |
| `SkillObservation` | L1    | Per-commit, per-skill raw evidence: `quality_score × complexity_weight`.       |
| `SkillMetric`      | L1    | Per-user, per-project, per-skill aggregate: `bayesian_score` + `confidence`.   |
| `LearningProof`    | L2    | Fix & Learn → behavioral proof: PENDING → PROVEN / RELAPSED / REINFORCED.       |
| `GrowthSnapshot`   | L2    | Weekly roll-up for timeline UI (writer is v1.1 work — not yet populated).      |

### Bayesian scoring (the short version)

- Every metric **starts at 50** (uncertain) with **confidence 0.0** — not 100 (optimistic).
- New observations blend in at a decaying `learning_rate` that shrinks as confidence grows.
- Complexity weight (`simple=0.4`, `medium=0.7`, `complex=1.0`) gates how much confidence each observation yields.
- A level label (`novice` → `master`) is only displayed once confidence crosses `CONFIDENCE_PRELIMINARY=0.15`. Early students see "insufficient data" instead of a fake 100.

Full derivation, constants and edge cases are in
[LEARNING_ALGORITHM.md](./LEARNING_ALGORITHM.md).

### Teacher-view vs student-view

The Workstream D endpoints (`/students/<id>/snapshot/`, `/trajectory/`,
`/pr-history/`, and `/cohorts/<id>/recurring-errors/`) aggregate the
same underlying tables but shape the response for the teacher's
question "what does this student need from me right now", not the
student's "how am I doing". See `views_student_intelligence.py` for the
per-endpoint shape and [API.md](./API.md) for examples.

---

## Directory layout (grading slice)

```
django_backend/
├── grading/
│   ├── models.py                 ← Cohort, Course, Submission, GradingSession, …
│   ├── permissions.py            ← IsTeacher, IsOrgAdmin, IsCourseOwnerOrAdmin, …
│   ├── views.py                  ← CohortViewSet, CourseViewSet, GradingSessionViewSet
│   ├── views_student_intelligence.py  ← Workstream D endpoints
│   ├── webhooks.py               ← /webhooks/github/ entrypoint
│   ├── serializers.py
│   ├── services/
│   │   ├── rubric_grader.py      ← ai_engine call + PII redaction
│   │   ├── github_fetcher.py     ← live PR diff fetch at grade-time
│   │   ├── github_poster.py      ← all-or-nothing comment post + Resume
│   │   └── pii_redaction.py
│   └── tests/
│       ├── test_cohort_lifecycle.py
│       ├── test_course_lifecycle.py
│       ├── test_student_intelligence.py
│       ├── test_webhooks.py
│       ├── test_github_poster.py
│       ├── test_rubric_eval.py
│       └── test_security_org_isolation.py
├── skills/                       ← Bayesian skill model (separate app)
└── evaluations/                  ← Pre-existing per-commit evals + findings
```

---

## Open questions / v1.1 backlog

- `GrowthSnapshot` is read today via the trajectory endpoint but nothing writes it. A weekly Celery aggregator is queued for v1.1.
- Webhook → course routing picks the first course in the cohort. Per-course routing via branch / PR-title conventions is tracked for v1.1.
- Generate-draft is synchronous. Move to background worker when p95 > 8s in production.
- `suggested_interventions` on the snapshot endpoint always returns `[]` — recommender is v1.1.
