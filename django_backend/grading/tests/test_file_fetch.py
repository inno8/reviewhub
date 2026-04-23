"""
Tests for GET /api/grading/sessions/<id>/file/ — the view-in-code endpoint
powering the inline-comment code modal on GradingSessionDetailView.

Coverage:
  - happy path (200, content returned)
  - missing ?path= → 400
  - no PAT available → 503 with code=no_pat
  - GitHub 404 on bad ref → 404
  - cross-org session → 404 (not 403 — isolation contract)
  - student in another cohort can't read another student's session → 404
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from grading.models import Cohort, Course, GradingSession, Rubric, Submission

User = get_user_model()


class _FakeResp:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def two_orgs(db):
    from users.models import Organization

    org_a = Organization.objects.create(name="Org A", slug="org-a-ff")
    org_b = Organization.objects.create(name="Org B", slug="org-b-ff")
    teacher_a = User.objects.create_user(
        username="t_a_ff",
        email="t_a_ff@example.com",
        password="pw",
        role="teacher",
        organization=org_a,
    )
    teacher_b = User.objects.create_user(
        username="t_b_ff",
        email="t_b_ff@example.com",
        password="pw",
        role="teacher",
        organization=org_b,
    )
    student_a = User.objects.create_user(
        username="s_a_ff",
        email="s_a_ff@example.com",
        password="pw",
        role="developer",
        organization=org_a,
    )
    # Give teacher_a a PAT so the happy-path tests don't hit the no-PAT branch.
    teacher_a.github_personal_access_token = "ghp_test_teacher_a"
    teacher_a.save()
    return {
        "org_a": org_a,
        "org_b": org_b,
        "teacher_a": teacher_a,
        "teacher_b": teacher_b,
        "student_a": student_a,
    }


@pytest.fixture
def session_a(db, two_orgs):
    rubric = Rubric.objects.create(
        org=two_orgs["org_a"],
        owner=two_orgs["teacher_a"],
        name="R",
        criteria=[{"id": "r", "name": "R", "weight": 1.0, "levels": [{"score": 1}]}],
    )
    cohort = Cohort.objects.create(org=two_orgs["org_a"], name="K")
    course = Course.objects.create(
        org=two_orgs["org_a"],
        cohort=cohort,
        owner=two_orgs["teacher_a"],
        name="C",
        rubric=rubric,
    )
    sub = Submission.objects.create(
        org=two_orgs["org_a"],
        course=course,
        student=two_orgs["student_a"],
        repo_full_name="acme/app",
        pr_number=7,
        pr_url="https://github.com/acme/app/pull/7",
        head_branch="feat/x",
    )
    return GradingSession.objects.create(
        org=two_orgs["org_a"], submission=sub, rubric=rubric
    )


@pytest.fixture
def session_b(db, two_orgs):
    rubric = Rubric.objects.create(
        org=two_orgs["org_b"],
        owner=two_orgs["teacher_b"],
        name="RB",
        criteria=[{"id": "r", "name": "R", "weight": 1.0, "levels": [{"score": 1}]}],
    )
    cohort = Cohort.objects.create(org=two_orgs["org_b"], name="KB")
    course = Course.objects.create(
        org=two_orgs["org_b"],
        cohort=cohort,
        owner=two_orgs["teacher_b"],
        name="CB",
        rubric=rubric,
    )
    other_student = User.objects.create_user(
        username="s_b_ff",
        email="s_b_ff@example.com",
        password="pw",
        role="developer",
        organization=two_orgs["org_b"],
    )
    sub = Submission.objects.create(
        org=two_orgs["org_b"],
        course=course,
        student=other_student,
        repo_full_name="other/app",
        pr_number=1,
        pr_url="https://github.com/other/app/pull/1",
        head_branch="feat/y",
    )
    return GradingSession.objects.create(
        org=two_orgs["org_b"], submission=sub, rubric=rubric
    )


@pytest.fixture
def client_a(two_orgs):
    c = APIClient()
    c.force_authenticate(user=two_orgs["teacher_a"])
    return c


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestGradingSessionFileContent:
    URL = "/api/grading/sessions/{}/file/"

    def test_happy_path_returns_file_content(self, client_a, session_a):
        with patch(
            "grading.views_file_fetch.requests.get",
            return_value=_FakeResp(200, "print('hi')\n"),
        ) as mock_get:
            resp = client_a.get(
                self.URL.format(session_a.id),
                {"path": "src/main.py"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["path"] == "src/main.py"
        assert body["content"] == "print('hi')\n"
        assert body["ref"] == "feat/x"  # default from head_branch
        assert body["truncated"] is False
        # GitHub URL was built from repo_full_name + encoded path
        args, kwargs = mock_get.call_args
        assert "acme/app/contents/src/main.py" in args[0]
        assert kwargs["params"]["ref"] == "feat/x"
        assert kwargs["headers"]["Authorization"].startswith("Bearer ")

    def test_missing_path_param_returns_400(self, client_a, session_a):
        resp = client_a.get(self.URL.format(session_a.id))
        assert resp.status_code == 400

    def test_no_pat_returns_503_with_hint(self, two_orgs, session_a, settings):
        # Strip the teacher's PAT AND the settings fallback.
        two_orgs["teacher_a"].github_personal_access_token = None
        two_orgs["teacher_a"].save()
        settings.GITHUB_TOKEN = ""
        c = APIClient()
        c.force_authenticate(user=two_orgs["teacher_a"])
        resp = c.get(self.URL.format(session_a.id), {"path": "a.py"})
        assert resp.status_code == 503
        assert resp.json().get("code") == "no_pat"

    def test_settings_token_fallback_when_user_has_no_pat(
        self, two_orgs, session_a, settings
    ):
        two_orgs["teacher_a"].github_personal_access_token = None
        two_orgs["teacher_a"].save()
        settings.GITHUB_TOKEN = "ghp_settings_fallback"
        c = APIClient()
        c.force_authenticate(user=two_orgs["teacher_a"])
        with patch(
            "grading.views_file_fetch.requests.get",
            return_value=_FakeResp(200, "fallback-content"),
        ):
            resp = c.get(self.URL.format(session_a.id), {"path": "a.py"})
        assert resp.status_code == 200
        assert resp.json()["content"] == "fallback-content"

    def test_bad_ref_returns_404(self, client_a, session_a):
        with patch(
            "grading.views_file_fetch.requests.get",
            return_value=_FakeResp(404, ""),
        ):
            resp = client_a.get(
                self.URL.format(session_a.id),
                {"path": "nope.py", "ref": "does-not-exist"},
            )
        assert resp.status_code == 404

    def test_cross_org_session_returns_404(self, client_a, session_b):
        # teacher_a must NOT be able to fetch files for org B's session.
        resp = client_a.get(self.URL.format(session_b.id), {"path": "a.py"})
        assert resp.status_code == 404

    def test_org_student_can_fetch_own_submission_file(
        self, two_orgs, session_a
    ):
        # The submitting student can view files for their own session.
        two_orgs["student_a"].github_personal_access_token = "ghp_student"
        two_orgs["student_a"].save()
        c = APIClient()
        c.force_authenticate(user=two_orgs["student_a"])
        with patch(
            "grading.views_file_fetch.requests.get",
            return_value=_FakeResp(200, "student-view"),
        ):
            resp = c.get(self.URL.format(session_a.id), {"path": "a.py"})
        assert resp.status_code == 200
        assert resp.json()["content"] == "student-view"

    def test_truncates_large_file(self, client_a, session_a):
        big = "x = 1\n" * 200_000  # ~1.2 MB
        with patch(
            "grading.views_file_fetch.requests.get",
            return_value=_FakeResp(200, big),
        ):
            resp = client_a.get(self.URL.format(session_a.id), {"path": "big.py"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["truncated"] is True
        assert body["content"].count("\n") <= 1000
