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
    ClassroomMembership,
    GradingSession,
    Submission,
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


def _membership_for_pr(
    repo_full_name: str,
    author_login: str,
) -> ClassroomMembership | None:
    """
    Match an incoming PR to a classroom membership.

    Match rules (in order, first match wins):
      1. Explicit repo_url match: ClassroomMembership.student_repo_url
         contains the PR's repo_full_name. Most common — the teacher
         configured "this student's repo is github.com/jan/assignment-q3".
      2. Student-owned repo fallback: the repo owner equals the PR author
         AND the author's GitHub handle matches a GitProviderConnection.
         Covers the case where the student created a new repo ad-hoc and
         the teacher hasn't updated ClassroomMembership yet. Requires
         repo_owner == author_login so we don't accidentally match PRs
         the student pushed to someone else's repo.
    """
    # Rule 1: explicit repo_url match
    membership = (
        ClassroomMembership.objects
        .filter(student_repo_url__icontains=repo_full_name)
        .select_related("student", "classroom")
        .first()
    )
    if membership:
        return membership

    # Rule 2: repo-owner-is-author fallback
    # Only match if the repo is OWNED by the PR author (student's own repo).
    repo_owner = (repo_full_name.split("/", 1)[0] or "").strip()
    if not repo_owner or repo_owner.lower() != (author_login or "").lower():
        return None

    from users.models import GitProviderConnection
    conn = (
        GitProviderConnection.objects
        .filter(provider="github", username__iexact=author_login)
        .select_related("user")
        .first()
    )
    if not conn:
        return None
    return (
        ClassroomMembership.objects
        .filter(student=conn.user)
        .select_related("student", "classroom")
        .first()
    )


def _upsert_submission_and_session(
    *,
    membership: ClassroomMembership,
    pr_payload: dict,
    repo_full_name: str,
) -> tuple[Submission, GradingSession, bool]:
    """
    Create-or-update the Submission for this PR and ensure a GradingSession
    exists. Returns (submission, session, created_new_session).
    """
    classroom = membership.classroom
    student = membership.student
    pr_number = int(pr_payload.get("number", 0))
    pr_state = pr_payload.get("state", "open")
    pr_merged = bool(pr_payload.get("merged", False))

    # Status mapping from GitHub PR state
    status = Submission.Status.OPEN
    if pr_state == "closed":
        status = Submission.Status.GRADED if pr_merged else Submission.Status.OPEN

    with transaction.atomic():
        submission, _ = Submission.objects.select_for_update().update_or_create(
            classroom=classroom,
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            defaults={
                "org": classroom.org,
                "student": student,
                "pr_url": pr_payload.get("html_url", ""),
                "pr_title": (pr_payload.get("title") or "")[:500],
                "base_branch": pr_payload.get("base", {}).get("ref", "main"),
                "head_branch": pr_payload.get("head", {}).get("ref", ""),
                "status": status,
            },
        )

        # Ensure GradingSession exists (one per Submission, OneToOne)
        classroom_rubric = classroom.rubric
        if classroom_rubric is None:
            log.warning(
                "webhook: classroom %s has no default rubric; skipping session creation",
                classroom.id,
            )
            return submission, None, False  # type: ignore[return-value]

        session, created = GradingSession.objects.select_for_update().get_or_create(
            submission=submission,
            defaults={
                "org": classroom.org,
                "rubric": classroom_rubric,
                "state": GradingSession.State.PENDING,
            },
        )

    return submission, session, created


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

    membership = _membership_for_pr(repo_full_name, author_login)
    if not membership:
        # Not an error — just a repo we don't track yet.
        log.info("webhook: no classroom match for %s (author=%s)", repo_full_name, author_login)
        return JsonResponse(
            {
                "ok": True,
                "matched": False,
                "message": (
                    "No classroom membership matched this repo. "
                    "Add the student's repo URL to a classroom in Django admin."
                ),
            },
            status=200,
        )

    # 6. Upsert Submission + GradingSession.
    try:
        submission, session, created = _upsert_submission_and_session(
            membership=membership,
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
            "classroom": membership.classroom.name,
            "student": membership.student.email,
        },
        status=200,
    )
