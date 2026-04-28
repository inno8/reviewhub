"""
Tests for CohortTeacher CRUD endpoints:
  GET    /api/grading/cohorts/{id}/teachers/            — list teachers
  POST   /api/grading/cohorts/{id}/teachers/            — add teacher (admin)
  DELETE /api/grading/cohorts/{id}/teachers/{aid}/      — remove teacher (admin)

Multi-teacher-per-cohort (bucket 4) — decouples teacher assignment from
Course ownership so an admin can pre-populate teachers before courses exist.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from grading.models import Cohort, CohortTeacher

User = get_user_model()


@pytest.fixture
def scaffold(db):
    from users.models import Organization

    org_a = Organization.objects.create(name="Org A CT", slug="org-a-ct")
    org_b = Organization.objects.create(name="Org B CT", slug="org-b-ct")

    admin_a = User.objects.create_user(
        username="admin_a_ct", email="admin_a_ct@ex.com", password="pw",
        role="admin", organization=org_a,
    )
    teacher_a = User.objects.create_user(
        username="teacher_a_ct", email="teacher_a_ct@ex.com", password="pw",
        role="teacher", organization=org_a,
    )
    teacher_a2 = User.objects.create_user(
        username="teacher_a2_ct", email="teacher_a2_ct@ex.com", password="pw",
        role="teacher", organization=org_a,
    )
    student_a = User.objects.create_user(
        username="student_a_ct", email="student_a_ct@ex.com", password="pw",
        role="developer", organization=org_a,
    )
    teacher_b = User.objects.create_user(
        username="teacher_b_ct", email="teacher_b_ct@ex.com", password="pw",
        role="teacher", organization=org_b,
    )
    cohort_a = Cohort.objects.create(org=org_a, name="Klas A")
    return {
        "org_a": org_a, "org_b": org_b,
        "admin_a": admin_a,
        "teacher_a": teacher_a, "teacher_a2": teacher_a2,
        "student_a": student_a,
        "teacher_b": teacher_b,
        "cohort_a": cohort_a,
    }


def _client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.mark.django_db
class TestCohortTeachersList:
    def test_admin_can_list_teachers(self, scaffold):
        CohortTeacher.objects.create(
            cohort=scaffold["cohort_a"], teacher=scaffold["teacher_a"],
        )
        c = _client(scaffold["admin_a"])
        resp = c.get(f"/api/grading/cohorts/{scaffold['cohort_a'].id}/teachers/")
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert len(body) == 1
        assert body[0]["teacher"] == scaffold["teacher_a"].id
        assert body[0]["teacher_email"] == "teacher_a_ct@ex.com"

    def test_assigned_teacher_can_list_teachers(self, scaffold):
        """A teacher assigned to the cohort sees the roster (cohort is in their
        visible queryset because of the teacher_assignments filter)."""
        CohortTeacher.objects.create(
            cohort=scaffold["cohort_a"], teacher=scaffold["teacher_a"],
        )
        c = _client(scaffold["teacher_a"])
        resp = c.get(f"/api/grading/cohorts/{scaffold['cohort_a'].id}/teachers/")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestCohortTeachersAdd:
    def test_admin_can_add_teacher(self, scaffold):
        c = _client(scaffold["admin_a"])
        resp = c.post(
            f"/api/grading/cohorts/{scaffold['cohort_a'].id}/teachers/",
            {"teacher_id": scaffold["teacher_a"].id},
            format="json",
        )
        assert resp.status_code == 201, resp.content
        assert CohortTeacher.objects.filter(
            cohort=scaffold["cohort_a"], teacher=scaffold["teacher_a"]
        ).exists()

    def test_admin_add_teacher_is_idempotent(self, scaffold):
        """Second POST with same teacher returns 200 (not 201) and does not
        create a duplicate row (get_or_create semantics)."""
        c = _client(scaffold["admin_a"])
        url = f"/api/grading/cohorts/{scaffold['cohort_a'].id}/teachers/"
        r1 = c.post(url, {"teacher_id": scaffold["teacher_a"].id}, format="json")
        assert r1.status_code == 201
        r2 = c.post(url, {"teacher_id": scaffold["teacher_a"].id}, format="json")
        assert r2.status_code == 200
        assert CohortTeacher.objects.filter(
            cohort=scaffold["cohort_a"], teacher=scaffold["teacher_a"]
        ).count() == 1

    def test_teacher_cannot_add_teacher(self, scaffold):
        # teacher_a, even if assigned to the cohort, cannot POST.
        CohortTeacher.objects.create(
            cohort=scaffold["cohort_a"], teacher=scaffold["teacher_a"],
        )
        c = _client(scaffold["teacher_a"])
        resp = c.post(
            f"/api/grading/cohorts/{scaffold['cohort_a'].id}/teachers/",
            {"teacher_id": scaffold["teacher_a2"].id},
            format="json",
        )
        assert resp.status_code == 403

    def test_cross_org_teacher_rejected(self, scaffold):
        c = _client(scaffold["admin_a"])
        resp = c.post(
            f"/api/grading/cohorts/{scaffold['cohort_a'].id}/teachers/",
            {"teacher_id": scaffold["teacher_b"].id},
            format="json",
        )
        # teacher_b is in org_b — admin_a cannot cross orgs
        assert resp.status_code in (400, 403)
        assert not CohortTeacher.objects.filter(
            teacher=scaffold["teacher_b"]
        ).exists()

    def test_non_teacher_role_rejected(self, scaffold):
        c = _client(scaffold["admin_a"])
        resp = c.post(
            f"/api/grading/cohorts/{scaffold['cohort_a'].id}/teachers/",
            {"teacher_id": scaffold["student_a"].id},
            format="json",
        )
        assert resp.status_code == 400
        assert not CohortTeacher.objects.filter(
            teacher=scaffold["student_a"]
        ).exists()


@pytest.mark.django_db
class TestCohortTeachersRemove:
    def test_admin_can_remove_teacher(self, scaffold):
        ct = CohortTeacher.objects.create(
            cohort=scaffold["cohort_a"], teacher=scaffold["teacher_a"],
        )
        c = _client(scaffold["admin_a"])
        resp = c.delete(
            f"/api/grading/cohorts/{scaffold['cohort_a'].id}/teachers/{ct.id}/"
        )
        assert resp.status_code == 204
        assert not CohortTeacher.objects.filter(pk=ct.id).exists()

    def test_teacher_cannot_remove_teacher(self, scaffold):
        ct = CohortTeacher.objects.create(
            cohort=scaffold["cohort_a"], teacher=scaffold["teacher_a"],
        )
        c = _client(scaffold["teacher_a"])
        resp = c.delete(
            f"/api/grading/cohorts/{scaffold['cohort_a'].id}/teachers/{ct.id}/"
        )
        assert resp.status_code == 403
        assert CohortTeacher.objects.filter(pk=ct.id).exists()
