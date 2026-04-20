"""
Scope B1 / Workstream C — Cohort lifecycle endpoint tests.

Covers:
  - Admin CRUD (create, patch, archive)
  - Non-admin (teacher/student) cannot mutate cohorts (403)
  - Teacher read visibility (own cohorts only)
  - Cohort membership add/remove with uniqueness guard
  - Cross-org 404 on all endpoints
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from grading.models import Cohort, CohortMembership, Course, Rubric

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def scaffold(db):
    from users.models import Organization

    org_a = Organization.objects.create(name="Org A WC", slug="org-a-wc")
    org_b = Organization.objects.create(name="Org B WC", slug="org-b-wc")

    admin_a = User.objects.create_user(
        username="admin_a_wc", email="admin_a_wc@ex.com", password="pw",
        role="admin", organization=org_a,
    )
    teacher_a = User.objects.create_user(
        username="teacher_a_wc", email="teacher_a_wc@ex.com", password="pw",
        role="teacher", organization=org_a,
    )
    teacher_a2 = User.objects.create_user(
        username="teacher_a2_wc", email="teacher_a2_wc@ex.com", password="pw",
        role="teacher", organization=org_a,
    )
    student_a = User.objects.create_user(
        username="student_a_wc", email="student_a_wc@ex.com", password="pw",
        role="developer", organization=org_a,
    )
    student_a2 = User.objects.create_user(
        username="student_a2_wc", email="student_a2_wc@ex.com", password="pw",
        role="developer", organization=org_a,
    )
    admin_b = User.objects.create_user(
        username="admin_b_wc", email="admin_b_wc@ex.com", password="pw",
        role="admin", organization=org_b,
    )
    teacher_b = User.objects.create_user(
        username="teacher_b_wc", email="teacher_b_wc@ex.com", password="pw",
        role="teacher", organization=org_b,
    )

    return {
        "org_a": org_a, "org_b": org_b,
        "admin_a": admin_a, "admin_b": admin_b,
        "teacher_a": teacher_a, "teacher_a2": teacher_a2, "teacher_b": teacher_b,
        "student_a": student_a, "student_a2": student_a2,
    }


def _client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


# ─────────────────────────────────────────────────────────────────────────────
# Admin write path
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestCohortAdminWrite:
    def test_admin_can_create_cohort(self, scaffold):
        c = _client(scaffold["admin_a"])
        resp = c.post(
            "/api/grading/cohorts/",
            {"name": "Klas 2A", "year": "2026-2027"},
            format="json",
        )
        assert resp.status_code == 201, resp.json()
        body = resp.json()
        assert body["name"] == "Klas 2A"
        # Cohort lands in admin's org via perform_create
        assert Cohort.objects.get(pk=body["id"]).org_id == scaffold["org_a"].id

    def test_admin_can_patch_cohort(self, scaffold):
        cohort = Cohort.objects.create(org=scaffold["org_a"], name="Orig")
        c = _client(scaffold["admin_a"])
        resp = c.patch(
            f"/api/grading/cohorts/{cohort.id}/",
            {"name": "Renamed"},
            format="json",
        )
        assert resp.status_code == 200, resp.json()
        cohort.refresh_from_db()
        assert cohort.name == "Renamed"

    def test_admin_can_archive_cohort(self, scaffold):
        cohort = Cohort.objects.create(org=scaffold["org_a"], name="Archive me")
        c = _client(scaffold["admin_a"])
        resp = c.post(f"/api/grading/cohorts/{cohort.id}/archive/")
        assert resp.status_code == 200, resp.json()
        cohort.refresh_from_db()
        assert cohort.archived_at is not None

    def test_archived_cohorts_hidden_from_default_list(self, scaffold):
        Cohort.objects.create(org=scaffold["org_a"], name="Active")
        arch = Cohort.objects.create(org=scaffold["org_a"], name="Archived")
        arch.archived_at = arch.created_at
        arch.save(update_fields=["archived_at"])
        c = _client(scaffold["admin_a"])
        resp = c.get("/api/grading/cohorts/")
        assert resp.status_code == 200
        names = [r["name"] for r in resp.json().get("results", resp.json())]
        assert "Active" in names
        assert "Archived" not in names

    def test_hard_delete_disabled(self, scaffold):
        cohort = Cohort.objects.create(org=scaffold["org_a"], name="NoDelete")
        c = _client(scaffold["admin_a"])
        resp = c.delete(f"/api/grading/cohorts/{cohort.id}/")
        assert resp.status_code == 405


# ─────────────────────────────────────────────────────────────────────────────
# Non-admin cannot write
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestCohortNonAdminCannotWrite:
    def test_teacher_cannot_create_cohort(self, scaffold):
        c = _client(scaffold["teacher_a"])
        resp = c.post("/api/grading/cohorts/", {"name": "Hacky"}, format="json")
        assert resp.status_code == 403

    def test_teacher_cannot_archive_cohort(self, scaffold):
        cohort = Cohort.objects.create(org=scaffold["org_a"], name="K")
        # give teacher a course so they can SEE the cohort; the archive should
        # still be refused for role reasons.
        Course.objects.create(
            org=scaffold["org_a"], cohort=cohort,
            owner=scaffold["teacher_a"], name="Frontend",
        )
        c = _client(scaffold["teacher_a"])
        resp = c.post(f"/api/grading/cohorts/{cohort.id}/archive/")
        assert resp.status_code == 403

    def test_student_cannot_create_cohort(self, scaffold):
        c = _client(scaffold["student_a"])
        resp = c.post("/api/grading/cohorts/", {"name": "Hacky"}, format="json")
        assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# Teacher + student read visibility
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestCohortVisibility:
    def test_teacher_sees_only_cohorts_they_teach(self, scaffold):
        mine = Cohort.objects.create(org=scaffold["org_a"], name="Mine")
        other = Cohort.objects.create(org=scaffold["org_a"], name="Other")
        Course.objects.create(
            org=scaffold["org_a"], cohort=mine,
            owner=scaffold["teacher_a"], name="Taught",
        )
        # "other" has a course owned by teacher_a2, not teacher_a
        Course.objects.create(
            org=scaffold["org_a"], cohort=other,
            owner=scaffold["teacher_a2"], name="Other Course",
        )
        c = _client(scaffold["teacher_a"])
        resp = c.get("/api/grading/cohorts/")
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json().get("results", resp.json())]
        assert mine.id in ids
        assert other.id not in ids

    def test_student_sees_only_own_cohort(self, scaffold):
        mine = Cohort.objects.create(org=scaffold["org_a"], name="MyKlas")
        other = Cohort.objects.create(org=scaffold["org_a"], name="OtherKlas")
        CohortMembership.objects.create(cohort=mine, student=scaffold["student_a"])
        c = _client(scaffold["student_a"])
        resp = c.get("/api/grading/cohorts/")
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json().get("results", resp.json())]
        assert ids == [mine.id]
        assert other.id not in ids


# ─────────────────────────────────────────────────────────────────────────────
# Membership add/remove
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestCohortMembership:
    def test_admin_can_add_student(self, scaffold):
        cohort = Cohort.objects.create(org=scaffold["org_a"], name="K")
        c = _client(scaffold["admin_a"])
        resp = c.post(
            f"/api/grading/cohorts/{cohort.id}/members/",
            {"student_id": scaffold["student_a"].id, "student_repo_url": "https://gh/x"},
            format="json",
        )
        assert resp.status_code == 201, resp.json()
        assert CohortMembership.objects.filter(
            cohort=cohort, student=scaffold["student_a"]
        ).exists()

    def test_adding_same_student_to_second_cohort_returns_400(self, scaffold):
        k1 = Cohort.objects.create(org=scaffold["org_a"], name="K1")
        k2 = Cohort.objects.create(org=scaffold["org_a"], name="K2")
        CohortMembership.objects.create(cohort=k1, student=scaffold["student_a"])

        c = _client(scaffold["admin_a"])
        resp = c.post(
            f"/api/grading/cohorts/{k2.id}/members/",
            {"student_id": scaffold["student_a"].id},
            format="json",
        )
        assert resp.status_code == 400
        body = resp.json()
        # error message mentions the existing cohort so the admin knows where
        # to look.
        joined = str(body)
        assert "already enrolled" in joined
        assert "K1" in joined

    def test_teacher_cannot_add_student(self, scaffold):
        cohort = Cohort.objects.create(org=scaffold["org_a"], name="K")
        Course.objects.create(
            org=scaffold["org_a"], cohort=cohort,
            owner=scaffold["teacher_a"], name="Frontend",
        )
        c = _client(scaffold["teacher_a"])
        resp = c.post(
            f"/api/grading/cohorts/{cohort.id}/members/",
            {"student_id": scaffold["student_a"].id},
            format="json",
        )
        assert resp.status_code == 403

    def test_admin_can_soft_remove_student(self, scaffold):
        cohort = Cohort.objects.create(org=scaffold["org_a"], name="K")
        m = CohortMembership.objects.create(
            cohort=cohort, student=scaffold["student_a"],
        )
        c = _client(scaffold["admin_a"])
        resp = c.delete(f"/api/grading/cohorts/{cohort.id}/members/{m.id}/")
        assert resp.status_code == 204
        m.refresh_from_db()
        assert m.removed_at is not None
        # Soft-delete: row still exists
        assert CohortMembership.objects.filter(pk=m.id).exists()

    def test_teacher_cannot_remove_student(self, scaffold):
        cohort = Cohort.objects.create(org=scaffold["org_a"], name="K")
        Course.objects.create(
            org=scaffold["org_a"], cohort=cohort,
            owner=scaffold["teacher_a"], name="Frontend",
        )
        m = CohortMembership.objects.create(
            cohort=cohort, student=scaffold["student_a"],
        )
        c = _client(scaffold["teacher_a"])
        resp = c.delete(f"/api/grading/cohorts/{cohort.id}/members/{m.id}/")
        assert resp.status_code == 403

    def test_member_list_visible_to_admin_and_cohort_teacher(self, scaffold):
        cohort = Cohort.objects.create(org=scaffold["org_a"], name="K")
        Course.objects.create(
            org=scaffold["org_a"], cohort=cohort,
            owner=scaffold["teacher_a"], name="Frontend",
        )
        CohortMembership.objects.create(cohort=cohort, student=scaffold["student_a"])
        CohortMembership.objects.create(cohort=cohort, student=scaffold["student_a2"])

        for user in (scaffold["admin_a"], scaffold["teacher_a"]):
            c = _client(user)
            resp = c.get(f"/api/grading/cohorts/{cohort.id}/members/")
            assert resp.status_code == 200, (user.role, resp.json())
            assert len(resp.json()) == 2


# ─────────────────────────────────────────────────────────────────────────────
# Cross-org isolation
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestCohortCrossOrgIsolation:
    def test_admin_a_cannot_retrieve_org_b_cohort(self, scaffold):
        cb = Cohort.objects.create(org=scaffold["org_b"], name="B")
        c = _client(scaffold["admin_a"])
        resp = c.get(f"/api/grading/cohorts/{cb.id}/")
        assert resp.status_code == 404

    def test_admin_a_cannot_patch_org_b_cohort(self, scaffold):
        cb = Cohort.objects.create(org=scaffold["org_b"], name="B")
        c = _client(scaffold["admin_a"])
        resp = c.patch(
            f"/api/grading/cohorts/{cb.id}/", {"name": "pwned"}, format="json"
        )
        assert resp.status_code == 404

    def test_admin_a_cannot_archive_org_b_cohort(self, scaffold):
        cb = Cohort.objects.create(org=scaffold["org_b"], name="B")
        c = _client(scaffold["admin_a"])
        resp = c.post(f"/api/grading/cohorts/{cb.id}/archive/")
        assert resp.status_code == 404

    def test_admin_a_cannot_add_member_to_org_b_cohort(self, scaffold):
        cb = Cohort.objects.create(org=scaffold["org_b"], name="B")
        c = _client(scaffold["admin_a"])
        resp = c.post(
            f"/api/grading/cohorts/{cb.id}/members/",
            {"student_id": scaffold["student_a"].id},
            format="json",
        )
        assert resp.status_code == 404
