"""
Scope B1 / Workstream C — Course lifecycle endpoint tests.

Covers:
  - Teacher can create course in cohort they teach, 403 in unrelated cohort
  - Teacher can update only their own courses, 404 on others
  - Admin can reassign course owner, teacher cannot
  - Admin archive works, non-admin blocked appropriately
  - Cross-org 404 on all endpoints
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from grading.models import Cohort, Course, Rubric

User = get_user_model()


@pytest.fixture
def scaffold(db):
    from users.models import Organization

    org_a = Organization.objects.create(name="Org A CL", slug="org-a-cl")
    org_b = Organization.objects.create(name="Org B CL", slug="org-b-cl")

    admin_a = User.objects.create_user(
        username="admin_a_cl", email="admin_a_cl@ex.com", password="pw",
        role="admin", organization=org_a,
    )
    teacher_a = User.objects.create_user(
        username="teacher_a_cl", email="teacher_a_cl@ex.com", password="pw",
        role="teacher", organization=org_a,
    )
    teacher_a2 = User.objects.create_user(
        username="teacher_a2_cl", email="teacher_a2_cl@ex.com", password="pw",
        role="teacher", organization=org_a,
    )
    student_a = User.objects.create_user(
        username="student_a_cl", email="student_a_cl@ex.com", password="pw",
        role="developer", organization=org_a,
    )
    teacher_b = User.objects.create_user(
        username="teacher_b_cl", email="teacher_b_cl@ex.com", password="pw",
        role="teacher", organization=org_b,
    )

    return {
        "org_a": org_a, "org_b": org_b,
        "admin_a": admin_a,
        "teacher_a": teacher_a, "teacher_a2": teacher_a2, "teacher_b": teacher_b,
        "student_a": student_a,
    }


def _client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


# ─────────────────────────────────────────────────────────────────────────────
# Course create rules
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestCourseCreate:
    def test_admin_can_create_course_in_any_cohort(self, scaffold):
        cohort = Cohort.objects.create(org=scaffold["org_a"], name="K")
        c = _client(scaffold["admin_a"])
        resp = c.post(
            "/api/grading/courses/",
            {
                "name": "Frontend",
                "cohort": cohort.id,
                "owner": scaffold["teacher_a"].id,
            },
            format="json",
        )
        assert resp.status_code == 201, resp.json()
        body = resp.json()
        assert body["owner"] == scaffold["teacher_a"].id

    def test_teacher_can_create_course_in_empty_cohort_as_self_owner(self, scaffold):
        cohort = Cohort.objects.create(org=scaffold["org_a"], name="K")
        c = _client(scaffold["teacher_a"])
        resp = c.post(
            "/api/grading/courses/",
            {"name": "Frontend", "cohort": cohort.id},
            format="json",
        )
        assert resp.status_code == 201, resp.json()
        assert resp.json()["owner"] == scaffold["teacher_a"].id

    def test_teacher_cannot_create_course_in_unrelated_cohort(self, scaffold):
        cohort = Cohort.objects.create(org=scaffold["org_a"], name="K")
        # Cohort already has a course owned by teacher_a2 — teacher_a does not teach here.
        Course.objects.create(
            org=scaffold["org_a"], cohort=cohort,
            owner=scaffold["teacher_a2"], name="Backend",
        )
        c = _client(scaffold["teacher_a"])
        resp = c.post(
            "/api/grading/courses/",
            {"name": "Sneaky", "cohort": cohort.id},
            format="json",
        )
        assert resp.status_code == 403

    def test_teacher_cannot_set_another_teacher_as_owner(self, scaffold):
        cohort = Cohort.objects.create(org=scaffold["org_a"], name="K")
        c = _client(scaffold["teacher_a"])
        resp = c.post(
            "/api/grading/courses/",
            {
                "name": "ForSomeoneElse",
                "cohort": cohort.id,
                "owner": scaffold["teacher_a2"].id,
            },
            format="json",
        )
        assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# Course update / archive rules
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestCourseUpdate:
    def test_teacher_can_update_own_course(self, scaffold):
        cohort = Cohort.objects.create(org=scaffold["org_a"], name="K")
        course = Course.objects.create(
            org=scaffold["org_a"], cohort=cohort,
            owner=scaffold["teacher_a"], name="Frontend",
        )
        c = _client(scaffold["teacher_a"])
        resp = c.patch(
            f"/api/grading/courses/{course.id}/",
            {"name": "Renamed"},
            format="json",
        )
        assert resp.status_code == 200, resp.json()
        course.refresh_from_db()
        assert course.name == "Renamed"

    def test_teacher_gets_404_on_other_teachers_course(self, scaffold):
        """
        Per existing cross-org pattern: missing/unauthorized resource returns
        404, not 403. Here teacher_a2 owns a course in a cohort where
        teacher_a does not teach, so get_queryset filters it out.
        """
        cohort = Cohort.objects.create(org=scaffold["org_a"], name="K")
        course = Course.objects.create(
            org=scaffold["org_a"], cohort=cohort,
            owner=scaffold["teacher_a2"], name="OwnedBy2",
        )
        c = _client(scaffold["teacher_a"])
        resp = c.patch(
            f"/api/grading/courses/{course.id}/",
            {"name": "Steal"},
            format="json",
        )
        assert resp.status_code == 404

    def test_teacher_cannot_update_course_they_only_see_via_cohort(self, scaffold):
        """
        Teacher A teaches course X in cohort K. Teacher A2 owns course Y in same
        cohort K. Teacher A can SEE course Y (cohort sibling) but cannot update
        it (IsCourseOwnerOrAdmin 403).
        """
        cohort = Cohort.objects.create(org=scaffold["org_a"], name="K")
        Course.objects.create(
            org=scaffold["org_a"], cohort=cohort,
            owner=scaffold["teacher_a"], name="Mine",
        )
        their_course = Course.objects.create(
            org=scaffold["org_a"], cohort=cohort,
            owner=scaffold["teacher_a2"], name="Theirs",
        )
        c = _client(scaffold["teacher_a"])
        # sanity: retrieve works
        resp = c.get(f"/api/grading/courses/{their_course.id}/")
        assert resp.status_code == 200
        # update refused
        resp = c.patch(
            f"/api/grading/courses/{their_course.id}/",
            {"name": "Steal"},
            format="json",
        )
        assert resp.status_code == 403

    def test_admin_can_archive_course(self, scaffold):
        cohort = Cohort.objects.create(org=scaffold["org_a"], name="K")
        course = Course.objects.create(
            org=scaffold["org_a"], cohort=cohort,
            owner=scaffold["teacher_a"], name="Frontend",
        )
        c = _client(scaffold["admin_a"])
        resp = c.post(f"/api/grading/courses/{course.id}/archive/")
        assert resp.status_code == 200, resp.json()
        course.refresh_from_db()
        assert course.archived_at is not None

    def test_hard_delete_disabled(self, scaffold):
        cohort = Cohort.objects.create(org=scaffold["org_a"], name="K")
        course = Course.objects.create(
            org=scaffold["org_a"], cohort=cohort,
            owner=scaffold["teacher_a"], name="Frontend",
        )
        c = _client(scaffold["admin_a"])
        resp = c.delete(f"/api/grading/courses/{course.id}/")
        assert resp.status_code == 405


# ─────────────────────────────────────────────────────────────────────────────
# Reassign
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestCourseReassign:
    def test_admin_can_reassign_owner(self, scaffold):
        cohort = Cohort.objects.create(org=scaffold["org_a"], name="K")
        course = Course.objects.create(
            org=scaffold["org_a"], cohort=cohort,
            owner=scaffold["teacher_a"], name="Frontend",
        )
        c = _client(scaffold["admin_a"])
        resp = c.post(
            f"/api/grading/courses/{course.id}/reassign/",
            {"new_owner_id": scaffold["teacher_a2"].id},
            format="json",
        )
        assert resp.status_code == 200, resp.json()
        course.refresh_from_db()
        assert course.owner_id == scaffold["teacher_a2"].id

    def test_teacher_cannot_reassign(self, scaffold):
        cohort = Cohort.objects.create(org=scaffold["org_a"], name="K")
        course = Course.objects.create(
            org=scaffold["org_a"], cohort=cohort,
            owner=scaffold["teacher_a"], name="Frontend",
        )
        c = _client(scaffold["teacher_a"])
        resp = c.post(
            f"/api/grading/courses/{course.id}/reassign/",
            {"new_owner_id": scaffold["teacher_a2"].id},
            format="json",
        )
        assert resp.status_code == 403

    def test_reassign_rejects_cross_org_user(self, scaffold):
        cohort = Cohort.objects.create(org=scaffold["org_a"], name="K")
        course = Course.objects.create(
            org=scaffold["org_a"], cohort=cohort,
            owner=scaffold["teacher_a"], name="Frontend",
        )
        c = _client(scaffold["admin_a"])
        resp = c.post(
            f"/api/grading/courses/{course.id}/reassign/",
            {"new_owner_id": scaffold["teacher_b"].id},
            format="json",
        )
        assert resp.status_code == 400
        course.refresh_from_db()
        assert course.owner_id == scaffold["teacher_a"].id

    def test_reassign_rejects_non_teacher(self, scaffold):
        cohort = Cohort.objects.create(org=scaffold["org_a"], name="K")
        course = Course.objects.create(
            org=scaffold["org_a"], cohort=cohort,
            owner=scaffold["teacher_a"], name="Frontend",
        )
        c = _client(scaffold["admin_a"])
        resp = c.post(
            f"/api/grading/courses/{course.id}/reassign/",
            {"new_owner_id": scaffold["student_a"].id},
            format="json",
        )
        assert resp.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# Cross-org isolation
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestCourseCrossOrgIsolation:
    def test_admin_a_cannot_retrieve_org_b_course(self, scaffold):
        cb = Cohort.objects.create(org=scaffold["org_b"], name="B")
        course_b = Course.objects.create(
            org=scaffold["org_b"], cohort=cb,
            owner=scaffold["teacher_b"], name="B course",
        )
        c = _client(scaffold["admin_a"])
        resp = c.get(f"/api/grading/courses/{course_b.id}/")
        assert resp.status_code == 404

    def test_admin_a_cannot_reassign_org_b_course(self, scaffold):
        cb = Cohort.objects.create(org=scaffold["org_b"], name="B")
        course_b = Course.objects.create(
            org=scaffold["org_b"], cohort=cb,
            owner=scaffold["teacher_b"], name="B course",
        )
        c = _client(scaffold["admin_a"])
        resp = c.post(
            f"/api/grading/courses/{course_b.id}/reassign/",
            {"new_owner_id": scaffold["teacher_a"].id},
            format="json",
        )
        assert resp.status_code == 404
