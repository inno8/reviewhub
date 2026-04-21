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
from urllib.parse import urlparse

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

        session, created = GradingSession.objects.select_for_update().get_or_create(
            submission=submission,
            defaults={
                "org": course.org,
                "rubric": course_rubric,
                "state": GradingSession.State.PENDING,
            },
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

    # 2. Delivery ID dedupe — GitHub retries on timeout; we reject dupes
    #    at the edge in <5ms (eng-review concurrency bundle #3).
    delivery_id = request.META.get("HTTP_X_GITHUB_DELIVERY", "")
    event_type = request.META.get("HTTP_X_GITHUB_EVENT", "")
    if delivery_id:
        _, created = WebhookDelivery.objects.get_or_create(
            provider="github",
            delivery_id=delivery_id,
            defaults={"event_type": event_type},
        )
        if not created:
            return JsonResponse({"ok": True, "deduped": True}, status=200)

    # 3. Parse payload.
    try:
        payload = json.loads(body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return HttpResponseBadRequest("invalid payload")

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
