"""
Regression test: students can read their own grading sessions.

Bug seen Apr 25 2026 (student-side QA pass): GradingSessionViewSet had
class-level `permission_classes = [IsAuthenticated, IsTeacher]`, which
meant every GET to /api/grading/sessions/<id>/ returned 403 to a
student — even on their own posted session. The whole pitch loop is
"teacher posts, student reads, student grows," but students couldn't
read.

Fix: per-action permissions. `list` and `retrieve` open up to
IsAuthenticated; queryset additionally filters students to their own
sessions. Every write/state-flip action stays IsTeacher.

This test goes red if either gate slips:
  - a student can write/PATCH/POST → 403 broken, security regression
  - a student gets 403 on their own retrieve → UX regression
  - a student sees another student's session → org/student isolation broken
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from grading.models import (
    Cohort,
    CohortMembership,
    Course,
    GradingSession,
    Rubric,
    Submission,
)

User = get_user_model()


@pytest.fixture
def two_students_one_teacher(db):
    """Two students in the same cohort + a teacher, each with a posted session."""
    from users.models import Organization

    org = Organization.objects.create(name="Org Read", slug="org-read")
    teacher = User.objects.create_user(
        username="t_read", email="t_read@example.com", password="pw",
        role="teacher", organization=org,
    )
    student_a = User.objects.create_user(
        username="s_a", email="s_a@example.com", password="pw",
        role="developer", organization=org,
    )
    student_b = User.objects.create_user(
        username="s_b", email="s_b@example.com", password="pw",
        role="developer", organization=org,
    )
    rubric = Rubric.objects.create(
        org=org, owner=teacher, name="R",
        criteria=[{
            "id": "c1", "name": "C1", "weight": 1.0,
            "levels": [{"score": 1, "description": "x"}, {"score": 4, "description": "y"}],
        }],
    )
    cohort = Cohort.objects.create(org=org, name="Cohort Read")
    course = Course.objects.create(
        org=org, cohort=cohort, owner=teacher, name="Course Read", rubric=rubric,
    )
    CohortMembership.objects.create(student=student_a, cohort=cohort)
    CohortMembership.objects.create(student=student_b, cohort=cohort)

    def _make_session(student, pr_number):
        sub = Submission.objects.create(
            org=org, course=course, student=student,
            repo_full_name="acme/repo", pr_number=pr_number,
            pr_url=f"https://github.com/acme/repo/pull/{pr_number}",
            head_branch=f"feat/{pr_number}",
        )
        return GradingSession.objects.create(
            org=org, submission=sub, rubric=rubric,
            state=GradingSession.State.POSTED,
            ai_draft_scores={"c1": {"score": 3, "evidence": "ok"}},
            ai_draft_comments=[{"file": "a.py", "line": 1, "body": "fine"}],
            final_scores={"c1": {"score": 3, "evidence": "ok"}},
            final_comments=[{"file": "a.py", "line": 1, "body": "fine"}],
        )

    sess_a = _make_session(student_a, 100)
    sess_b = _make_session(student_b, 200)
    return {
        "teacher": teacher,
        "student_a": student_a, "student_b": student_b,
        "sess_a": sess_a, "sess_b": sess_b,
    }


def _client_for(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.mark.django_db
class TestStudentCanReadOwnSession:
    def test_student_a_retrieves_own_session(self, two_students_one_teacher):
        f = two_students_one_teacher
        c = _client_for(f["student_a"])
        resp = c.get(f"/api/grading/sessions/{f['sess_a'].id}/")
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["state"] == "posted"
        assert len(body["final_comments"]) == 1
        assert len(body["ai_draft_comments"]) == 1

    def test_student_a_cannot_retrieve_student_b_session(
        self, two_students_one_teacher
    ):
        """Cross-student access returns 404 (not 403) — no enumeration leak."""
        f = two_students_one_teacher
        c = _client_for(f["student_a"])
        resp = c.get(f"/api/grading/sessions/{f['sess_b'].id}/")
        assert resp.status_code == 404, resp.content

    def test_student_a_lists_only_own_sessions(self, two_students_one_teacher):
        f = two_students_one_teacher
        c = _client_for(f["student_a"])
        resp = c.get("/api/grading/sessions/")
        assert resp.status_code == 200, resp.content
        body = resp.json()
        results = body.get("results", body)
        ids = [r["id"] for r in results]
        assert f["sess_a"].id in ids
        assert f["sess_b"].id not in ids


@pytest.mark.django_db
class TestStudentCannotWriteSession:
    """Every state-flip and write must stay teacher-only even post-fix."""

    def test_student_cannot_patch_session(self, two_students_one_teacher):
        f = two_students_one_teacher
        c = _client_for(f["student_a"])
        resp = c.patch(
            f"/api/grading/sessions/{f['sess_a'].id}/",
            {"final_summary": "nice try"},
            format="json",
        )
        assert resp.status_code == 403, resp.content

    def test_student_cannot_send(self, two_students_one_teacher):
        f = two_students_one_teacher
        c = _client_for(f["student_a"])
        resp = c.post(f"/api/grading/sessions/{f['sess_a'].id}/send/")
        assert resp.status_code == 403, resp.content

    def test_student_cannot_generate_draft(self, two_students_one_teacher):
        f = two_students_one_teacher
        c = _client_for(f["student_a"])
        resp = c.post(f"/api/grading/sessions/{f['sess_a'].id}/generate_draft/")
        assert resp.status_code == 403, resp.content

    def test_student_cannot_start_review(self, two_students_one_teacher):
        f = two_students_one_teacher
        c = _client_for(f["student_a"])
        resp = c.post(f"/api/grading/sessions/{f['sess_a'].id}/start_review/")
        assert resp.status_code == 403, resp.content

    def test_student_cannot_resume(self, two_students_one_teacher):
        f = two_students_one_teacher
        c = _client_for(f["student_a"])
        resp = c.post(f"/api/grading/sessions/{f['sess_a'].id}/resume/")
        assert resp.status_code == 403, resp.content


@pytest.mark.django_db
class TestTeacherStillFullAccess:
    """Sanity: the per-action permission split didn't accidentally narrow
    teacher access."""

    def test_teacher_lists_all_org_sessions(self, two_students_one_teacher):
        f = two_students_one_teacher
        c = _client_for(f["teacher"])
        resp = c.get("/api/grading/sessions/")
        assert resp.status_code == 200, resp.content
        body = resp.json()
        results = body.get("results", body)
        ids = [r["id"] for r in results]
        assert f["sess_a"].id in ids
        assert f["sess_b"].id in ids

    def test_teacher_retrieves_either_student_session(
        self, two_students_one_teacher
    ):
        f = two_students_one_teacher
        c = _client_for(f["teacher"])
        for sess in (f["sess_a"], f["sess_b"]):
            resp = c.get(f"/api/grading/sessions/{sess.id}/")
            assert resp.status_code == 200, (sess.id, resp.content)
