"""
Tests for the Leera suggested_snippet feature:

  1. github_poster formats the posted PR comment body with GitHub's
     ```suggestion code-fence block when ``suggested_snippet`` is non-empty
     on a grading comment. This unlocks the native "Commit suggestion"
     button on the student's PR.

  2. GradingSessionEditSerializer validates the optional snippet fields
     (original_snippet, suggested_snippet, teacher_explanation) on PATCH:
     accepts strings, rejects non-strings, remains backward-compatible
     for comments that omit the fields entirely.

Separate file (not extending test_github_poster.py) so the Leera feature
has a clean, greppable test surface.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from grading.models import (
    Cohort,
    Course,
    GradingSession,
    PostedComment,
    Rubric,
    Submission,
)
from grading.serializers import GradingSessionEditSerializer
from grading.services import github_poster
from grading.services.github_poster import _format_comment_body

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixture: minimal sendable GradingSession
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def session(db):
    from users.models import Organization

    org = Organization.objects.create(name="Test Org Sugg", slug="test-org-sugg")
    teacher = User.objects.create_user(
        username="t_sugg", email="t_sugg@ex.com", password="pw",
        role="teacher", organization=org,
    )
    student = User.objects.create_user(
        username="s_sugg", email="s_sugg@ex.com", password="pw",
        role="developer", organization=org,
    )
    rubric = Rubric.objects.create(
        org=org, owner=teacher, name="R",
        criteria=[
            {
                "id": "c1", "name": "C1", "weight": 1.0,
                "levels": [{"score": 1, "description": "bad"},
                           {"score": 4, "description": "good"}],
            }
        ],
    )
    cohort = Cohort.objects.create(org=org, name="KlasSugg")
    course = Course.objects.create(
        org=org, cohort=cohort, owner=teacher, name="Cls", rubric=rubric,
    )
    submission = Submission.objects.create(
        org=org, course=course, student=student,
        repo_full_name="s/repo", pr_number=1,
        pr_url="https://github.com/s/repo/pull/1",
        head_branch="feat",
    )
    return GradingSession.objects.create(
        org=org, submission=submission, rubric=rubric,
        state=GradingSession.State.SENDING,
        final_scores={"c1": {"score": 3, "evidence": "ok"}},
        final_comments=[],  # overridden per test
        final_summary="",
    )


class FakeResponse:
    def __init__(self, status_code: int, body: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._body = body or {}
        self.text = text or json.dumps(self._body)

    def json(self):
        return self._body


def _pr_snapshot_response() -> FakeResponse:
    return FakeResponse(200, {"state": "open", "merged": False, "head": {"sha": "abc123"}})


def _comment_response(comment_id: int = 1001) -> FakeResponse:
    return FakeResponse(201, {"id": comment_id})


# ─────────────────────────────────────────────────────────────────────────────
# _format_comment_body unit tests (the helper is what shape-assemble tests
# depend on; we test the integration through post_all_or_nothing below too)
# ─────────────────────────────────────────────────────────────────────────────
class TestFormatCommentBody:
    def test_body_only(self):
        assert _format_comment_body(body="Hello") == "Hello"

    def test_body_and_suggestion(self):
        got = _format_comment_body(body="Use const instead.", suggested_snippet="const x = 1;")
        assert got == "Use const instead.\n\n```suggestion\nconst x = 1;\n```"

    def test_body_and_explanation(self):
        got = _format_comment_body(
            body="Naming nit.",
            teacher_explanation="Prefer snake_case here — it's the house style.",
        )
        assert got == "Naming nit.\n\nPrefer snake_case here — it's the house style."

    def test_body_explanation_and_suggestion_order(self):
        got = _format_comment_body(
            body="Refactor this.",
            teacher_explanation="Single responsibility.",
            suggested_snippet="def add(a, b):\n    return a + b",
        )
        # Order must be: body, explanation, suggestion fence.
        assert got == (
            "Refactor this.\n"
            "\n"
            "Single responsibility.\n"
            "\n"
            "```suggestion\n"
            "def add(a, b):\n"
            "    return a + b\n"
            "```"
        )

    def test_suggestion_preserves_newlines_and_indentation(self):
        snippet = "def foo():\n    if x:\n        return 1\n    return 0"
        got = _format_comment_body(body="fix", suggested_snippet=snippet)
        assert "```suggestion\n" + snippet + "\n```" in got

    def test_empty_snippet_is_ignored(self):
        # whitespace-only snippet should not render a fence
        assert _format_comment_body(body="hi", suggested_snippet="   \n  ") == "hi"


# ─────────────────────────────────────────────────────────────────────────────
# post_all_or_nothing: end-to-end body formatting in the HTTP payload
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestPosterSuggestionIntegration:
    def _run(self, session, capture):
        with patch("grading.services.github_poster.requests.get",
                   side_effect=lambda *a, **kw: _pr_snapshot_response()), \
             patch("grading.services.github_poster.requests.post",
                   side_effect=capture):
            return github_poster.post_all_or_nothing(session, teacher_pat="pat")

    def _inline_body(self, posts):
        """First inline-comment POST body (filtered from summary posts)."""
        for url, payload in posts:
            if "/pulls/" in url and "/comments" in url:
                return payload["body"]
        raise AssertionError("no inline POST captured")

    def test_non_empty_snippet_emits_suggestion_block(self, session):
        session.final_comments = [{
            "file": "src/a.py", "line": 10,
            "body": "Use a list comp here.",
            "suggested_snippet": "[x * 2 for x in items]",
        }]
        session.save(update_fields=["final_comments"])

        posts = []

        def capture(url, **kw):
            posts.append((url, kw.get("json")))
            return _comment_response(2001)

        self._run(session, capture)
        body = self._inline_body(posts)
        assert "```suggestion\n[x * 2 for x in items]\n```" in body

    def test_empty_snippet_no_suggestion_block(self, session):
        session.final_comments = [{
            "file": "src/a.py", "line": 10,
            "body": "Looks good.",
            "suggested_snippet": "",
        }]
        session.save(update_fields=["final_comments"])

        posts = []

        def capture(url, **kw):
            posts.append((url, kw.get("json")))
            return _comment_response(2001)

        self._run(session, capture)
        body = self._inline_body(posts)
        assert "```suggestion" not in body
        assert body == "Looks good."

    def test_teacher_explanation_renders_between_body_and_suggestion(self, session):
        session.final_comments = [{
            "file": "src/a.py", "line": 10,
            "body": "Tighten this.",
            "teacher_explanation": "Single responsibility.",
            "suggested_snippet": "return early",
        }]
        session.save(update_fields=["final_comments"])

        posts = []

        def capture(url, **kw):
            posts.append((url, kw.get("json")))
            return _comment_response(2001)

        self._run(session, capture)
        body = self._inline_body(posts)
        # Order check: body, explanation, then fence.
        i_body = body.index("Tighten this.")
        i_expl = body.index("Single responsibility.")
        i_fence = body.index("```suggestion")
        assert i_body < i_expl < i_fence

    def test_explanation_only_no_fence(self, session):
        session.final_comments = [{
            "file": "src/a.py", "line": 10,
            "body": "Naming nit.",
            "teacher_explanation": "Prefer snake_case.",
        }]
        session.save(update_fields=["final_comments"])

        posts = []

        def capture(url, **kw):
            posts.append((url, kw.get("json")))
            return _comment_response(2001)

        self._run(session, capture)
        body = self._inline_body(posts)
        assert "```suggestion" not in body
        assert body == "Naming nit.\n\nPrefer snake_case."

    def test_snippet_preserves_indentation_exactly(self, session):
        snippet = "if flag:\n    do_thing()\nelse:\n    do_other()"
        session.final_comments = [{
            "file": "src/a.py", "line": 10,
            "body": "Flip branches.",
            "suggested_snippet": snippet,
        }]
        session.save(update_fields=["final_comments"])

        posts = []

        def capture(url, **kw):
            posts.append((url, kw.get("json")))
            return _comment_response(2001)

        self._run(session, capture)
        body = self._inline_body(posts)
        assert f"```suggestion\n{snippet}\n```" in body

    def test_backward_compat_no_new_fields(self, session):
        """A comment with only file/line/body still posts as it did pre-Leera."""
        session.final_comments = [{
            "file": "src/a.py", "line": 10,
            "body": "Classic comment, no snippet.",
        }]
        session.save(update_fields=["final_comments"])

        posts = []

        def capture(url, **kw):
            posts.append((url, kw.get("json")))
            return _comment_response(2001)

        result = self._run(session, capture)
        body = self._inline_body(posts)
        assert body == "Classic comment, no snippet."
        assert result.posted_count == 1
        # Ledger row written (mutation_id matches legacy body-only hash).
        assert PostedComment.objects.filter(grading_session=session).count() == 1


# ─────────────────────────────────────────────────────────────────────────────
# Serializer: accept / reject new optional fields
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestSerializerSuggestionFields:
    def test_accepts_string_snippet_fields(self, session):
        payload = {
            "final_comments": [{
                "file": "src/a.py", "line": 10, "body": "body",
                "original_snippet": "old()",
                "suggested_snippet": "new()",
                "teacher_explanation": "Because reasons.",
            }]
        }
        ser = GradingSessionEditSerializer(session, data=payload, partial=True)
        assert ser.is_valid(), ser.errors
        ser.save()
        session.refresh_from_db()
        c = session.final_comments[0]
        assert c["suggested_snippet"] == "new()"
        assert c["original_snippet"] == "old()"
        assert c["teacher_explanation"] == "Because reasons."

    def test_rejects_non_string_suggested_snippet(self, session):
        payload = {
            "final_comments": [{
                "file": "src/a.py", "line": 10, "body": "body",
                "suggested_snippet": 12345,
            }]
        }
        ser = GradingSessionEditSerializer(session, data=payload, partial=True)
        assert not ser.is_valid()
        assert "final_comments" in ser.errors

    def test_backward_compat_missing_fields_accepted(self, session):
        payload = {
            "final_comments": [
                {"file": "src/a.py", "line": 10, "body": "no new fields"},
            ]
        }
        ser = GradingSessionEditSerializer(session, data=payload, partial=True)
        assert ser.is_valid(), ser.errors
        ser.save()
        session.refresh_from_db()
        assert session.final_comments[0]["body"] == "no new fields"
