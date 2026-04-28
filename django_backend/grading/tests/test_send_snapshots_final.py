"""
Regression test: any session in POSTED has final_* populated.

Bug seen Apr 25 2026: when the teacher accepted the AI draft as-is and
clicked Send (no edits → frontend never PATCHes the session), the
github_poster posted ai_draft_comments but left session.final_comments
empty in the DB. Reopening the posted session showed a blank summary
editor and made the data layer ambiguous about "what got posted."

Fix: at every state→POSTED transition, mirror ai_draft_* into final_*
if final_* is empty. final_* becomes the canonical "what landed on
GitHub" record. Idempotent — never overwrites teacher edits.

This test goes red if the snapshot helper is removed or any future
POSTED transition site forgets to call it.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from grading.models import Cohort, Course, GradingSession, Rubric, Submission
from grading.services.github_poster import SendResult
from grading.views import _snapshot_final_from_ai_draft_if_empty

User = get_user_model()


@pytest.fixture
def teacher_session(db):
    """A reviewing-state session with AI draft populated and final_* empty."""
    from users.models import Organization

    org = Organization.objects.create(name="Org Snap", slug="org-snap")
    teacher = User.objects.create_user(
        username="t_snap", email="t_snap@example.com", password="pw",
        role="teacher", organization=org,
    )
    student = User.objects.create_user(
        username="s_snap", email="s_snap@example.com", password="pw",
        role="developer", organization=org,
    )
    rubric = Rubric.objects.create(
        org=org, owner=teacher, name="R",
        criteria=[
            {"id": "c1", "name": "C1", "weight": 1.0,
             "levels": [{"score": 1, "description": "x"}, {"score": 4, "description": "y"}]},
        ],
    )
    cohort = Cohort.objects.create(org=org, name="Cohort Snap")
    course = Course.objects.create(
        org=org, cohort=cohort, owner=teacher, name="Course Snap", rubric=rubric,
    )
    submission = Submission.objects.create(
        org=org, course=course, student=student,
        repo_full_name="acme/repo", pr_number=42,
        pr_url="https://github.com/acme/repo/pull/42",
        head_branch="feat/x",
    )
    s = GradingSession.objects.create(
        org=org, submission=submission, rubric=rubric,
        state=GradingSession.State.REVIEWING,
        ai_draft_scores={"c1": {"score": 3, "evidence": "looks ok"}},
        ai_draft_comments=[
            {"file": "src/a.py", "line": 10, "body": "comment A"},
            {"file": "src/b.py", "line": 20, "body": "comment B"},
        ],
        final_scores={},
        final_comments=[],
        final_summary="",
    )
    client = APIClient()
    client.force_authenticate(user=teacher)
    return {"session": s, "teacher": teacher, "client": client}


# ─────────────────────────────────────────────────────────────────────────────
# Helper unit tests
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestHelper:
    def test_mirrors_ai_draft_into_empty_final(self, teacher_session):
        s = teacher_session["session"]
        touched = _snapshot_final_from_ai_draft_if_empty(s)
        assert "final_comments" in touched
        assert "final_scores" in touched
        assert s.final_comments == s.ai_draft_comments
        assert s.final_scores == s.ai_draft_scores
        # Defensive copy: mutating final_* must not affect ai_draft_*.
        s.final_comments[0]["body"] = "edited"
        assert s.ai_draft_comments[0]["body"] == "comment A"

    def test_does_not_overwrite_teacher_edits(self, teacher_session):
        s = teacher_session["session"]
        edited = [{"file": "src/a.py", "line": 10, "body": "TEACHER EDIT"}]
        s.final_comments = edited
        s.final_scores = {"c1": {"score": 4, "evidence": "great"}}
        touched = _snapshot_final_from_ai_draft_if_empty(s)
        # Nothing touched — teacher's data preserved.
        assert touched == []
        assert s.final_comments == edited
        assert s.final_scores == {"c1": {"score": 4, "evidence": "great"}}

    def test_no_op_when_both_empty(self, teacher_session):
        # Some sessions may legitimately have neither ai_draft nor final
        # (e.g., draft generation failed). Helper must be a no-op there.
        s = teacher_session["session"]
        s.ai_draft_comments = []
        s.ai_draft_scores = {}
        s.final_comments = []
        s.final_scores = {}
        touched = _snapshot_final_from_ai_draft_if_empty(s)
        assert touched == []

    def test_final_summary_is_never_synthesized(self, teacher_session):
        # The AI doesn't produce a free-text summary. Honest behavior:
        # leave final_summary empty rather than fabricate one.
        s = teacher_session["session"]
        _snapshot_final_from_ai_draft_if_empty(s)
        assert s.final_summary == ""


# ─────────────────────────────────────────────────────────────────────────────
# End-to-end via /send/
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestSendSnapshotsFinal:
    def test_send_with_no_edits_mirrors_ai_draft(self, teacher_session):
        """
        Teacher accepts AI draft as-is and clicks Send. Frontend never
        PATCHes (dirty=false). Backend must still snapshot ai_draft_* into
        final_* so the DB row tells the truth about what got posted.
        """
        s = teacher_session["session"]
        client = teacher_session["client"]

        with patch("grading.services.github_poster.post_all_or_nothing") as p:
            p.return_value = SendResult(
                posted_count=2, skipped_duplicate_count=0, summary_comment_id=999,
            )
            resp = client.post(f"/api/grading/sessions/{s.id}/send/")
        assert resp.status_code == 200, resp.content
        assert resp.json()["state"] == "posted"

        s.refresh_from_db()
        assert s.state == GradingSession.State.POSTED
        # The fix in question:
        assert s.final_comments == s.ai_draft_comments
        assert s.final_scores == s.ai_draft_scores

    def test_send_with_teacher_edits_keeps_edits(self, teacher_session):
        """
        Teacher edited the draft (PATCH happened), then sent. final_*
        already populated → snapshot helper must not touch it.
        """
        s = teacher_session["session"]
        client = teacher_session["client"]
        teacher_edits_comments = [
            {"file": "src/a.py", "line": 10, "body": "TEACHER REWROTE THIS"},
        ]
        teacher_edits_scores = {"c1": {"score": 4, "evidence": "teacher view"}}
        s.final_comments = teacher_edits_comments
        s.final_scores = teacher_edits_scores
        s.final_summary = "Solid work overall."
        s.save(update_fields=["final_comments", "final_scores", "final_summary"])

        with patch("grading.services.github_poster.post_all_or_nothing") as p:
            p.return_value = SendResult(
                posted_count=1, skipped_duplicate_count=0, summary_comment_id=999,
            )
            resp = client.post(f"/api/grading/sessions/{s.id}/send/")
        assert resp.status_code == 200, resp.content

        s.refresh_from_db()
        assert s.final_comments == teacher_edits_comments
        assert s.final_scores == teacher_edits_scores
        assert s.final_summary == "Solid work overall."
