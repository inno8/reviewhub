"""
Critical regression test: cross-org isolation.

From the eng-review + CEO-review threat model: the single most important
correctness bet in the grading app is that org A cannot read, update, or
send data belonging to org B. Every ViewSet relies on OrgScopedManager.for_user().

This test creates two orgs, puts a teacher + rubric + classroom + session in
each, and verifies that teacher-A gets 404 (NOT 403, to prevent enumeration)
on every teacher-B resource across every endpoint and every method.

If this test ever goes red, STOP and audit — the guarantee is broken.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from grading.models import Classroom, GradingSession, Rubric, Submission

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def two_orgs(db):
    """Create two independent orgs with a teacher + student each."""
    from users.models import Organization

    org_a = Organization.objects.create(name="Org A", slug="org-a")
    org_b = Organization.objects.create(name="Org B", slug="org-b")

    teacher_a = User.objects.create_user(
        username="teacher_a",
        email="teacher_a@example.com",
        password="pw",
        role="teacher",
        organization=org_a,
    )
    teacher_b = User.objects.create_user(
        username="teacher_b",
        email="teacher_b@example.com",
        password="pw",
        role="teacher",
        organization=org_b,
    )
    student_a = User.objects.create_user(
        username="student_a",
        email="student_a@example.com",
        password="pw",
        role="developer",
        organization=org_a,
    )
    student_b = User.objects.create_user(
        username="student_b",
        email="student_b@example.com",
        password="pw",
        role="developer",
        organization=org_b,
    )
    return {
        "org_a": org_a,
        "org_b": org_b,
        "teacher_a": teacher_a,
        "teacher_b": teacher_b,
        "student_a": student_a,
        "student_b": student_b,
    }


@pytest.fixture
def rubrics(db, two_orgs):
    ra = Rubric.objects.create(
        org=two_orgs["org_a"],
        owner=two_orgs["teacher_a"],
        name="Rubric A",
        criteria=[
            {
                "id": "readability",
                "name": "Readability",
                "weight": 1.0,
                "levels": [
                    {"score": 1, "description": "bad"},
                    {"score": 4, "description": "good"},
                ],
            }
        ],
    )
    rb = Rubric.objects.create(
        org=two_orgs["org_b"],
        owner=two_orgs["teacher_b"],
        name="Rubric B",
        criteria=[
            {
                "id": "readability",
                "name": "Readability",
                "weight": 1.0,
                "levels": [
                    {"score": 1, "description": "bad"},
                    {"score": 4, "description": "good"},
                ],
            }
        ],
    )
    return {"a": ra, "b": rb}


@pytest.fixture
def classrooms(db, two_orgs, rubrics):
    ca = Classroom.objects.create(
        org=two_orgs["org_a"],
        owner=two_orgs["teacher_a"],
        name="Class A",
        rubric=rubrics["a"],
    )
    cb = Classroom.objects.create(
        org=two_orgs["org_b"],
        owner=two_orgs["teacher_b"],
        name="Class B",
        rubric=rubrics["b"],
    )
    return {"a": ca, "b": cb}


@pytest.fixture
def sessions(db, two_orgs, rubrics, classrooms):
    sub_a = Submission.objects.create(
        org=two_orgs["org_a"],
        classroom=classrooms["a"],
        student=two_orgs["student_a"],
        repo_full_name="student_a/repo",
        pr_number=1,
        pr_url="https://github.com/student_a/repo/pull/1",
        head_branch="feature",
    )
    sub_b = Submission.objects.create(
        org=two_orgs["org_b"],
        classroom=classrooms["b"],
        student=two_orgs["student_b"],
        repo_full_name="student_b/repo",
        pr_number=1,
        pr_url="https://github.com/student_b/repo/pull/1",
        head_branch="feature",
    )
    sa = GradingSession.objects.create(
        org=two_orgs["org_a"], submission=sub_a, rubric=rubrics["a"]
    )
    sb = GradingSession.objects.create(
        org=two_orgs["org_b"], submission=sub_b, rubric=rubrics["b"]
    )
    return {"a": sa, "b": sb, "sub_a": sub_a, "sub_b": sub_b}


@pytest.fixture
def client_a(two_orgs):
    c = APIClient()
    c.force_authenticate(user=two_orgs["teacher_a"])
    return c


@pytest.fixture
def client_b(two_orgs):
    c = APIClient()
    c.force_authenticate(user=two_orgs["teacher_b"])
    return c


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestRubricIsolation:
    def test_teacher_a_cannot_list_org_b_rubrics(self, client_a, rubrics):
        resp = client_a.get("/api/grading/rubrics/")
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json().get("results", resp.json())]
        assert rubrics["a"].id in ids
        assert rubrics["b"].id not in ids

    def test_teacher_a_cannot_retrieve_org_b_rubric(self, client_a, rubrics):
        resp = client_a.get(f"/api/grading/rubrics/{rubrics['b'].id}/")
        assert resp.status_code == 404  # not 403 — don't leak existence

    def test_teacher_a_cannot_update_org_b_rubric(self, client_a, rubrics):
        resp = client_a.patch(
            f"/api/grading/rubrics/{rubrics['b'].id}/",
            {"name": "pwned"},
            format="json",
        )
        assert resp.status_code == 404


@pytest.mark.django_db
class TestClassroomIsolation:
    def test_teacher_a_cannot_list_org_b_classrooms(self, client_a, classrooms):
        resp = client_a.get("/api/grading/classrooms/")
        assert resp.status_code == 200
        ids = [c["id"] for c in resp.json().get("results", resp.json())]
        assert classrooms["a"].id in ids
        assert classrooms["b"].id not in ids

    def test_teacher_a_cannot_retrieve_org_b_classroom(self, client_a, classrooms):
        resp = client_a.get(f"/api/grading/classrooms/{classrooms['b'].id}/")
        assert resp.status_code == 404

    def test_teacher_a_cannot_add_member_to_org_b_classroom(self, client_a, classrooms, two_orgs):
        resp = client_a.post(
            f"/api/grading/classrooms/{classrooms['b'].id}/members/",
            {"student_id": two_orgs["student_a"].id},
            format="json",
        )
        assert resp.status_code == 404


@pytest.mark.django_db
class TestGradingSessionIsolation:
    def test_teacher_a_cannot_list_org_b_sessions(self, client_a, sessions):
        resp = client_a.get("/api/grading/sessions/")
        assert resp.status_code == 200
        ids = [s["id"] for s in resp.json().get("results", resp.json())]
        assert sessions["a"].id in ids
        assert sessions["b"].id not in ids

    def test_teacher_a_cannot_retrieve_org_b_session(self, client_a, sessions):
        resp = client_a.get(f"/api/grading/sessions/{sessions['b'].id}/")
        assert resp.status_code == 404

    def test_teacher_a_cannot_send_org_b_session(self, client_a, sessions):
        resp = client_a.post(f"/api/grading/sessions/{sessions['b'].id}/send/")
        assert resp.status_code == 404

    def test_teacher_a_cannot_resume_org_b_session(self, client_a, sessions):
        resp = client_a.post(f"/api/grading/sessions/{sessions['b'].id}/resume/")
        assert resp.status_code == 404

    def test_teacher_a_cannot_start_review_on_org_b_session(self, client_a, sessions):
        resp = client_a.post(f"/api/grading/sessions/{sessions['b'].id}/start_review/")
        assert resp.status_code == 404


@pytest.mark.django_db
class TestSubmissionIsolation:
    def test_teacher_a_cannot_list_org_b_submissions(self, client_a, sessions):
        resp = client_a.get("/api/grading/submissions/")
        assert resp.status_code == 200
        ids = [s["id"] for s in resp.json().get("results", resp.json())]
        assert sessions["sub_a"].id in ids
        assert sessions["sub_b"].id not in ids

    def test_teacher_a_cannot_retrieve_org_b_submission(self, client_a, sessions):
        resp = client_a.get(f"/api/grading/submissions/{sessions['sub_b'].id}/")
        assert resp.status_code == 404


@pytest.mark.django_db
class TestUnauthenticatedAccess:
    def test_anonymous_cannot_list_rubrics(self, db):
        c = APIClient()
        resp = c.get("/api/grading/rubrics/")
        assert resp.status_code == 401

    def test_anonymous_cannot_list_sessions(self, db):
        c = APIClient()
        resp = c.get("/api/grading/sessions/")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestStudentRoleRestriction:
    def test_student_cannot_create_rubric(self, two_orgs):
        c = APIClient()
        c.force_authenticate(user=two_orgs["student_a"])
        resp = c.post(
            "/api/grading/rubrics/",
            {
                "name": "Smuggled",
                "criteria": [
                    {
                        "id": "x",
                        "name": "X",
                        "weight": 1,
                        "levels": [{"score": 1}, {"score": 2}],
                    }
                ],
            },
            format="json",
        )
        assert resp.status_code == 403

    def test_student_cannot_create_classroom(self, two_orgs):
        c = APIClient()
        c.force_authenticate(user=two_orgs["student_a"])
        resp = c.post("/api/grading/classrooms/", {"name": "Smuggled"}, format="json")
        assert resp.status_code == 403
