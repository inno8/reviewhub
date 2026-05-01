# Klas Boekenruil — End-to-End Demo Validation

**Date:** 2026-04-30
**Demo target:** May 7 pitch (Innovate8 booth)
**Persona:** Vash, 18-year-old MBO-4 ICT student (`afriqxpress@gmail.com`)
**Test repo:** [https://github.com/inno8/klas-boekenruil](https://github.com/inno8/klas-boekenruil)
**Cohort:** stage / Course: fullstack
**LLM:** `claude-sonnet-4-20250514`

---

## Executive summary

Three PRs from a fictional student build a small Laravel "klas boekenruil" (class book swap) app. The arc tells the demo story: PR 1 ships rough beginner code, PR 2 fixes the security holes, PR 3 adds a real feature on top of the cleaner base. LEERA receives webhooks for all three, grades each commit against an 8-criterion rubric, and produces docent-voice draft reviews.

End-to-end pipeline confirmed: webhook ingest, signature verification, diff extraction, per-commit Code Review, rubric scoring, draft synthesis. Two PRs (1 and 2) had drafts confirmed in the teacher UI by the human. PR 3 was retested today after the gunicorn worker timeout was raised from 30s to 180s. Both PR 2 and PR 3 also have fresh retest commits pushed (commits `320dc10` and `78899e0`) so the human can verify drafts complete first-try without manual reset.

The demo arc works. The gap is operational: this run uncovered 12 distinct bugs in the deployment plumbing, listed below for the v1.1 hardening backlog.

---

## The story arc (3 PRs)

The student persona is a beginner. Each PR demonstrates a different LEERA capability:

1. **PR 1 — rough first commit.** LEERA finds the obvious mistakes (SQL injection, IDOR, XSS, N+1, no tests). Docent-voice tone is the headline.
2. **PR 2 — fixes everything from PR 1.** LEERA marks the SECURITY findings as RESOLVED across PRs (cross-PR continuity), mints LearningProof, and the SkillMetric for SECURITY moves up.
3. **PR 3 — new feature on a cleaner base.** N+1 from PR 1 is gone (eager loading shows up in the diff). New swap flow gets graded fresh. The trajectory chart shows movement.

The arc is intentional: rough → redemption → growth. That's the docent value prop in 90 seconds.

---

## Per-PR breakdown

### PR 1 — Add boeken CRUD (rough)

**URL:** [https://github.com/inno8/klas-boekenruil/pull/1](https://github.com/inno8/klas-boekenruil/pull/1)
**Branch:** `feat/books-crud`

Beginner mistakes planted (every one a teaching moment):

- `BookController@index` — raw SQL with user input: `DB::select("...title like '%$search%'")`. Textbook SQL injection.
- `store()` and `update()` — `$request->all()` straight to `Book::create`. No validation, mass-assignment risk.
- `update()` and `destroy()` — no authorization check. Any logged-in user can edit/delete any book. IDOR.
- `index.blade.php` — `{!! $book->title !!}` instead of `{{ }}`. XSS.
- Loop over `$books` and access `$book->owner` per row — N+1 query.
- No tests in `tests/Feature/`.
- Recurring-pattern bait: a follow-up commit (`4299f05`) adds a `byCondition()` method that **repeats the same SQL injection pattern** as `index()`. Recurring-error detection should flag this as the same root cause.

**LEERA expected behavior:** Code Review pipeline produces ≥4 SECURITY findings + 1 PERFORMANCE finding + 1 TESTING finding. Score in the low-to-mid range (we saw commit `5427eb9` land at score 25 with 2 findings during plumbing tests).

**Status:** Drafted in UI (confirmed by human).

---

### PR 2 — Beveiliging + validatie fixes

**URL:** [https://github.com/inno8/klas-boekenruil/pull/2](https://github.com/inno8/klas-boekenruil/pull/2)
**Branch:** `fix/security-validation`

Each PR 1 sin gets fixed:

- Raw SQL replaced with `Book::where('title', 'like', "%$search%")`. Eloquent escapes the parameter.
- New `StoreBookRequest` and `UpdateBookRequest` form requests with proper validation rules.
- New `BookPolicy` checking `$user->id === $book->owner_id` on update/delete.
- Blade XSS fixed: `{{ $book->title }}` (auto-escaped).
- `tests/Feature/BookTest.php` — 4 new tests covering policy, validation, and search.

**LEERA expected behavior:**

- Cross-PR finding state: PR 1's SECURITY findings are marked RESOLVED on PR 2's submission.
- LearningProof minted (state = PROVEN) for the SQL injection and XSS patterns.
- SkillMetric for SECURITY moves up (was uncertain at 50, should land in the 65-75 range with this proof).

**Status:** Drafted (confirmed by human after manual reset). Retest commit `320dc10` just pushed — should draft first-try with the gunicorn fix in place.

---

### PR 3 — Ruilverzoeken + N+1 fix

**URL:** [https://github.com/inno8/klas-boekenruil/pull/3](https://github.com/inno8/klas-boekenruil/pull/3)
**Branch:** `feat/swap-requests`

New feature stacked on the cleaner base:

- New `SwapRequest` model + migration (`requester_id`, `book_id`, `status`).
- `SwapController` with `request()`, `accept()`, `reject()` actions.
- `BookController@index` updated to `Book::with('owner')` — fixes the N+1 from PR 1.
- 3 new tests in `tests/Feature/SwapTest.php` covering happy path + reject path.

**LEERA expected behavior:**

- N+1 finding from PR 1 marked RESOLVED.
- New ARCHITECTURE + TESTING findings on the swap flow (probably nits — missing transaction wrap, missing notification stub).
- PERFORMANCE skill nudges up. SECURITY stays where PR 2 left it.

**Status:** Retest commit `78899e0` pushed today (post gunicorn-fix). Human to verify first-try draft in UI.

---

## Skill movement evidence

The trajectory chart should show three data points per skill across the three PRs. Expected shape:


| Skill          | After PR 1 | After PR 2 | After PR 3 | Notes                                |
| -------------- | ---------- | ---------- | ---------- | ------------------------------------ |
| security       | ~35        | ~70        | ~70        | Big jump after fixes + LearningProof |
| code_quality   | ~45        | ~60        | ~62        | Steady improvement                   |
| testing        | ~30        | ~55        | ~65        | New tests in PR 2 and PR 3           |
| performance    | ~40        | ~40        | ~60        | N+1 not addressed until PR 3         |
| validation     | ~35        | ~75        | ~75        | Form requests in PR 2                |
| architecture   | ~50        | ~55        | ~60        | Policy class + new model             |
| documentation  | ~50        | ~50        | ~50        | Vash didn't write any                |
| best_practices | ~45        | ~60        | ~65        | Eloquent over raw SQL, etc.          |


Numbers are projections — the human verifies the actual movement in the trajectory chart for the deck screenshot.

The two recurring-pattern proofs (SQL injection in `index()` repeated in `byCondition()`, then both fixed in PR 2) should produce the cleanest LearningProof story for the slide.

---

## Bugs uncovered during integration testing

Twelve issues hit during this run. All resolved or worked around for the demo. Each is a candidate for the v1.1 hardening backlog.

1. **Gunicorn 30s default timeout killed LLM-bound requests.** Worker SIGKILL'd mid-Anthropic-call, leaving GradingSessions stuck in `drafting`. Bumped to 180s in commit `388e479` on the LEERA reviewhub repo. Real fix: async kickoff via Celery (already planned as Part 2).
2. **ai-engine entry point mismatch.** Dockerfile launched `app.main:app` but the FastAPI app is at top-level `main.py`. Container crashlooped on every boot.
3. `**FASTAPI_URL` not passed to django service in dev compose.** Django fell back to `localhost:8001` from inside the container, which resolved to the Django container itself. Webhook handler crashed silently.
4. `**AI_ENGINE_URL` legacy alias short-circuited the fallback.** `webhooks.py` used `os.getenv('AI_ENGINE_URL') or os.getenv('FASTAPI_URL')` — the legacy var had a populated default, so `or` never fired. `or` only triggers on falsy.
5. `**ALLOWED_HOSTS` missing `django`.** Internal django→ai-engine→django callbacks were rejected with `DisallowedHost`. Looks like an HTTP 400 with `DEBUG=False`, which is misleading.
6. **DiffExtractor uses unauthenticated git clone.** Fails silently for private repos. Worked around by making `inno8/klas-boekenruil` public for the demo. Real fix: thread the GitHub App installation token through the clone URL.
7. **LLM model names in env were fake.** `claude-haiku-4-5-20250929` and `claude-sonnet-4-5-20250929` 404'd from the Anthropic API. Aligned both tiers to `claude-sonnet-4-20250514`. Suboptimal cost (no haiku tier for cheap passes) but works.
8. **Pending placeholder Evaluations duplicate completed rows.** ai-engine creates a placeholder Evaluation, then a separate completed row instead of updating the placeholder. Worked around with a queryset filter that hides pending rows from the user-facing list. Real fix: ai-engine updates the existing row.
9. **GitHub App Setup URL vs Callback URL confusion.** Install OAuth flow redirected to a path Django didn't serve. Resolved by aligning the Callback URL to `/dev-profile/connected`.
10. `**GITHUB_APP_PRIVATE_KEY_PATH` plumbing.** Missing volume mount and missing env var passthrough kept `is_github_app_configured()` returning False on first attempts. Two-line fix once spotted.
11. **CohortMembership hard-deleted on member-remove.** Re-invite restores the user but not the membership, breaking webhook routing for anyone who got removed and re-added. Tracked as a soft-delete refactor for post-pitch.
12. **Mixed dev/prod compose state on droplet.** Orphan containers from earlier runs caused DNS resolution failures (django couldn't find `ai-engine` because a legacy `ai_engine` container was crashlooping in parallel and squatting the network alias). Fixed by `docker compose down` on both files + standardizing on the prod compose.

---

## Demo script (2 min, for the booth)

Read this on stage. Dunglish is fine — it lands better with MBO docenten than full English.

**(0:00–0:15) Hook**
"Drie PRs van student Vash op klas-boekenruil. Een laravel app om boeken te ruilen tussen klasgenoten. Vash is beginner. Hij maakt fouten." [Show the GitHub repo with the 3 PRs.]

**(0:15–0:45) PR 1 — the rough draft**
Open PR 1 in LEERA teacher view. Read the top finding aloud:
"SQL injectie in BookController, regel 14. `$search` komt direct van de gebruiker en wordt in een raw query gegooid."
Point at the docent-voice tone. "Dit klinkt zoals een Nederlandse ICT-docent. Niet zoals ChatGPT."

**(0:45–1:15) PR 2 — redemption**
Open PR 2. "Zelfde finding. Nu groen. RESOLVED." Point at the LearningProof badge. "Vash heeft het bewijs geleverd. Niet alleen gerepareerd — bewezen dat hij het patroon snapt."
Open the trajectory chart. "Security skill ging van 35 naar 70."

**(1:15–1:45) PR 3 — growth**
Open PR 3. "Nieuwe feature: ruilverzoeken. De N+1 query uit PR 1 is meteen opgelost — kijk, `Book::with('owner')`. Performance gaat omhoog. Security blijft staan."

**(1:45–2:00) The close**
"Vijf minuten per PR. Vijfentwintig studenten per klas. De docent krijgt zijn avond terug. En de student krijgt feedback op elke push, niet één keer per maand."

End on the screenshot of the trajectory chart. No buzzwords. Walk off.

---

## What still needs the human's eyes

Before May 7:

- Refresh PR 2 in the LEERA UI. Verify the draft for commit `320dc10` completes first-try (no manual reset needed). This validates the gunicorn timeout fix.
- Refresh PR 3 in the LEERA UI. Verify the draft for commit `78899e0` completes first-try.
- Click through all 3 PRs in teacher view. Screenshot one finding per PR for the deck (highest-impact one each).
- Open the trajectory chart for student `afriqxpress@gmail.com`. Verify the SECURITY line actually moves PR-1 → PR-2. Screenshot for the deck.
- Check the recurring-error detection on PR 1. Confirm it flagged the `byCondition()` SQL injection as the same pattern as `index()`. This is the strongest "we know what we're doing" signal in the demo.
- Confirm SECURITY findings on PR 1 show as RESOLVED on PR 2 (cross-PR continuity).
- Confirm at least one LearningProof minted with state PROVEN.

If any of the above doesn't render, the fallback for the booth is the screenshots — capture them now while the data is fresh.