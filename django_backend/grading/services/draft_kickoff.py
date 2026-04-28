"""
Fire-and-forget draft kickoff for newly-created GradingSessions.

Why this exists
---------------
When a new iteration is created (via webhook event like review_requested, or
the manual teacher "Start nieuwe iteratie" action), the session lands in
state=PENDING. Historically the draft only actually fires when a teacher
navigates to the session in the UI (GradingSessionDetailView.vue onMounted
pings /generate_draft/ if state==pending). That client-side trigger is
fragile:

- API-only callers (tests, tooling, Slack bot in v2) don't fire it.
- If the webhook triggers an iteration while the teacher isn't in the app,
  the session sits PENDING until they click in.

This module gives webhooks.create_next_iteration (and anyone else who spawns
a PENDING iteration) a consistent server-side nudge.

Contract
--------
`fire(session_id)` returns immediately. It kicks a background thread that
POSTs to the ai_engine draft endpoint. Errors are logged, never raised —
this is belt-and-braces; the UI onMounted path is the fallback.

Note on "background thread"
---------------------------
We deliberately don't introduce Celery / RQ here — the project is still a
monolith without a broker. A daemon thread is fine because:
  1. Django's `transaction.atomic()` already committed by the time we call
     fire(); the thread reads the row fresh.
  2. Kickoff is idempotent — Django's generate_draft view is state-machine
     guarded (pending → drafting → drafted). A second caller sees DRAFTING
     and bails.
  3. If the process dies mid-draft the UI mount path still re-fires on the
     next teacher open.

Post-pitch: swap the thread for Celery or Django Q when the hosting stack
grows a broker.
"""
from __future__ import annotations

import logging
import threading
import time

log = logging.getLogger(__name__)


def fire(session_id: int, *, delay_seconds: float = 0.5) -> None:
    """
    Schedule a draft kickoff for the given session.

    Returns immediately. If the kickoff fails the session stays PENDING and
    the UI's onMounted path will retry when the teacher opens it.
    """
    t = threading.Thread(
        target=_run,
        args=(session_id, delay_seconds),
        daemon=True,
        name=f"draft-kickoff-{session_id}",
    )
    t.start()


def _run(session_id: int, delay_seconds: float) -> None:
    """
    Worker. Waits briefly so the creating transaction has time to commit,
    then calls generate_draft via the internal view dispatch.
    """
    try:
        time.sleep(delay_seconds)
        from rest_framework.test import APIRequestFactory, force_authenticate
        from django.contrib.auth import get_user_model
        from grading.models import GradingSession
        from grading.views import GradingSessionViewSet

        session = (
            GradingSession.objects
            .select_related("submission__student", "rubric", "org")
            .filter(pk=session_id)
            .first()
        )
        if session is None:
            log.info("draft_kickoff: session=%s vanished; aborting", session_id)
            return
        if session.state != GradingSession.State.PENDING:
            log.info(
                "draft_kickoff: session=%s state=%s — already progressing; skipping",
                session_id, session.state,
            )
            return

        # Pick a teacher to attribute the kickoff to. Prefer the cohort's
        # course owner; fall back to any CohortTeacher; last resort is the
        # first superuser. We only need a "docent-authenticated" request
        # because generate_draft is state-machine-guarded, not identity-
        # guarded.
        User = get_user_model()
        course = getattr(session.submission, "course", None)
        teacher = None
        if course is not None:
            teacher = getattr(course, "owner", None)
            if teacher is None:
                ct = course.cohort.teacher_assignments.select_related("teacher").first()
                teacher = ct.teacher if ct else None
        if teacher is None:
            teacher = User.objects.filter(is_superuser=True).first()
        if teacher is None:
            log.warning(
                "draft_kickoff: no teacher available for session=%s; aborting",
                session_id,
            )
            return

        # Build a DRF request and wire the auth pipeline explicitly.
        # `force_authenticate` is the documented way to skip authentication
        # while keeping request.user / request.auth populated — the old
        # `request.user = teacher` assignment on a plain Django request
        # didn't survive DRF's initialize_request() and produced 401s
        # under the hood (silent kickoff failure).
        factory = APIRequestFactory()
        request = factory.post(
            f"/api/grading/sessions/{session_id}/generate_draft/",
            data={},
            format="json",
        )
        force_authenticate(request, user=teacher)

        viewset = GradingSessionViewSet.as_view({"post": "generate_draft"})
        response = viewset(request, pk=session_id)
        # Some DRF responses need render() before status_code is stable in
        # a non-HTTP dispatch context.
        if hasattr(response, "render") and not getattr(response, "is_rendered", False):
            try:
                response.render()
            except Exception:  # pragma: no cover — defensive
                pass
        # DRF views return a Response; coerce to a status code for the log.
        status = getattr(response, "status_code", None)
        log.info(
            "draft_kickoff: session=%s status=%s teacher=%s",
            session_id, status, teacher.pk,
        )
    except Exception as e:  # pragma: no cover — best-effort
        log.exception("draft_kickoff: session=%s failed: %s", session_id, e)
