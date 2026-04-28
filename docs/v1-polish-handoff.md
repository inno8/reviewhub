# v1-polish — pre-pitch hand-off (Apr 28 2026)

## What landed on `feat/v1-polish-project-layer`

The branch contains **four commits** plus this hand-off doc:

1. `feat(grading): Project + StudentProjectRepo models + LLMCostLog.prompt_version`
   — schema + migration `0011`
2. `feat(grading): Project/Repo permissions + tighten Course-create to admin-only`
   — backend permission classes, plus the bug fix that closes the
   "teacher creates Course via API" leak
3. `feat(grading): serializers + URLs + webhook routing + project-layer tests`
   — full API surface + 17 focused tests (all pass) + webhook
   `_match_project_for_submission` fallback that prefers
   `StudentProjectRepo.repo_url` over the legacy
   `CohortMembership.student_repo_url`
4. `feat(school-admin): dedicated dashboard for IT/program managers`
   — new `SchoolAdminDashboardView.vue` (license + cohorts + members
   + at-risk students). Hides Grading Inbox from school admin nav.
5. *(this doc + Phase 3 frontend additions)* — API helpers in
   `useApi.js`, Projects section + create modal in
   `CourseDetailView.vue`

### What works end-to-end

- School admin creates Cohort + Course (existing flow)
- Teacher (course owner) creates Project under their course via the new
  Projects section in CourseDetailView
- Project has optional rubric override; falls back to course rubric
- Backend webhook prefers StudentProjectRepo over legacy
  CohortMembership.student_repo_url for routing — multi-course cohort
  support is now real (tested in `test_project_layer.py`)
- LLMCostLog records `prompt_version` when callers pass it (no breaking
  change for existing callers)

## What's deferred to a follow-up session

### Phase 3.3 — student "New Review" modal rebuild

The legacy "New Review" modal in `Sidebar.vue` (lines 725-820) plumbs the
old `projects.Project` model. To complete the v1 self-service flow,
rebuild it to use the new endpoints:

**Current behavior:**
1. Student clicks "New Review" button (sidebar)
2. Modal: pick a project (legacy projects.Project from `projectsStore`)
3. Modal: paste repo URL
4. Submit → legacy projects flow

**Target behavior:**
1. Student clicks "New Review" button
2. Modal step 1 — pick a Course (`api.grading.cohorts.get(myCohortId)` →
   `course_count` then `api.grading.courses.list({ cohort: myCohortId })`)
3. Modal step 2 — pick a Project from that course
   (`api.grading.projects.byCourse(selectedCourseId)`)
4. Modal step 3 — paste repo URL + (existing) Git identity selector
5. Submit → POST `/api/grading/student-project-repos/` with
   `{ project: <id>, repo_url: <url> }`
6. Result: webhook router will now match incoming PRs from this repo
   to the right Project + Course

**Estimated effort: 1.5–2 hours.** The API helpers
(`api.grading.studentProjectRepos.create`) are already in place; the
work is purely the modal UI rewrite.

### Phase 4 candidates (post-pitch)

These are tracked in `docs/TODO.md` but worth mentioning here for the
v1-polish series specifically:

- **License + subscription endpoint** — replace the placeholder card on
  `SchoolAdminDashboardView` ("renewal in 45 days") with real data from
  `GET /api/org/subscription/`. ~2-3h backend, 15min frontend.
- **`api.grading.cohorts.overview` helper** — currently the school
  admin dashboard's at-risk-students rollup uses a `fallbackOverview`
  via raw fetch. Add a proper helper. ~5 min.
- **Org-wide growth snapshot endpoint** — aggregate avg eindniveau
  across all cohorts over time. Powers the "growth snapshot" widget
  that's intentionally omitted from `SchoolAdminDashboardView` v1.
  ~1-2h backend.
- **Per-model + per-prompt-version cost split on ops dashboard** —
  the field is in place on `LLMCostLog` (`prompt_version`); the
  dashboard widgets are post-pitch.

## Test status when handed off

```bash
cd django_backend
# New project_layer tests: 17/17 pass
python -m pytest grading/tests/test_project_layer.py -v
# Existing webhook regression: 19/19 pass
python -m pytest grading/tests/test_webhooks.py -v
# Wider grading/ regression: started but not waited for; webhook tests
# are the most relevant smoke. Re-run before merging:
python -m pytest grading/tests/ -q
```

Frontend:
```bash
cd frontend
npm run build   # exits 0 — no new TS errors introduced
```

## What to merge

The branch `feat/v1-polish-project-layer` is ready for merge after:
1. (Optional) Run the wider grading regression once to confirm no
   collateral breakage outside the 19 webhook tests already verified.
2. Apply migrations on the dogfood DB before deploying:
   ```bash
   python manage.py migrate grading 0011
   ```
3. Open a PR, get CI green, merge.

## When the May 1 9am Dutch translation task fires

It will operate on whatever the latest code is. If `feat/v1-polish-project-layer`
has merged by then, the new strings (Dutch already on the school-admin
dashboard, Dutch already on the Project create modal) will be the only
ones the translation pass needs to touch — most of it stays in place.
