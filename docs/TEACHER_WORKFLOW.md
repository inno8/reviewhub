# Teacher workflow — Nakijken Copilot v1

This is the end-to-end daily flow for a docent (teacher) using
Nakijken Copilot. Written in English first; a Dutch translation
follows in May once the v0.9 UI is stable.

Related docs:
- [ARCHITECTURE.md](./ARCHITECTURE.md) — system + permission model
- [API.md](./API.md) — endpoint reference

> Screenshots marked `[SCREENSHOT: …]` will be filled in after the
> v0.9 deploy during the May 15 dogfood (tracked in
> `docs/dogfood-eval/`).

---

## Step 1 — Teacher joins their school

The org admin invites the teacher by email from `/org/members`. The
teacher receives an email, sets a password, and lands on the
org-members dashboard.

- `/org/members` is empty at first (no cohorts assigned yet).
- `/grading/inbox` shows an empty state: "No submissions yet. Ask
  your admin to create a cohort and assign students."

`[SCREENSHOT: /org/members — teacher's first view, empty state]`

---

## Step 2 — Admin sets up the cohort + course

The admin (usually the coordinator for MBO-4 ICT) creates:

1. A **Cohort** (klas): e.g. "Klas 2A ICT 2026-2027".
2. **Students** added to that cohort via email, each with their
   repo URL (`github.com/<student>/<assignment-repo>`).
3. **Courses** (vakken) inside the cohort — one per subject, each
   assigned to a specific teacher as `owner` with a default rubric.

Once saved, the teacher sees their course in `/grading/courses`
within seconds — the course list is scoped to "courses I own OR
co-teach OR sit alongside in a cohort I already teach in".

`[SCREENSHOT: /grading/courses — teacher sees newly assigned course]`

---

## Step 3 — Student opens a PR; webhook flows in

The student pushes a commit + opens a PR on their assignment repo.
GitHub fires `pull_request` to `/api/grading/webhooks/github/`. The
webhook handler:

- Deduplicates via `X-GitHub-Delivery`.
- Matches the PR's repo to the student's `CohortMembership`.
- Picks a `Course` in the cohort (first-course fallback for v1).
- Upserts a `Submission` and creates a `GradingSession` in
  `state=pending`.

The teacher's `/grading/inbox` now shows a new row:

| Student | PR Title | Due | State |
|---------|----------|-----|-------|
| Jan de Boer | `Add authentication middleware` | Thu | Pending |

`[SCREENSHOT: /grading/inbox — new pending session highlighted]`

No LLM spend has happened yet. We wait for the teacher to open the
session before burning budget.

---

## Step 4 — Teacher reviews: AI draft + student snapshot

The teacher clicks the inbox row. Two things happen:

1. **Start review** fires → `state=reviewing`, stopwatch starts
   (`docent_review_started_at`).
2. If no draft yet, **Generate draft** kicks off the rubric grader
   (synchronous call to `ai_engine`) → `state=drafting` → `drafted`.

The split-pane UI on `/grading/sessions/{id}`:

- **Left**: PR diff + AI-draft comments inline. Teacher can edit,
  delete, reorder, or add comments.
- **Right (StudentSnapshotPanel)**: bundle from
  `GET /api/grading/students/{student_id}/snapshot/` —
  skill radar, top-5 recurring patterns, what's trending up/down,
  recent PR count and average Bayesian score.

The teacher typically:
1. Skims the radar + recurring errors to frame "what does this
   student need right now".
2. Reads the AI summary, tweaks tone in their own voice.
3. Deletes 1–2 comments the AI misread; adds 1 original
   observation the AI missed.
4. Fills `final_summary` (1–3 sentences in Dutch).
5. Clicks **Send**.

Target p50 review time: **≤ 5 minutes per PR** (vs. ~20 minutes
unaided). That's the v1 validation metric.

`[SCREENSHOT: /grading/sessions/{id} — split pane, snapshot on right]`

---

## Step 5 — Send lands on GitHub; student gets notified

**Send** flips `state=sending` under a row lock, then posts each
final comment + summary to the GitHub PR outside the transaction.

- Per-comment `client_mutation_id` hashes are written to
  `PostedComment` before GitHub is called — duplicates (Send + Resume,
  double-click) skip silently.
- On full success: `state=posted`, stopwatch stops,
  `docent_review_time_seconds` is persisted.
- On partial failure: `state=partial` with `failed_at_comment_idx`
  and a Resume button. Resume replays from where it stopped.

The student receives a normal GitHub notification for each comment
and the summary. No separate in-app notification surface in v1 —
teachers live in GitHub, so do students.

`[SCREENSHOT: GitHub PR — docent comments + summary posted]`

---

## Step 6 — Weekly cohort view

Once a week the teacher opens
`/grading/cohorts/{id}/recurring-errors` (linked from the course
detail page) and reviews:

- **Top 10 unresolved patterns** across all active students in the
  cohort.
- For each: affected-student count, total frequency, severity, and
  up to 3 example finding descriptions.
- A summary line: "14/19 students have unresolved patterns; most
  affected category: code_smell".

This is the "what should I teach on Monday" signal. It replaces the
old "gut feel after grading 20 PRs" loop.

`[SCREENSHOT: /grading/cohorts/{id}/recurring-errors — class weekly view]`

---

## Edge cases a teacher will hit

| Symptom                              | What's happening                                                      | Fix                                                               |
|--------------------------------------|-----------------------------------------------------------------------|-------------------------------------------------------------------|
| Inbox empty after student pushes     | Student's repo URL isn't in the `CohortMembership`                    | Ask admin to set `student_repo_url` in the cohort member row      |
| Draft never arrives (stuck drafting) | LLM timeout or ceiling exceeded                                        | Retry; if persistent, admin checks `/ops/summary/` for cost cap   |
| Send fails with "github_auth"        | Teacher's GitHub PAT expired                                          | Re-authorize GitHub under Settings → Connected accounts           |
| Student's snapshot radar empty       | Not enough Bayesian observations yet (<5 PRs graded)                  | Expected for new students; resolves after 2–3 weeks of activity   |

Full error-code reference in [API.md](./API.md).

---

## v1.1 and beyond

Not covered in v1 but queued:
- Per-course PR routing (currently picks first course in cohort).
- Background worker for Generate Draft (currently synchronous).
- Dutch UI translation.
- `suggested_interventions` recommender on the snapshot endpoint.
- `GrowthSnapshot` weekly aggregator — powers finer trajectory charts.
