"""
Tests for grading.services.github_poster.

Key guarantees being tested (all flagged P1 in the eng review):
  1. Idempotency: same comment posted twice → single GitHub POST + single PostedComment row.
  2. Partial-post recovery: GitHub fails mid-loop → PartialPostError with posted_ids;
     Resume picks up and posts the rest without duplicating.
  3. PR-closed handling: GitHub returns state=closed → PRClosedError, no comments attempted.
  4. Idempotency across Send + Resume: PostedComment dedupe works on both paths.

Uses `responses` (via monkeypatch of requests) to avoid hitting real GitHub.
No PyPI dependency — we stub requests.post/get directly.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from grading.exceptions import PartialPostError, PRClosedError
from grading.models import Cohort, Course, GradingSession, PostedComment, Rubric, Submission
from grading.services import github_poster

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Minimal DB fixtures (independent of the org-isolation suite)
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def session(db):
    """A GradingSession ready to send, with 3 approved comments."""
    from users.models import Organization

    org = Organization.objects.create(name="Test Org", slug="test-org")
    teacher = User.objects.create_user(
        username="t", email="t@ex.com", password="pw",
        role="teacher", organization=org,
    )
    student = User.objects.create_user(
        username="s", email="s@ex.com", password="pw",
        role="developer", organization=org,
    )
    rubric = Rubric.objects.create(
        org=org, owner=teacher, name="R",
        criteria=[
            {
                "id": "c1", "name": "C1", "weight": 1.0,
                "levels": [{"score": 1, "description": "bad"}, {"score": 4, "description": "good"}],
            }
        ],
    )
    cohort = Cohort.objects.create(org=org, name="Klas")
    course = Course.objects.create(org=org, cohort=cohort, owner=teacher, name="Cls", rubric=rubric)
    submission = Submission.objects.create(
        org=org, course=course, student=student,
        repo_full_name="s/repo", pr_number=1,
        pr_url="https://github.com/s/repo/pull/1",
        head_branch="feat",
    )
    s = GradingSession.objects.create(
        org=org, submission=submission, rubric=rubric,
        state=GradingSession.State.SENDING,
        final_scores={"c1": {"score": 3, "evidence": "looks ok"}},
        final_comments=[
            {"file": "src/a.py", "line": 10, "body": "body A"},
            {"file": "src/b.py", "line": 20, "body": "body B"},
            {"file": "src/c.py", "line": 30, "body": "body C"},
        ],
        final_summary="Solid work.",
    )
    return s


# ─────────────────────────────────────────────────────────────────────────────
# HTTP helpers for the mock
# ─────────────────────────────────────────────────────────────────────────────
class FakeResponse:
    def __init__(self, status_code: int, body: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._body = body or {}
        self.text = text or json.dumps(self._body)

    def json(self):
        return self._body


def _pr_snapshot_response(state: str = "open", merged: bool = False) -> FakeResponse:
    return FakeResponse(
        200,
        {"state": state, "merged": merged, "head": {"sha": "abc123"}},
    )


def _comment_response(comment_id: int = 1001) -> FakeResponse:
    return FakeResponse(201, {"id": comment_id})


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestHappyPath:
    def test_posts_all_three_inline_plus_summary(self, session):
        posts = []
        gets = []

        def fake_get(url, **kw):
            gets.append(url)
            return _pr_snapshot_response()

        def fake_post(url, **kw):
            posts.append((url, kw.get("json")))
            return _comment_response(1000 + len(posts))

        with patch("grading.services.github_poster.requests.get", side_effect=fake_get), \
             patch("grading.services.github_poster.requests.post", side_effect=fake_post):
            result = github_poster.post_all_or_nothing(session, teacher_pat="pat_test")

        # 1 GET (PR snapshot) + 3 inline + 1 summary = 4 POSTs
        assert len(gets) == 1
        assert len(posts) == 4
        assert result.posted_count == 3
        assert result.skipped_duplicate_count == 0
        assert result.summary_comment_id is not None

        # PostedComment ledger has 3 rows
        assert PostedComment.objects.filter(grading_session=session).count() == 3

        # Mutation IDs are deterministic per (session, file, line, body_hash)
        ids = set(
            PostedComment.objects.filter(grading_session=session)
            .values_list("client_mutation_id", flat=True)
        )
        assert len(ids) == 3  # all distinct


@pytest.mark.django_db
class TestIdempotency:
    def test_second_send_skips_already_posted(self, session):
        """Send, then Send again: second call posts nothing, skips all three."""
        # First send → seed PostedComment rows
        with patch("grading.services.github_poster.requests.get",
                   side_effect=lambda *a, **kw: _pr_snapshot_response()), \
             patch("grading.services.github_poster.requests.post",
                   side_effect=[
                       _comment_response(1001), _comment_response(1002),
                       _comment_response(1003), _comment_response(2001),  # summary
                   ]):
            github_poster.post_all_or_nothing(session, teacher_pat="pat")

        assert PostedComment.objects.filter(grading_session=session).count() == 3

        # Second send → inline POSTs should be 0 (all dupes), summary still posts
        second_posts = []

        def capture_post(url, **kw):
            second_posts.append(url)
            return _comment_response(9999)

        with patch("grading.services.github_poster.requests.get",
                   side_effect=lambda *a, **kw: _pr_snapshot_response()), \
             patch("grading.services.github_poster.requests.post",
                   side_effect=capture_post):
            result = github_poster.post_all_or_nothing(session, teacher_pat="pat")

        # Only the summary POST happens on re-send (no inline re-posts)
        summary_posts = [u for u in second_posts if "/issues/" in u]
        inline_posts = [u for u in second_posts if "/pulls/1/comments" in u]
        assert len(inline_posts) == 0  # zero inline re-posts
        assert len(summary_posts) == 1  # summary always posts
        assert result.skipped_duplicate_count == 3

    def test_body_change_produces_new_mutation_id(self, session):
        """If the docent edits a comment body between Send attempts, the new
        comment should post (different mutation_id)."""
        from grading.models import PostedComment as PC

        # Simulate a prior send with OLD body text
        original_body = "body A"
        old_mid = PC.compute_mutation_id(session.id, "src/a.py", 10, original_body)
        PC.objects.create(
            grading_session=session, client_mutation_id=old_mid,
            github_comment_id=777, file_path="src/a.py", line_number=10,
            body_preview=original_body,
        )

        # Docent edits comment #1 (body A → body A++) and clicks Send again
        session.final_comments = [
            {"file": "src/a.py", "line": 10, "body": "body A++"},  # changed
            {"file": "src/b.py", "line": 20, "body": "body B"},
            {"file": "src/c.py", "line": 30, "body": "body C"},
        ]
        session.save(update_fields=["final_comments"])

        with patch("grading.services.github_poster.requests.get",
                   side_effect=lambda *a, **kw: _pr_snapshot_response()), \
             patch("grading.services.github_poster.requests.post",
                   side_effect=[
                       _comment_response(1101),  # re-post edited #1
                       _comment_response(1102),  # new #2
                       _comment_response(1103),  # new #3
                       _comment_response(2001),  # summary
                   ]):
            result = github_poster.post_all_or_nothing(session, teacher_pat="pat")

        # Edited body → new mutation_id → not a duplicate → re-posted
        assert result.posted_count == 3
        # PostedComment ledger has 4: old (unchanged) + 3 new
        assert PC.objects.filter(grading_session=session).count() == 4


@pytest.mark.django_db
class TestPartialPost:
    def test_failure_on_second_comment_raises_with_posted_ids(self, session):
        """Simulate: 1st inline succeeds, 2nd fails with 502."""
        call_count = {"n": 0}

        def fake_post(url, **kw):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return _comment_response(5001)
            if call_count["n"] == 2:
                return FakeResponse(502, text="upstream failed")
            return _comment_response(5002)

        with patch("grading.services.github_poster.requests.get",
                   side_effect=lambda *a, **kw: _pr_snapshot_response()), \
             patch("grading.services.github_poster.requests.post",
                   side_effect=fake_post):
            with pytest.raises(PartialPostError) as exc_info:
                github_poster.post_all_or_nothing(session, teacher_pat="pat")

        err = exc_info.value
        assert len(err.posted_ids) == 1
        assert err.posted_ids[0] == 5001
        assert err.failed_at == 1  # second comment (index 1)

        # PostedComment ledger: exactly 1 row for the one that landed.
        assert PostedComment.objects.filter(grading_session=session).count() == 1

    def test_resume_after_partial_posts_only_the_remaining(self, session):
        """After partial failure, Resume should re-attempt the un-posted ones."""
        # Stage: first comment already posted on a prior run
        from grading.models import PostedComment as PC

        c0 = session.final_comments[0]
        mid0 = PC.compute_mutation_id(session.id, c0["file"], c0["line"], c0["body"])
        PC.objects.create(
            grading_session=session, client_mutation_id=mid0,
            github_comment_id=5001, file_path=c0["file"], line_number=c0["line"],
            body_preview=c0["body"],
        )

        # Resume: GitHub should see POSTs only for comments 2 and 3, plus summary
        posted_urls: list[str] = []

        def capture_post(url, **kw):
            posted_urls.append(url)
            return _comment_response(6000 + len(posted_urls))

        with patch("grading.services.github_poster.requests.get",
                   side_effect=lambda *a, **kw: _pr_snapshot_response()), \
             patch("grading.services.github_poster.requests.post",
                   side_effect=capture_post):
            result = github_poster.resume_partial(session, teacher_pat="pat")

        assert result.posted_count == 2  # #2 and #3
        assert result.skipped_duplicate_count == 1  # #1
        inline_posts = [u for u in posted_urls if "/pulls/1/comments" in u]
        assert len(inline_posts) == 2


@pytest.mark.django_db
class TestPRClosed:
    def test_closed_pr_raises_before_any_comment_posts(self, session):
        posts: list = []

        def fake_post(url, **kw):
            posts.append(url)
            return _comment_response(9999)

        with patch("grading.services.github_poster.requests.get",
                   side_effect=lambda *a, **kw: _pr_snapshot_response(state="closed")), \
             patch("grading.services.github_poster.requests.post",
                   side_effect=fake_post):
            with pytest.raises(PRClosedError):
                github_poster.post_all_or_nothing(session, teacher_pat="pat")

        # Nothing posted.
        assert len(posts) == 0
        assert PostedComment.objects.filter(grading_session=session).count() == 0


@pytest.mark.django_db
class TestMalformedComments:
    def test_skips_comments_missing_path_or_line(self, session):
        """Bad comment payloads are logged and skipped, not sent."""
        session.final_comments = [
            {"file": "src/a.py", "line": 10, "body": "good"},
            {"file": "", "line": 20, "body": "bad — empty file"},       # skip
            {"file": "src/c.py", "line": 0, "body": "bad — line 0"},    # skip
            {"file": "src/d.py", "line": 40, "body": ""},               # skip
            {"file": "src/e.py", "line": 50, "body": "good"},
        ]
        session.save(update_fields=["final_comments"])

        posts = []

        def fake_post(url, **kw):
            posts.append(kw.get("json"))
            return _comment_response(7000 + len(posts))

        with patch("grading.services.github_poster.requests.get",
                   side_effect=lambda *a, **kw: _pr_snapshot_response()), \
             patch("grading.services.github_poster.requests.post",
                   side_effect=fake_post):
            result = github_poster.post_all_or_nothing(session, teacher_pat="pat")

        # Only 2 valid inline + 1 summary = 3 POSTs
        assert len(posts) == 3
        inline_posts = [p for p in posts if "commit_id" in p]
        assert len(inline_posts) == 2
        assert result.posted_count == 2
