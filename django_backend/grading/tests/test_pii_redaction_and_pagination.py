"""
Two student-side privacy / UX regressions, fixed together:

1. CohortMembershipSerializer leaked peer student_email + student_repo_url
   to any cohort member. Quiet GDPR/AVG issue. Fixed by gating both
   fields on viewer-is-staff or viewer-is-self via SerializerMethodField.

2. SubmissionViewSet ignored ?page_size, shipping 20-row pages
   regardless of the caller. Fixed by attaching GradingPagination —
   same class the inbox got in 9a73cb2.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from grading.models import (
    Cohort,
    CohortMembership,
    Course,
    Rubric,
    Submission,
)

User = get_user_model()


@pytest.fixture
def cohort_with_two_students(db):
    from users.models import Organization

    org = Organization.objects.create(name="Org PII", slug="org-pii")
    teacher = User.objects.create_user(
        username="t_pii", email="t_pii@example.com", password="pw",
        role="teacher", organization=org,
    )
    student_a = User.objects.create_user(
        username="s_a_pii", email="s_a_pii@example.com", password="pw",
        role="developer", organization=org,
    )
    student_b = User.objects.create_user(
        username="s_b_pii", email="s_b_pii@example.com", password="pw",
        role="developer", organization=org,
    )
    rubric = Rubric.objects.create(
        org=org, owner=teacher, name="R",
        criteria=[{
            "id": "c1", "name": "C1", "weight": 1.0,
            "levels": [{"score": 1, "description": "x"}, {"score": 4, "description": "y"}],
        }],
    )
    cohort = Cohort.objects.create(org=org, name="Cohort PII")
    Course.objects.create(
        org=org, cohort=cohort, owner=teacher, name="Course PII", rubric=rubric,
    )
    CohortMembership.objects.create(
        student=student_a, cohort=cohort,
        student_repo_url="https://github.com/student-a/secret-repo",
    )
    CohortMembership.objects.create(
        student=student_b, cohort=cohort,
        student_repo_url="https://github.com/student-b/private-repo",
    )
    return {
        "org": org, "teacher": teacher,
        "student_a": student_a, "student_b": student_b,
        "cohort": cohort,
    }


def _client_for(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


# ─────────────────────────────────────────────────────────────────────────────
# PII redaction on /cohorts/<id>/members/
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestCohortMembersPiiRedaction:
    def test_student_a_sees_own_email_and_repo(self, cohort_with_two_students):
        f = cohort_with_two_students
        c = _client_for(f["student_a"])
        resp = c.get(f"/api/grading/cohorts/{f['cohort'].id}/members/")
        assert resp.status_code == 200, resp.content
        rows = resp.json()
        own = next(r for r in rows if r["student"] == f["student_a"].id)
        assert own["student_email"] == f["student_a"].email
        assert own["student_repo_url"] == "https://github.com/student-a/secret-repo"

    def test_student_a_does_not_see_student_b_email_or_repo(
        self, cohort_with_two_students
    ):
        f = cohort_with_two_students
        c = _client_for(f["student_a"])
        resp = c.get(f"/api/grading/cohorts/{f['cohort'].id}/members/")
        assert resp.status_code == 200, resp.content
        rows = resp.json()
        peer = next(r for r in rows if r["student"] == f["student_b"].id)
        assert peer["student_email"] is None, (
            "Peer email leaked — privacy regression"
        )
        assert peer["student_repo_url"] is None, (
            "Peer repo URL leaked — privacy regression"
        )
        # Display name still visible (it's not PII; shown elsewhere in app).
        # student_id still visible (needed for routing on teacher views; on
        # student views the row is benign without email/repo).
        assert "student" in peer
        assert "student_name" in peer

    def test_teacher_sees_full_pii_for_every_member(self, cohort_with_two_students):
        f = cohort_with_two_students
        c = _client_for(f["teacher"])
        resp = c.get(f"/api/grading/cohorts/{f['cohort'].id}/members/")
        assert resp.status_code == 200, resp.content
        rows = resp.json()
        for r in rows:
            assert r["student_email"] is not None
            assert r["student_repo_url"] is not None


# ─────────────────────────────────────────────────────────────────────────────
# /submissions/ pagination
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def submissions_for_pagination(cohort_with_two_students):
    f = cohort_with_two_students
    course = Course.objects.get(cohort=f["cohort"])
    for i in range(7):
        Submission.objects.create(
            org=f["org"], course=course, student=f["student_a"],
            repo_full_name="acme/repo", pr_number=i + 1,
            pr_url=f"https://github.com/acme/repo/pull/{i + 1}",
            head_branch=f"feat/{i}",
        )
    return f


@pytest.mark.django_db
class TestSubmissionsPagination:
    def test_page_size_query_param_honored(self, submissions_for_pagination):
        f = submissions_for_pagination
        c = _client_for(f["student_a"])
        resp = c.get("/api/grading/submissions/?page_size=3")
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert len(body["results"]) == 3
        assert body["count"] == 7
        assert body["next"] is not None

    def test_default_page_size_unchanged(self, submissions_for_pagination):
        f = submissions_for_pagination
        c = _client_for(f["student_a"])
        resp = c.get("/api/grading/submissions/")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["results"]) == 7  # 7 < default 20
        assert body["next"] is None
