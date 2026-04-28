# Grading API reference — Scope B1

Concise reference for the endpoints added in Workstreams A–D.
Unless otherwise noted:

- Base URL: `/api/grading/`
- Auth: `Authorization: Bearer <JWT>` (except `/webhooks/github/`)
- Content type: `application/json`
- Cross-org access returns **404** (not 403) — see
  [ARCHITECTURE.md](./ARCHITECTURE.md#permissions).

Jump:
- [Cohorts](#cohorts) · [Courses](#courses) · [Student intelligence](#student-intelligence) · [Webhook (recap)](#webhook-recap) · [Send (recap)](#send-recap)

---

## Cohorts

### `GET /cohorts/`

| Permission | Any authenticated user; scoped by role (see ARCHITECTURE.md) |
|------------|---------------------------------------------------------------|
| Query param | `include_archived=true` to include soft-archived cohorts      |

Response: array of cohorts the user can see.

```json
[
  {
    "id": 12, "org": 3, "name": "Klas 2A ICT 2026-2027",
    "year": "2026-2027", "starts_at": "2026-09-01", "ends_at": "2027-06-30",
    "archived_at": null, "student_count": 19, "course_count": 4,
    "created_at": "2026-08-15T09:00:00Z", "updated_at": "2026-08-15T09:00:00Z"
  }
]
```

### `POST /cohorts/`

| Permission | `IsOrgAdmin` |
|------------|--------------|

```json
{ "name": "Klas 2B ICT 2026-2027", "year": "2026-2027",
  "starts_at": "2026-09-01", "ends_at": "2027-06-30" }
```

Returns the created cohort. `org` is set from the caller automatically.

### `PATCH /cohorts/{id}/` · `POST /cohorts/{id}/archive/`

Admin-only. Hard `DELETE` is disabled (returns 405) — use `archive/`.
Re-archiving is a no-op.

### `GET /cohorts/{id}/members/`

List active cohort memberships. Visible to admin, any teacher of a
course in the cohort, or the students themselves.

```json
[
  { "id": 88, "cohort": 12, "student": 214,
    "student_email": "jan.deboer@school.nl",
    "student_name": "Jan de Boer",
    "student_repo_url": "https://github.com/jandeboer/q3-assignment",
    "joined_at": "2026-09-04T10:12:00Z" }
]
```

### `POST /cohorts/{id}/members/`

| Permission | `IsOrgAdmin` |
|------------|--------------|

```json
{ "student_id": 214, "student_repo_url": "https://github.com/jandeboer/q3-assignment" }
```

Returns the membership (201 new, 200 if already active). If the student
is in a **different** cohort, returns 400 with a remove-first error —
transfers are explicit in v1.

### `DELETE /cohorts/{id}/members/{membership_id}/`

Admin-only soft-delete (sets `removed_at`).

### `GET /cohorts/{id}/recurring-errors/`

| Permission | Admin in same org; teacher of a course in the cohort. Enrolled students: **403**. |

Top-10 unresolved `Pattern` records aggregated across the active student
set in this cohort — "what is my class weak at".

```json
{
  "cohort": { "id": 12, "name": "Klas 2A ICT 2026-2027", "student_count": 19 },
  "top_patterns": [
    {
      "pattern_key": "bare_except",
      "pattern_type": "code_smell",
      "affected_students": 11,
      "total_frequency": 38,
      "avg_frequency_per_student": 3.5,
      "severity": "warning",
      "last_seen_days_ago": 2,
      "example_findings": [
        "Replaced broad `except:` with specific exception class",
        "Bare except hid a NameError for 6 commits"
      ]
    }
  ],
  "summary": {
    "students_with_unresolved_patterns": 14,
    "total_unresolved_patterns": 52,
    "most_affected_category": "code_smell"
  }
}
```

---

## Courses

### `GET /courses/`

| Permission | Any authenticated user; scoped by role |
|------------|----------------------------------------|
| Query param | `include_archived=true`                |

Scoping:
- admin: every course in the org
- teacher: own + secondary + sibling courses in cohorts they teach
- student: courses in their own cohort

### `POST /courses/`

| Permission | Admin or teacher. |
|------------|-------------------|

```json
{ "cohort": 12, "name": "Frontend (Vue 3)", "rubric": 5,
  "source_control_type": "github_org", "target_branch_pattern": "main" }
```

- Admins may set `owner` to any teacher in the org.
- Teachers may only create courses they'll own themselves. If the cohort
  already has courses and the teacher doesn't teach any of them, 403.

### `PATCH /courses/{id}/`

| Permission | `IsCourseOwnerOrAdmin` (owner-only for teachers) |

Non-admins cannot change `owner` via PATCH — use `/reassign/`.

### `POST /courses/{id}/archive/`

Owner or admin. Soft-archives the course.

### `POST /courses/{id}/reassign/`

| Permission | `IsOrgAdmin` |

```json
{ "new_owner_id": 417 }
```

Swaps `course.owner`. The new owner must be a teacher/admin in the same
org. Used when a teacher leaves school or hands off mid-term.

### `GET`/`POST`/`DELETE` `/courses/{id}/members/`

Legacy Classroom-era endpoint bridged to `Cohort.memberships`. Prefer
`/cohorts/{id}/members/` for new integrations — this shim exists so v0.x
UI keeps working during the Cohort migration.

---

## Student intelligence

All four endpoints return 404 when the caller cannot view the student or
cohort (except `recurring-errors` for enrolled students → 403, see above).
Visibility is checked by `can_view_student()` / `_can_view_cohort_intelligence()`.

### `GET /students/{id}/snapshot/`

| Permission | Self, admin in same org, or teacher of the student's cohort |

Lightweight bundle for the grading-session side panel: radar, top
recurring errors, recent activity.

```json
{
  "student": { "id": 214, "name": "Jan de Boer", "email": "…",
                "cohort": { "id": 12, "name": "Klas 2A ICT 2026-2027" } },
  "skill_radar": [
    { "category": "Code Quality", "score": 62.3, "confidence": 0.41,
      "level_label": "competent", "trend": "up" }
  ],
  "recurring_patterns": [
    { "pattern_key": "bare_except", "pattern_type": "code_smell",
      "frequency": 4, "last_seen_days_ago": 3, "severity": "warning" }
  ],
  "trending_up": ["Code Quality"],
  "trending_down": [],
  "recent_activity": { "prs_last_30d": 6, "avg_bayesian_score": 57.8 },
  "suggested_interventions": []
}
```

### `GET /students/{id}/trajectory/?weeks=12`

| Permission | Same as snapshot |
| Query param | `weeks` (default 12, clamp 1–52) |

Weekly roll-up of skill observations + milestone markers for timeline UI.

```json
{
  "student": { "id": 214, "name": "Jan de Boer", "email": "…" },
  "weeks": [
    { "week_start": "2026-02-02",
      "avg_score_per_category": { "Code Quality": 55.1, "Security": 42.0 },
      "prs_count": 2, "findings_count": 9 }
  ],
  "milestones": [
    { "date": "2026-03-15", "event": "Concept proven", "skill": "Input validation" },
    { "date": "2026-04-02", "event": "Relapse detected", "skill": "Error handling" }
  ]
}
```

### `GET /students/{id}/pr-history/?limit=20`

| Permission | Same as snapshot |
| Query param | `limit` (default 20, clamp 1–100) |

Recent grading sessions for this student — the timeline list feeding the
teacher's student-profile view.

```json
{
  "student": { "id": 214, "name": "Jan de Boer", "email": "…" },
  "sessions": [
    {
      "id": 908, "pr_url": "https://github.com/jandeboer/q3-assignment/pull/14",
      "pr_number": 14, "pr_title": "Add authentication middleware",
      "repo_full_name": "jandeboer/q3-assignment",
      "submitted_at": "2026-04-15T11:02:00Z",
      "graded_at":   "2026-04-15T14:48:00Z",
      "state": "posted",
      "rubric_score_avg": 2.75,
      "findings_count": 4,
      "course_name": "Backend (Django)"
    }
  ]
}
```

---

## Webhook (recap)

### `POST /webhooks/github/`

| Auth | **Unauthenticated.** Security boundary is `X-Hub-Signature-256` HMAC verification when `GITHUB_WEBHOOK_SECRET` is set. |

Handled events: `pull_request` with action in `(opened, reopened, synchronize, closed)`.

Flow: dedupe via `X-GitHub-Delivery` → match PR to a `CohortMembership`
→ pick a `Course` in the cohort → upsert `Submission` → ensure a
`GradingSession` exists in `pending`. See
[ARCHITECTURE.md — Grading pipeline](./ARCHITECTURE.md#grading-pipeline).

Response codes:
- `200` with `{"deduped": true}` — re-delivered event, no-op.
- `200` with `{"matched": false, ...}` — no cohort membership matched this repo.
- `200` with `{"submission_id", "session_id", "session_created"}` — happy path.
- `400` — invalid JSON or missing required payload fields.
- `403` — signature verification failed.

Full field reference in `django_backend/grading/webhooks.py`.

---

## Send (recap)

### `POST /sessions/{id}/send/`

| Permission | `IsTeacher` (teacher or admin). |

Posts the session's `final_comments` + `final_summary` to the PR on
GitHub. Under the hood:

1. Locks the row with `select_for_update()`.
2. Flips `state=sending` inside a short transaction.
3. Calls `github_poster.post_all_or_nothing()` **outside** the transaction.
4. On success: state → `posted`, `posted_at` set, 200.
5. On partial failure: state → `partial`, 207 with `failed_at_comment_idx`. Resume via `POST /sessions/{id}/resume/`.
6. On `PRClosedError`: 409. On `GitHubAuthExpired`: 401 (teacher re-authorizes). On other GitHub errors: 502.

Idempotency guarantees:
- A double-click on Send: second call sees `state=sending`, returns 202 without re-posting.
- Each comment's `client_mutation_id` hash is matched against `PostedComment` — duplicates skip silently. This IS the Resume logic.

Related actions on the same viewset (all `IsTeacher`):
- `POST /sessions/{id}/start_review/` — `drafted → reviewing` + starts stopwatch.
- `POST /sessions/{id}/generate_draft/` — kick off AI grading (sync for v1).
- `POST /sessions/{id}/resume/` — resume a `partial` session.

Listing / detail: `GET /sessions/` (inbox) with filters `course=`,
`state=`, `overdue=true`.
