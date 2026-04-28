"""
Regression test: every FAILED/PARTIAL transition records actionable
context in partial_post_error.

Bug seen Apr 25 2026: session 46 was in state=failed with
partial_post_error=null and ai_draft_*=empty. The QA agent reported it
as "no info anywhere about what failed." Cause: the four exception
handlers in generate_draft (PRClosedError, EmptyDiffError,
LLMCeilingExceeded, LLMError|DiffTooLargeError) all flipped state to
FAILED but never wrote to partial_post_error.

Fix: every drafting-failure handler now writes
{"stage":"drafting","error_class","message",...}, plus a defensive
catch-all for unexpected exceptions. The send/resume paths (which
already wrote to the field) now also include "stage":"sending" for
parity, so the UI can differentiate "draft generation failed" from
"send failed."

This test goes red if any FAILED transition site forgets to populate
the field.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from grading.exceptions import (
    DiffTooLargeError,
    EmptyDiffError,
    LLMCeilingExceeded,
    LLMError,
    PRClosedError,
)
from grading.models import Cohort, Course, GradingSession, Rubric, Submission

User = get_user_model()


@pytest.fixture
def session_ready_to_draft(db):
    """A pending-state session ready for generate_draft to be called."""
    from users.models import Organization

    org = Organization.objects.create(name="Org Fail", slug="org-fail")
    teacher = User.objects.create_user(
        username="t_fail", email="t_fail@example.com", password="pw",
        role="teacher", organization=org,
    )
    student = User.objects.create_user(
        username="s_fail", email="s_fail@example.com", password="pw",
        role="developer", organization=org,
    )
    rubric = Rubric.objects.create(
        org=org, owner=teacher, name="R",
        criteria=[{
            "id": "c1", "name": "C1", "weight": 1.0,
            "levels": [{"score": 1, "description": "x"}, {"score": 4, "description": "y"}],
        }],
    )
    cohort = Cohort.objects.create(org=org, name="Cohort Fail")
    course = Course.objects.create(
        org=org, cohort=cohort, owner=teacher, name="Course Fail", rubric=rubric,
    )
    submission = Submission.objects.create(
        org=org, course=course, student=student,
        repo_full_name="acme/repo", pr_number=99,
        pr_url="https://github.com/acme/repo/pull/99",
        head_branch="feat/fail",
    )
    s = GradingSession.objects.create(
        org=org, submission=submission, rubric=rubric,
        state=GradingSession.State.PENDING,
    )
    client = APIClient()
    client.force_authenticate(user=teacher)
    return {"session": s, "client": client}


def _force_grader(*, raises: Exception):
    """Patch every IO point inside generate_draft to skip live calls and
    funnel the desired exception out of rubric_grader.generate_draft."""
    return patch.multiple(
        "grading.views",
        # Bypass the live GitHub fetcher fan-out — the bug is in the
        # rubric_grader call path, not the fetcher.
    ) if False else patch("grading.services.rubric_grader.generate_draft", side_effect=raises)


def _mock_github_fetch():
    """Bypass live GitHub. Return enough diff to skip empty-diff guards."""
    return patch.multiple(
        "grading.services.github_fetcher",
        fetch_pr_diff=lambda **kw: "diff --git a/x b/x\n+x\n",
        fetch_pr_commit_messages=lambda **kw: ["wip"],
        fetch_pr_body=lambda **kw: "",
    )


@pytest.mark.django_db
class TestDraftingFailureCapturesError:
    def test_empty_diff_records_stage_and_error(self, session_ready_to_draft):
        s = session_ready_to_draft["session"]
        client = session_ready_to_draft["client"]
        with _mock_github_fetch(), _force_grader(raises=EmptyDiffError("no code")):
            resp = client.post(f"/api/grading/sessions/{s.id}/generate_draft/")
        assert resp.status_code == 400
        s.refresh_from_db()
        assert s.state == GradingSession.State.FAILED
        assert s.partial_post_error is not None
        assert s.partial_post_error["stage"] == "drafting"
        assert s.partial_post_error["error_class"] == "EmptyDiffError"
        assert "empty diff" in s.partial_post_error["message"].lower()

    def test_llm_ceiling_records_stage_and_error(self, session_ready_to_draft):
        s = session_ready_to_draft["session"]
        client = session_ready_to_draft["client"]
        with _mock_github_fetch(), _force_grader(raises=LLMCeilingExceeded("ceiling 5 EUR/day")):
            resp = client.post(f"/api/grading/sessions/{s.id}/generate_draft/")
        assert resp.status_code == 429
        s.refresh_from_db()
        assert s.state == GradingSession.State.FAILED
        assert s.partial_post_error["stage"] == "drafting"
        assert s.partial_post_error["error_class"] == "LLMCeilingExceeded"
        assert "ceiling" in s.partial_post_error["message"]

    def test_llm_error_records_stage_and_error(self, session_ready_to_draft):
        s = session_ready_to_draft["session"]
        client = session_ready_to_draft["client"]
        with _mock_github_fetch(), _force_grader(raises=LLMError("anthropic 503")):
            resp = client.post(f"/api/grading/sessions/{s.id}/generate_draft/")
        assert resp.status_code == 502
        s.refresh_from_db()
        assert s.state == GradingSession.State.FAILED
        assert s.partial_post_error["stage"] == "drafting"
        assert s.partial_post_error["error_class"] == "LLMError"
        assert "anthropic 503" in s.partial_post_error["message"]

    def test_diff_too_large_records_stage_and_error(self, session_ready_to_draft):
        s = session_ready_to_draft["session"]
        client = session_ready_to_draft["client"]
        with _mock_github_fetch(), _force_grader(raises=DiffTooLargeError("100 KB")):
            resp = client.post(f"/api/grading/sessions/{s.id}/generate_draft/")
        assert resp.status_code == 502
        s.refresh_from_db()
        assert s.state == GradingSession.State.FAILED
        assert s.partial_post_error["stage"] == "drafting"
        assert s.partial_post_error["error_class"] == "DiffTooLargeError"

    def test_unexpected_exception_does_not_leave_session_in_drafting(
        self, session_ready_to_draft
    ):
        """
        Defensive catch-all: any unexpected exception during the LLM call
        (network blip, JSON parse error, KeyError on a malformed response,
        etc.) must flip state to FAILED with context — NOT leave the
        session stuck in DRAFTING with a spinning UI forever.
        """
        s = session_ready_to_draft["session"]
        client = session_ready_to_draft["client"]
        with _mock_github_fetch(), _force_grader(raises=KeyError("missing 'scores' key")):
            resp = client.post(f"/api/grading/sessions/{s.id}/generate_draft/")
        assert resp.status_code == 500
        s.refresh_from_db()
        assert s.state == GradingSession.State.FAILED, (
            "stuck in DRAFTING — the catch-all is missing or broken"
        )
        assert s.partial_post_error["stage"] == "drafting"
        assert s.partial_post_error["error_class"] == "KeyError"
        assert s.partial_post_error.get("unexpected") is True

    def test_pr_closed_during_fetch_records_stage_and_error(self, session_ready_to_draft):
        """
        PRClosedError raised by the GitHub fetcher (PR was closed between
        webhook and teacher click). Different code path: it gets handled
        BEFORE the rubric_grader call, in the fan-out except block.
        """
        s = session_ready_to_draft["session"]
        client = session_ready_to_draft["client"]
        from grading.services import github_fetcher
        with patch.object(
            github_fetcher, "fetch_pr_diff",
            side_effect=PRClosedError("PR was closed"),
        ), patch.object(
            github_fetcher, "fetch_pr_commit_messages", return_value=[],
        ), patch.object(
            github_fetcher, "fetch_pr_body", return_value="",
        ):
            resp = client.post(f"/api/grading/sessions/{s.id}/generate_draft/")
        assert resp.status_code == 409
        s.refresh_from_db()
        assert s.state == GradingSession.State.FAILED
        assert s.partial_post_error["stage"] == "drafting"
        assert s.partial_post_error["error_class"] == "PRClosedError"
