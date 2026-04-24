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

This is deliberately loose-coupled: we DON'T react to push events here
(those fire the existing developer-flow ai_engine webhook for the learning
loop). We DON'T pre-generate drafts on webhook — we wait for the teacher
to click Generate Draft in the inbox so we don't burn LLM budget on every
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
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.db import transaction
from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from grading.models import (
    CohortMembership,
    Course,
    GradingSession,
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

        # Iteration-aware session resolution (Leera's "what happens after
        # Send?" loop). A Submission may now have many GradingSessions.
        # Pick the latest non-superseded session; if there is none, create
        # iteration 1. If there IS one and this webhook is a `synchronize`
        # (new commits) AND the latest session is in a terminal state, then
        # the teacher already sent feedback — create a NEW session for the
        # next iteration and mark the old one superseded.
        TERMINAL_STATES = {
            GradingSession.State.POSTED,
            GradingSession.State.PARTIAL,
            GradingSession.State.FAILED,
            GradingSession.State.DISCARDED,
        }

        action = (pr_payload.get("_action") or "").strip()
        # pr_payload is the inner pull_request block; we can't read the
        # top-level `action` from it directly. Pass-through via caller would
        # be cleaner, but for minimal surface area we infer: any push that
        # changes head_branch/head_sha reaches the synchronize path upstream.
        # The caller of _upsert_submission_and_session will tag pr_payload
        # with _action before invoking us.

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
        elif action == "synchronize" and latest.state in TERMINAL_STATES:
            # New iteration — student pushed after teacher sent feedback.
            session = GradingSession.objects.create(
                org=course.org,
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
            latest.superseded_by = session
            latest.save(update_fields=["superseded_by", "updated_at"])
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

    # 4. Short-circuit anything that isn't a PR event we care about.
    if event_type != "pull_request":
        return JsonResponse(
            {"ok": True, "message": f"ignored event: {event_type}"}, status=200
        )

    action = payload.get("action", "")
    if action not in ("opened", "reopened", "synchronize", "closed"):
        return JsonResponse(
            {"ok": True, "message": f"ignored action: {action}"}, status=200
        )

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

    # 6. Upsert Submission + GradingSession + Contributors.
    # Tag the inner pr_payload with the webhook action so the iteration-aware
    # session-upsert path can distinguish `synchronize` (new commits) from
    # `opened` / `reopened` without us having to thread another argument.
    pr["_action"] = action
    try:
        submission, session, created = _upsert_submission_and_session(
            memberships=memberships,
            primary=primary,
            course=course,
            pr_payload=pr,
            repo_full_name=repo_full_name,
        )
    except Exception as e:
        log.exception("webhook: upsert failed")
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

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
        },
        status=200,
    )
