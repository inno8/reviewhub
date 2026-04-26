"""
Grading webhook handler for GitHub PR events.

Endpoint: POST /api/grading/webhooks/github/
Events handled: pull_request (opened, reopened, synchronize, closed)

Flow:
  1. Verify signature (if GITHUB_WEBHOOK_SECRET is set).
  2. Dedupe via WebhookDelivery (X-GitHub-Delivery header). Re-delivered
     webhooks return 200 OK immediately — this is the idempotency
     guarantee from the eng review concurrency bundle.
  3. Match the PR's repo URL to a ClassroomMembership (student_repo_url).
     If no match: 200 OK + "no match" (webhook was successful from
     GitHub's POV; we just don't care about this repo).
  4. Create or update a Submission for the PR.
  5. Create a GradingSession in `pending` state if one doesn't exist yet.
     The teacher then triggers generate_draft from the inbox when they're
     ready to grade.
  6. On pull_request.closed: mark Submission.status = GRADED (if merged)
     or OPEN (if just closed) — doesn't delete existing GradingSession.

Push events are forwarded to the ai_engine FastAPI service for the
per-commit Code Review pipeline (see forward_push_to_ai_engine). Nakijken
itself only handles PR-level events (pull_request, pull_request_review,
pull_request_review_thread); the per-commit AI auto-review is a separate
loop in ai_engine. We act as the gateway so schools configure ONE webhook
URL per repo, and Leera owns the fan-out.

We DON'T pre-generate drafts on webhook — we wait for the teacher to
click Generate Draft in the inbox so we don't burn LLM budget on every
synchronize.

Public: the endpoint is at /api/grading/webhooks/github/ and does NOT
require authentication (GitHub is the caller). Signature verification
is the security boundary.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.db import models, transaction
from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from django.utils import timezone as _tz

from grading.models import (
    CohortMembership,
    CohortTeacher,
    Course,
    GradingSession,
    PostedComment,
    Submission,
    SubmissionContributor,
    WebhookDelivery,
)

log = logging.getLogger(__name__)


# ── signature verification ────────────────────────────────────────────
def _verify_github_signature(body: bytes, header: str, secret: str) -> bool:
    """Constant-time HMAC verify for X-Hub-Signature-256."""
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", header)


def _parse_repo_url(repo_url: str) -> tuple[str, str] | None:
    """Extract (owner, repo) from a github.com URL. None on malformed input."""
    try:
        parsed = urlparse((repo_url or "").strip())
        if parsed.hostname and "github.com" not in parsed.hostname:
            return None
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(parts) < 2:
            return None
        owner, repo = parts[0], parts[1]
        if repo.endswith(".git"):
            repo = repo[:-4]
        return owner, repo
    except Exception:
        return None


def _resolve_project_id_for_push(repo_html_url: str) -> int | None:
    """
    Find the projects.Project that owns this repo URL so we can target
    the right ai_engine endpoint. Tolerant of trailing slashes and the
    .git suffix that GitHub clones use but webhook payloads don't.

    Returns None if no Project matches — push silently skips fan-out.
    A teacher's first push to a fresh repo before they register the
    Project should not 500; it should just no-op the AI auto-review
    until the Project exists.
    """
    if not repo_html_url:
        return None
    from projects.models import Project
    candidates = {
        repo_html_url,
        repo_html_url.rstrip("/"),
        repo_html_url.rstrip("/") + ".git",
    }
    if repo_html_url.endswith(".git"):
        candidates.add(repo_html_url[:-4])
    project = Project.objects.filter(repo_url__in=list(candidates)).first()
    return project.id if project else None


def forward_push_to_ai_engine(
    *,
    body: bytes,
    payload: dict,
    signature_header: str,
    delivery_id: str,
) -> dict:
    """
    Fan-out for push events. Nakijken Copilot's webhook deliberately
    handles only PR-level events (pull_request, pull_request_review,
    ...). Per-commit AI auto-review lives in the ai_engine FastAPI
    service at /api/v1/webhook/github/{project_id}.

    This helper bridges the two: when a push lands at the Nakijken
    endpoint, we forward the SAME raw body and signature to ai_engine.
    Both services share GITHUB_WEBHOOK_SECRET, so ai_engine's signature
    verification accepts the forwarded request as if GitHub had POSTed
    directly.

    Fire-and-forget: a daemon thread does the POST so Django can return
    200 to GitHub immediately. Mirrors draft_kickoff's pattern. Errors
    are logged, never raised — webhook delivery remains successful from
    GitHub's perspective even if ai_engine is down.

    Returns a dict describing the dispatch decision (for tests / logging).
    """
    repo_html_url = ((payload.get("repository") or {}).get("html_url") or "").strip()
    project_id = _resolve_project_id_for_push(repo_html_url)
    if not project_id:
        log.info(
            "forward_push_to_ai_engine: no Project matched repo=%r — skipping",
            repo_html_url,
        )
        return {"forwarded": False, "reason": "no_project_match", "repo_url": repo_html_url}

    ai_engine_url = getattr(settings, "AI_ENGINE_URL", "http://localhost:8001")
    forward_url = f"{ai_engine_url.rstrip('/')}/api/v1/webhook/github/{project_id}"

    # Headers: forward the signature verbatim so ai_engine's HMAC check
    # passes (assumes both services share GITHUB_WEBHOOK_SECRET). We
    # explicitly set X-GitHub-Event=push since that's what we're
    # forwarding; the rest of GitHub's headers are not required by
    # ai_engine's handler.
    headers = {
        "Content-Type": "application/json",
        "X-GitHub-Event": "push",
        "X-GitHub-Delivery": delivery_id or "",
        "X-Hub-Signature-256": signature_header or "",
        "User-Agent": "ReviewHub-Nakijken-Forwarder/1.0",
    }

    def _do_forward():
        try:
            import requests
            resp = requests.post(forward_url, data=body, headers=headers, timeout=10)
            log.info(
                "forward_push_to_ai_engine: project=%s status=%s",
                project_id, resp.status_code,
            )
        except Exception as exc:  # noqa: BLE001 — fan-out must never raise
            log.warning(
                "forward_push_to_ai_engine: project=%s POST failed: %s",
                project_id, exc,
            )

    threading.Thread(
        target=_do_forward,
        daemon=True,
        name=f"ai-engine-forward-{project_id}",
    ).start()
    return {
        "forwarded": True,
        "project_id": project_id,
        "ai_engine_url": forward_url,
    }


def _memberships_for_pr(
    repo_full_name: str,
    author_login: str,
) -> list[CohortMembership]:
    """
    Match an incoming PR to ALL relevant CohortMemberships (Workstream G).

    Shared-repo support: an MBO-4 ICT group often shares ONE repo. Instead of
    first-match-wins, we return the full list of matched cohort members so
    the webhook can attach all of them as Submission.contributors.

    Match rules:
      1. Explicit repo_url match: every non-removed CohortMembership whose
         `student_repo_url` contains the PR's repo_full_name. For solo repos,
         this is 1 member; for group repos, it's 2+.
      2. If rule 1 returns zero, fall back to the author→GitProviderConnection
         rule (single student who owns the repo ad-hoc). Only when the repo
         is owned by the PR author.
      3. If still empty, return [] — caller emits matched=false.
    """
    # Rule 1: explicit repo_url match — ALL matching memberships.
    qs = (
        CohortMembership.objects
        .filter(student_repo_url__icontains=repo_full_name)
        .filter(removed_at__isnull=True)
        .select_related("student", "cohort")
        .order_by("student__email")  # deterministic tiebreak
    )
    members = list(qs)
    if members:
        return members

    # Rule 2: repo-owner-is-author fallback — single-student path.
    repo_owner = (repo_full_name.split("/", 1)[0] or "").strip()
    if not repo_owner or repo_owner.lower() != (author_login or "").lower():
        return []

    from users.models import GitProviderConnection
    conn = (
        GitProviderConnection.objects
        .filter(provider="github", username__iexact=author_login)
        .select_related("user")
        .first()
    )
    if not conn:
        return []
    m = (
        CohortMembership.objects
        .filter(student=conn.user, removed_at__isnull=True)
        .select_related("student", "cohort")
        .first()
    )
    return [m] if m else []


def _pick_primary_author(
    memberships: list[CohortMembership],
    author_login: str,
) -> CohortMembership:
    """
    Pick the primary author among matched cohort members.

    Rule: if the PR author's GitHub login maps (via GitProviderConnection)
    to one of the members, that member is primary. Otherwise the first
    member sorted alphabetically by email (deterministic fallback).
    """
    if not memberships:
        raise ValueError("_pick_primary_author called with empty memberships")

    from users.models import GitProviderConnection
    if author_login:
        conn = (
            GitProviderConnection.objects
            .filter(provider="github", username__iexact=author_login)
            .values_list("user_id", flat=True)
            .first()
        )
        if conn:
            for m in memberships:
                if m.student_id == conn:
                    return m

    # Deterministic fallback: alphabetical by email.
    return sorted(memberships, key=lambda m: (m.student.email or "").lower())[0]


def _course_for_membership(membership: CohortMembership) -> Course | None:
    """
    Pick a Course from the cohort for this webhook's Submission.

    In v1 a cohort typically has multiple courses; we don't (yet) know
    which course a given PR corresponds to without extra signals (PR
    title conventions, branch naming, per-course repo mapping). For
    Workstream A we pick the first course in the cohort so PR webhooks
    keep flowing end-to-end. Workstream B+ will add per-course routing.
    """
    return (
        Course.objects
        .filter(cohort=membership.cohort)
        .select_related("rubric", "org")
        .order_by("created_at")
        .first()
    )


def _ensure_evaluation_link(submission: Submission, session: GradingSession, pr_payload: dict) -> None:
    """
    Ensure a lightweight Evaluation + SessionEvaluation link exists for this
    GradingSession so downstream skill_binding / trajectory code can find it.

    Idempotency:
      * Evaluation uniquely keyed by (virtual project, commit_sha) — webhook
        redelivery for the same head commit reuses the existing row. (Webhook
        dedupe via WebhookDelivery.delivery_id is the first line of defense;
        this is the second.)
      * SessionEvaluation unique on (grading_session, evaluation) — create
        is wrapped in get_or_create so a rerun with the same commit is a
        no-op.

    Failure isolation: callers MUST wrap this in try/except. The webhook's
    200-OK contract to GitHub cannot be broken by an Evaluation write
    failure — see callsite in _upsert_submission_and_session.

    This helper does NOT fetch commit diffs / call the LLM. The created
    Evaluation is a placeholder: overall_score stays null until the
    teacher triggers generate_draft, at which point skill_binding will
    attach SkillObservations to it.
    """
    from evaluations.models import Evaluation
    from grading.models import SessionEvaluation
    from grading.services.virtual_project import get_or_create_virtual_project

    head_sha = ((pr_payload.get("head") or {}).get("sha") or "")[:40]
    if not head_sha:
        # Synthesize a stable placeholder so Evaluation.commit_sha isn't blank
        # and redelivery still hits the same (project, commit_sha) row.
        head_sha = f"pr-{submission.pr_number}-{submission.head_branch or 'head'}"[:40]

    project = get_or_create_virtual_project(submission)
    head_ref = (pr_payload.get("head") or {}).get("ref", "") or submission.head_branch or "unknown"
    pr_title = (pr_payload.get("title") or submission.pr_title or "")[:500]

    evaluation, _ = Evaluation.objects.get_or_create(
        project=project,
        commit_sha=head_sha,
        defaults={
            "author": submission.student,
            "commit_message": pr_title,
            "branch": head_ref[:100],
            "author_name": (submission.student.username or submission.student.email or "")[:100],
            "author_email": (submission.student.email or "")[:255],
            "status": Evaluation.Status.PENDING,
            "llm_model": "",
        },
    )

    SessionEvaluation.objects.get_or_create(
        grading_session=session,
        evaluation=evaluation,
        defaults={"included_in_draft": False},
    )


def _upsert_submission_and_session(
    *,
    memberships: list[CohortMembership],
    primary: CohortMembership,
    course: Course,
    pr_payload: dict,
    repo_full_name: str,
) -> tuple[Submission, GradingSession, bool]:
    """
    Create-or-update the Submission for this PR and ensure a GradingSession
    exists. Attaches ALL matched cohort members as SubmissionContributor
    rows (shared-repo / Workstream G).

    Returns (submission, session, created_new_session).

    v1 note: contribution_fraction is an equal split across matched members.
    Commit-level attribution (mapping commit authors → Users via
    GitProviderConnection → lines_changed) is v1.1 work — requires a new
    github-api fetcher that isn't in scope for this workstream.
    """
    pr_number = int(pr_payload.get("number", 0))
    pr_state = pr_payload.get("state", "open")
    pr_merged = bool(pr_payload.get("merged", False))

    # Status mapping from GitHub PR state
    status = Submission.Status.OPEN
    if pr_state == "closed":
        status = Submission.Status.GRADED if pr_merged else Submission.Status.OPEN

    with transaction.atomic():
        submission, _ = Submission.objects.select_for_update().update_or_create(
            course=course,
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            defaults={
                "org": course.org,
                "student": primary.student,
                "pr_url": pr_payload.get("html_url", ""),
                "pr_title": (pr_payload.get("title") or "")[:500],
                "base_branch": pr_payload.get("base", {}).get("ref", "main"),
                "head_branch": pr_payload.get("head", {}).get("ref", ""),
                "status": status,
            },
        )

        # Ensure contributor rows exist for every matched member.
        _sync_contributors(submission, memberships, primary)

        # Ensure GradingSession exists (one per Submission, OneToOne)
        course_rubric = course.rubric
        if course_rubric is None:
            log.warning(
                "webhook: course %s has no default rubric; skipping session creation",
                course.id,
            )
            return submission, None, False  # type: ignore[return-value]

        # Iteration logic simplified post-bugfix: `synchronize` is an in-place
        # head_sha update only. Iterations are spawned by explicit intent
        # signals (review_requested, student-submitted review, manual action).
        # See the layer-2 event handlers below.
        latest = (
            GradingSession.objects
            .select_for_update()
            .filter(submission=submission, superseded_by__isnull=True)
            .order_by("-iteration_number", "-created_at")
            .first()
        )

        if latest is None:
            session = GradingSession.objects.create(
                org=course.org,
                submission=submission,
                rubric=course_rubric,
                state=GradingSession.State.PENDING,
                iteration_number=1,
            )
            created = True
        else:
            session = latest
            created = False

        # Ensure an Evaluation + SessionEvaluation link exists so that
        # skill_binding (runs after the teacher triggers generate_draft)
        # has a representative Evaluation to attach SkillObservations to.
        # Failure here must NOT fail the webhook: log and continue.
        try:
            _ensure_evaluation_link(submission, session, pr_payload)
        except Exception:
            log.exception(
                "webhook: evaluation link creation failed for submission=%s session=%s",
                submission.id, session.id,
            )

    return submission, session, created


def _sync_contributors(
    submission: Submission,
    memberships: list[CohortMembership],
    primary: CohortMembership,
) -> None:
    """
    Create SubmissionContributor rows for every matched member.

    v1 equal-split: `contribution_fraction = 1/N` for N contributors.
    Upgrade path (v1.1): fetch PR commits, group by commit author login,
    map login → User via GitProviderConnection, compute lines_changed
    per author, set fractions from that.

    Idempotent — re-running on the same PR leaves existing rows alone
    (update_or_create keyed on (submission, user)). Fractions get
    rewritten so a new contributor joining triggers a rebalance.
    """
    n = max(1, len(memberships))
    equal_fraction = round(1.0 / n, 6)
    for m in memberships:
        SubmissionContributor.objects.update_or_create(
            submission=submission,
            user=m.student,
            defaults={
                "is_primary_author": (m.student_id == primary.student_id),
                "contribution_fraction": equal_fraction,
                # lines_changed / commits_count stay 0 at webhook time —
                # filled in by a future commit-attribution fetcher.
            },
        )


TERMINAL_SESSION_STATES = {
    GradingSession.State.POSTED,
    GradingSession.State.PARTIAL,
    GradingSession.State.FAILED,
    GradingSession.State.DISCARDED,
}


def _cascade_discard_inflight_sessions(submission: Submission, *, merged: bool) -> int:
    """
    Orphan-iteration guard: when a PR is closed (merged or not), discard any
    GradingSessions on this submission that are still mid-flight (PENDING,
    DRAFTING, DRAFTED, REVIEWING, SENDING). They can never be sent now because
    GitHub will reject comments with PRClosedError, so leaving them in limbo
    just confuses the teacher.

    For each discarded session we set partial_post_error to a structured marker
    the frontend uses to render the "iteratie afgebroken / PR is gemerged"
    banner — distinct from a real Send-time error so we don't overwrite genuine
    failure data on already-terminal sessions.

    Returns the number of sessions transitioned. Idempotent: re-running on the
    same submission is a no-op because all matching sessions are now terminal.
    """
    reason = "pr_merged" if merged else "pr_closed_by_student"
    count = 0
    # Cap the loop so a misbehaving submission can't blow up a webhook
    # request budget. 50 in-flight sessions on one PR is already absurd —
    # if we hit it, log loudly and let a follow-up webhook clean up the
    # tail.
    INFLIGHT_CAP = 50
    inflight_ids = list(
        GradingSession.objects
        .filter(submission=submission)
        .exclude(state__in=TERMINAL_SESSION_STATES)
        .values_list("id", flat=True)[:INFLIGHT_CAP]
    )
    if len(inflight_ids) >= INFLIGHT_CAP:
        log.warning(
            "cascade_discard: hit INFLIGHT_CAP=%d on submission=%s — tail will be "
            "discarded by the next webhook delivery",
            INFLIGHT_CAP, submission.id,
        )
    for sid in inflight_ids:
        with transaction.atomic():
            s = (
                GradingSession.objects
                .select_for_update()
                .filter(pk=sid)
                .first()
            )
            if s is None:
                continue
            if s.state in TERMINAL_SESSION_STATES:
                # Raced with another writer (e.g. concurrent Send completed).
                continue
            # Route through the state-machine guard so the ALLOWED_TRANSITIONS
            # table stays the single source of truth. If the table ever
            # tightens to forbid `<state>→DISCARDED`, this will start
            # logging instead of silently bypassing.
            if not s.can_transition_to(GradingSession.State.DISCARDED):
                log.warning(
                    "cascade_discard: state-machine refused %s→discarded on session=%s; "
                    "skipping",
                    s.state, sid,
                )
                continue
            previous_state = s.state
            s.state = GradingSession.State.DISCARDED
            s.partial_post_error = {
                "reason": reason,
                "abandoned_at": _tz.now().isoformat(),
                "previous_state": previous_state,
            }
            s.save(update_fields=["state", "partial_post_error", "updated_at"])
            count += 1
    return count


def _pr_is_terminal(submission: Submission, pr_payload: dict) -> bool:
    """
    Return True if the PR behind this submission is in a terminal state.
    Hard guard: never create a new iteration on a merged/closed PR.

    Terminal = Submission.status == GRADED (merged) OR the incoming
    pull_request.state == "closed" (merged or simply closed).
    """
    if submission.status == Submission.Status.GRADED:
        return True
    if (pr_payload or {}).get("state") == "closed":
        return True
    return False


def create_next_iteration(session: GradingSession) -> GradingSession | None:
    """
    Spawn a new iteration for `session`'s submission and supersede the old
    one. Safe to call from any trigger path (webhook event or manual action).

    Preconditions (caller must enforce 400s on the manual path):
      - session.submission is NOT a merged PR (caller checks via _pr_is_terminal)
      - session is in a terminal state (caller checks)

    Internally uses select_for_update on the submission so concurrent
    triggers (double webhook + teacher click) collapse to one winner.
    Returns the new session, or the already-existing next iteration if a
    racing caller created one first.
    """
    submission = session.submission
    course_rubric = session.rubric
    with transaction.atomic():
        latest = (
            GradingSession.objects
            .select_for_update()
            .filter(submission=submission, superseded_by__isnull=True)
            .order_by("-iteration_number", "-created_at")
            .first()
        )
        if latest is None:
            # Shouldn't happen — caller saw `session` — but be defensive.
            return None
        if latest.state not in TERMINAL_SESSION_STATES:
            # Someone already spawned an iteration and it's mid-flight; reuse.
            return latest

        new_session = GradingSession.objects.create(
            org=session.org,
            submission=submission,
            rubric=course_rubric,
            state=GradingSession.State.PENDING,
            iteration_number=latest.iteration_number + 1,
            ai_draft_scores={},
            ai_draft_comments=[],
            final_scores={},
            final_comments=[],
            final_summary="",
        )
        latest.superseded_by = new_session
        latest.save(update_fields=["superseded_by", "updated_at"])

    # Fire-and-forget the draft kickoff so the new iteration doesn't sit in
    # PENDING until a teacher navigates to the session in the UI. This matches
    # what GradingSessionDetailView.vue onMounted does for PENDING sessions,
    # but backs it up server-side so webhook-driven iterations (student
    # re-requests review while teacher isn't looking at the app) also draft
    # automatically. Synchronous path is fine here — the actual LLM call is
    # already non-blocking inside generate_draft via the ai_engine proxy.
    try:
        from grading.services import draft_kickoff  # lightweight async launcher
        draft_kickoff.fire(new_session.id)
    except Exception as e:  # pragma: no cover — kickoff is best-effort
        import logging
        logging.getLogger(__name__).warning(
            "create_next_iteration: draft kickoff failed for session=%s: %s",
            new_session.id, e,
        )
    return new_session


def _resolve_teacher_from_review_request(payload: dict, cohort) -> "object | None":
    """
    On `pull_request review_requested`, GitHub includes a `requested_reviewer`
    user. Try to match their login to a User who teaches on this cohort
    (Course owner / secondary / CohortTeacher assignment). Returns the
    User or None if the request was directed elsewhere (another student,
    unrelated reviewer).
    """
    reviewer = (payload.get("requested_reviewer") or {})
    login = (reviewer.get("login") or "").strip()
    if not login:
        return None
    from users.models import GitProviderConnection
    user_id = (
        GitProviderConnection.objects
        .filter(provider="github", username__iexact=login)
        .values_list("user_id", flat=True)
        .first()
    )
    if not user_id:
        return None

    # Is this user a teacher on this cohort?
    teaches_via_course = Course.objects.filter(
        cohort=cohort,
    ).filter(
        models.Q(owner_id=user_id) | models.Q(secondary_docent_id=user_id),
    ).exists()
    teaches_via_assignment = CohortTeacher.objects.filter(
        cohort=cohort, teacher_id=user_id,
    ).exists()
    if teaches_via_course or teaches_via_assignment:
        from users.models import User
        return User.objects.filter(pk=user_id).first()
    return None


def _handle_review_requested(payload: dict, primary: CohortMembership, course: Course,
                             memberships: list[CohortMembership], repo_full_name: str):
    """
    Layer 2a: `pull_request` action=`review_requested`.
    Create a new iteration iff the requested reviewer is a teacher on this cohort.
    Returns (submission, session, created_new_iteration, reason_if_skipped).
    """
    pr = payload.get("pull_request") or {}
    # Upsert the submission first — it may not exist yet for a PR that went
    # straight to review-request without hitting opened in our system.
    pr["_action"] = "review_requested"
    submission, session, _ = _upsert_submission_and_session(
        memberships=memberships, primary=primary, course=course,
        pr_payload=pr, repo_full_name=repo_full_name,
    )
    if session is None:
        return submission, None, False, "no_session"

    if _pr_is_terminal(submission, pr):
        log.debug("webhook: review_requested but PR is terminal — skipping iteration")
        return submission, session, False, "pr_terminal"

    teacher = _resolve_teacher_from_review_request(payload, primary.cohort)
    if teacher is None:
        return submission, session, False, "reviewer_not_teacher"

    if session.state not in TERMINAL_SESSION_STATES:
        # Active session — review_requested is redundant; keep the current one.
        return submission, session, False, "session_not_terminal"

    new_session = create_next_iteration(session)
    return submission, new_session, (new_session is not None and new_session.id != session.id), None


def _handle_student_submitted_review(payload: dict, primary: CohortMembership, course: Course,
                                     memberships: list[CohortMembership], repo_full_name: str):
    """
    Layer 2b: `pull_request_review` action=`submitted`.
    If the submitter == the PR author (student) → new iteration.
    If it's a teacher — skip (normal teacher activity).
    """
    pr = payload.get("pull_request") or {}
    review = payload.get("review") or {}
    reviewer_login = ((review.get("user") or {}).get("login") or "").strip().lower()
    pr_author_login = ((pr.get("user") or {}).get("login") or "").strip().lower()

    if not reviewer_login:
        return None, None, False, "no_reviewer"

    if reviewer_login != pr_author_login:
        return None, None, False, "reviewer_is_not_student"

    # Upsert to ensure we have a submission + session row to iterate on.
    pr["_action"] = "pr_review_submitted"
    submission, session, _ = _upsert_submission_and_session(
        memberships=memberships, primary=primary, course=course,
        pr_payload=pr, repo_full_name=repo_full_name,
    )
    if session is None:
        return submission, None, False, "no_session"

    if _pr_is_terminal(submission, pr):
        return submission, session, False, "pr_terminal"

    if session.state not in TERMINAL_SESSION_STATES:
        return submission, session, False, "session_not_terminal"

    # Accept any review state (approved / changes_requested / commented-with-body)
    # as an intent-to-re-review signal.
    body = (review.get("body") or "").strip()
    state = (review.get("state") or "").strip().lower()
    if not body and state not in ("approved", "changes_requested"):
        return submission, session, False, "review_without_signal"

    new_session = create_next_iteration(session)
    return submission, new_session, (new_session is not None and new_session.id != session.id), None


def _handle_review_thread_resolution(payload: dict) -> dict:
    """
    Layer 2c: `pull_request_review_thread` action=`resolved|unresolved`.
    Update PostedComment.resolved_at / resolved_by_student. No iteration.
    Returns a small dict summary for the response body.
    """
    action = payload.get("action")
    thread = payload.get("thread") or {}
    pr = payload.get("pull_request") or {}
    pr_author_login = ((pr.get("user") or {}).get("login") or "").strip().lower()
    resolver_login = ((payload.get("sender") or {}).get("login") or "").strip().lower()

    comment_ids = []
    for c in (thread.get("comments") or []):
        cid = c.get("id")
        if cid:
            comment_ids.append(cid)

    if not comment_ids:
        return {"updated": 0, "action": action}

    qs = PostedComment.objects.filter(github_comment_id__in=comment_ids)
    updated = 0
    if action == "resolved":
        resolved_by_student = bool(
            pr_author_login and resolver_login and pr_author_login == resolver_login
        )
        updated = qs.update(
            resolved_at=_tz.now(),
            resolved_by_student=resolved_by_student,
        )
    elif action == "unresolved":
        updated = qs.update(resolved_at=None, resolved_by_student=False)

    return {"updated": updated, "action": action}


# ── the view ─────────────────────────────────────────────────────────
@csrf_exempt
@require_POST
def github_webhook(request):
    """
    Entry point for GitHub PR webhooks. Mounted at
    /api/grading/webhooks/github/.

    NOTE: This view is CSRF-exempt and auth-less. Security boundary is
    the X-Hub-Signature-256 HMAC verification (when GITHUB_WEBHOOK_SECRET
    is configured). Without a secret, ANY caller can trigger it — OK for
    local dev, not for production.
    """
    # 1. Signature verification (production safeguard).
    body = request.body
    secret = getattr(settings, "GITHUB_WEBHOOK_SECRET", "") or ""
    if secret:
        header = request.META.get("HTTP_X_HUB_SIGNATURE_256", "")
        if not _verify_github_signature(body, header, secret):
            return HttpResponseForbidden("invalid signature")

    delivery_id = request.META.get("HTTP_X_GITHUB_DELIVERY", "")
    event_type = request.META.get("HTTP_X_GITHUB_EVENT", "")

    # 2. Early dedupe check — if this delivery_id was already successfully
    #    stored (parsed + accepted on a previous request), return 200 so
    #    GitHub stops retrying. We do NOT create the row yet: if parsing
    #    fails below, we'd burn the guid and block GitHub's redelivery of
    #    a fixed payload. Persist happens AFTER successful parsing.
    if delivery_id and WebhookDelivery.objects.filter(
        provider="github", delivery_id=delivery_id,
    ).exists():
        return JsonResponse({"ok": True, "deduped": True}, status=200)

    # 3. Parse payload. GitHub supports both application/json and
    #    application/x-www-form-urlencoded (payload=<json>) content types.
    content_type = (request.content_type or "").split(";", 1)[0].strip().lower()
    try:
        if content_type == "application/x-www-form-urlencoded":
            form = parse_qs(body.decode("utf-8"))
            raw = (form.get("payload") or [""])[0]
            if not raw:
                return HttpResponseBadRequest("missing payload form field")
            payload = json.loads(raw)
        elif content_type == "application/json" or not content_type:
            payload = json.loads(body.decode("utf-8"))
        else:
            return HttpResponseBadRequest(
                f"unsupported content type: {content_type}"
            )
    except (json.JSONDecodeError, UnicodeDecodeError):
        return HttpResponseBadRequest("invalid payload")

    # 4. Parsing succeeded — persist the dedupe row now. If a concurrent
    #    redelivery raced us, the second one returns 200+deduped.
    if delivery_id:
        _, created = WebhookDelivery.objects.get_or_create(
            provider="github",
            delivery_id=delivery_id,
            defaults={"event_type": event_type},
        )
        if not created:
            return JsonResponse({"ok": True, "deduped": True}, status=200)

    # 4. Push events: forward to ai_engine for the per-commit Code Review
    #    pipeline. Nakijken itself doesn't touch push (rubric grading is
    #    PR-level), but we own the GitHub webhook integration, so we act
    #    as the gateway and fan out. See forward_push_to_ai_engine.
    if event_type == "push":
        sig_header = request.META.get("HTTP_X_HUB_SIGNATURE_256", "")
        result = forward_push_to_ai_engine(
            body=body,
            payload=payload,
            signature_header=sig_header,
            delivery_id=delivery_id,
        )
        return JsonResponse({"ok": True, "fanout": result}, status=200)

    # 5. Short-circuit anything that isn't an event we care about.
    ACCEPTED_EVENT_TYPES = (
        "pull_request",
        "pull_request_review",
        "pull_request_review_thread",
    )
    if event_type not in ACCEPTED_EVENT_TYPES:
        return JsonResponse(
            {"ok": True, "message": f"ignored event: {event_type}"}, status=200
        )

    action = payload.get("action", "")
    if event_type == "pull_request":
        if action not in (
            "opened", "reopened", "synchronize", "closed",
            "review_requested", "ready_for_review",
        ):
            return JsonResponse(
                {"ok": True, "message": f"ignored action: {action}"}, status=200
            )
    elif event_type == "pull_request_review":
        if action != "submitted":
            return JsonResponse(
                {"ok": True, "message": f"ignored action: {action}"}, status=200
            )
    elif event_type == "pull_request_review_thread":
        if action not in ("resolved", "unresolved"):
            return JsonResponse(
                {"ok": True, "message": f"ignored action: {action}"}, status=200
            )

    # Early branch: review_thread events need different matching — they key
    # off github_comment_id, not a repo URL.
    if event_type == "pull_request_review_thread":
        summary = _handle_review_thread_resolution(payload)
        return JsonResponse({"ok": True, "matched": True, **summary}, status=200)

    pr = payload.get("pull_request") or {}
    if not pr:
        return HttpResponseBadRequest("no pull_request in payload")

    # 5. Match repo + PR author to a classroom membership.
    repo_data = payload.get("repository") or {}
    repo_url = repo_data.get("html_url", "")
    repo_full_name = repo_data.get("full_name", "")
    author_login = (pr.get("user") or {}).get("login", "")

    if not repo_full_name:
        return HttpResponseBadRequest("missing repository.full_name")

    memberships = _memberships_for_pr(repo_full_name, author_login)
    if not memberships:
        # Not an error — just a repo we don't track yet.
        log.info("webhook: no cohort match for %s (author=%s)", repo_full_name, author_login)
        return JsonResponse(
            {
                "ok": True,
                "matched": False,
                "message": (
                    "No cohort membership matched this repo. "
                    "Add the student's repo URL to a cohort in Django admin."
                ),
            },
            status=200,
        )

    primary = _pick_primary_author(memberships, author_login)

    # Pick a Course within the primary's cohort for this Submission.
    # (All members in a shared repo usually belong to the same cohort.)
    course = _course_for_membership(primary)
    if course is None:
        log.info(
            "webhook: cohort %s has no courses; skipping (add a course first)",
            primary.cohort_id,
        )
        return JsonResponse(
            {
                "ok": True,
                "matched": True,
                "submission_id": None,
                "session_id": None,
                "session_created": False,
                "cohort": primary.cohort.name,
                "student": primary.student.email,
                "message": "Cohort has no courses; add a course before submissions can land.",
            },
            status=200,
        )

    # 6. Dispatch by (event_type, action).
    # pull_request review_requested → teacher-triggered iteration
    # pull_request_review submitted (by student) → intent-to-re-review → iteration
    # pull_request opened / reopened / synchronize / closed / ready_for_review
    #   → standard upsert path (no iteration trigger for synchronize anymore)
    pr["_action"] = action
    iteration_reason: str | None = None
    try:
        if event_type == "pull_request" and action == "review_requested":
            submission, session, created, iteration_reason = _handle_review_requested(
                payload, primary, course, memberships, repo_full_name,
            )
        elif event_type == "pull_request_review" and action == "submitted":
            submission, session, created, iteration_reason = _handle_student_submitted_review(
                payload, primary, course, memberships, repo_full_name,
            )
        else:
            submission, session, created = _upsert_submission_and_session(
                memberships=memberships,
                primary=primary,
                course=course,
                pr_payload=pr,
                repo_full_name=repo_full_name,
            )
            # On pull_request closed: cascade-discard any GradingSession that
            # was mid-flight on this submission. The teacher's draft can no
            # longer be sent (GitHub will reject with PRClosedError), so move
            # the session to a terminal state with a structured marker so the
            # UI can render the "iteratie afgebroken" banner.
            if (
                event_type == "pull_request"
                and action == "closed"
                and submission is not None
            ):
                _cascade_discard_inflight_sessions(
                    submission, merged=bool(pr.get("merged", False)),
                )
    except Exception as e:
        log.exception("webhook: upsert failed")
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

    if submission is None:
        # Nothing to report (e.g. review submitted by non-student on a non-existent submission).
        return JsonResponse(
            {
                "ok": True,
                "matched": True,
                "action": action,
                "session_created": False,
                "iteration_skipped_reason": iteration_reason,
            },
            status=200,
        )

    return JsonResponse(
        {
            "ok": True,
            "matched": True,
            "action": action,
            "submission_id": submission.id,
            "session_id": session.id if session else None,
            "session_created": created,
            "cohort": primary.cohort.name,
            "course": course.name,
            "student": primary.student.email,
            "contributors": [m.student.email for m in memberships],
            "contributor_count": len(memberships),
            "iteration_skipped_reason": iteration_reason,
        },
        status=200,
    )
