"""
Tests for TeacherStudentListView — GET /api/grading/students/.

Covers:
  - Teacher sees only students in cohorts they teach (org-scoped)
  - Cross-org teacher does not see another org's students
  - Teacher in the same org but not teaching a given cohort does not see
    its students
  - Admin sees all students in their org
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from grading.models import Cohort, CohortMembership, Course, Rubric

User = get_user_model()

URL = "/api/grading/students/"


@pytest.fixture
def two_orgs(db):
    from users.models import Organization

    return {
        "a": Organization.objects.create(name="Stu List A", slug="stu-list-a"),
        "b": Organization.objects.create(name="Stu List B", slug="stu-list-b"),
    }


@pytest.fixture
def users_set(db, two_orgs):
    return {
        "admin_a": User.objects.create_user(
            username="admin_stu_a", email="admin_stu_a@x.com", password="p",
            role="admin", organization=two_orgs["a"],
        ),
        "teacher_in": User.objects.create_user(
            username="teacher_in_stu", email="tin_stu@x.com", password="p",
            role="teacher", organization=two_orgs["a"],
        ),
        "teacher_out": User.objects.create_user(
            username="teacher_out_stu", email="tout_stu@x.com", password="p",
            role="teacher", organization=two_orgs["a"],
        ),
        "teacher_b": User.objects.create_user(
            username="teacher_b_stu", email="tb_stu@x.com", password="p",
            role="teacher", organization=two_orgs["b"],
        ),
        "s1": User.objects.create_user(
            username="s1_stu", email="s1_stu@x.com", password="p",
            role="developer", organization=two_orgs["a"],
        ),
        "s2": User.objects.create_user(
            username="s2_stu", email="s2_stu@x.com", password="p",
            role="developer", organization=two_orgs["a"],
        ),
        "s_other_cohort": User.objects.create_user(
            username="s_other_stu", email="s_other_stu@x.com", password="p",
            role="developer", organization=two_orgs["a"],
        ),
        "s_in_b": User.objects.create_user(
            username="s_in_b_stu", email="s_in_b_stu@x.com", password="p",
            role="developer", organization=two_orgs["b"],
        ),
    }


@pytest.fixture
def rubric_a(db, two_orgs, users_set):
    return Rubric.objects.create(
        org=two_orgs["a"],
        owner=users_set["teacher_in"],
        name="R Stu A",
        criteria=[],
    )


@pytest.fixture
def cohort_setup(db, two_orgs, users_set, rubric_a):
    cohort_a = Cohort.objects.create(org=two_orgs["a"], name="Stu Cohort A")
    cohort_other = Cohort.objects.create(org=two_orgs["a"], name="Stu Other Cohort")
    cohort_b = Cohort.objects.create(org=two_orgs["b"], name="Stu Cohort B")

    # teacher_in owns a Course in cohort_a only (not cohort_other)
    Course.objects.create(
        org=two_orgs["a"], cohort=cohort_a, owner=users_set["teacher_in"],
        name="Stu Course A", rubric=rubric_a,
    )

    CohortMembership.objects.create(cohort=cohort_a, student=users_set["s1"])
    CohortMembership.objects.create(cohort=cohort_a, student=users_set["s2"])
    CohortMembership.objects.create(
        cohort=cohort_other, student=users_set["s_other_cohort"],
    )
    CohortMembership.objects.create(cohort=cohort_b, student=users_set["s_in_b"])
    return {"cohort_a": cohort_a, "cohort_other": cohort_other, "cohort_b": cohort_b}


def _auth(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.mark.django_db
def test_teacher_sees_only_their_students(users_set, cohort_setup):
    c = _auth(users_set["teacher_in"])
    resp = c.get(URL)
    assert resp.status_code == 200, resp.content
    ids = {r["id"] for r in resp.json()["results"]}
    assert ids == {users_set["s1"].id, users_set["s2"].id}
    # Student from other cohort in same org not visible.
    assert users_set["s_other_cohort"].id not in ids
    # Cross-org student never visible.
    assert users_set["s_in_b"].id not in ids


@pytest.mark.django_db
def test_cross_org_teacher_sees_only_own_org(users_set, cohort_setup):
    c = _auth(users_set["teacher_b"])
    resp = c.get(URL)
    assert resp.status_code == 200
    ids = {r["id"] for r in resp.json()["results"]}
    # teacher_b teaches no course yet → empty
    assert ids == set()
    # Even adding a course, they should never see org-a students.
    assert users_set["s1"].id not in ids


@pytest.mark.django_db
def test_teacher_without_courses_sees_nothing(users_set, cohort_setup):
    c = _auth(users_set["teacher_out"])
    resp = c.get(URL)
    assert resp.status_code == 200
    assert resp.json()["results"] == []


@pytest.mark.django_db
def test_admin_sees_all_students_in_org(users_set, cohort_setup):
    c = _auth(users_set["admin_a"])
    resp = c.get(URL)
    assert resp.status_code == 200
    ids = {r["id"] for r in resp.json()["results"]}
    assert {users_set["s1"].id, users_set["s2"].id, users_set["s_other_cohort"].id} <= ids
    assert users_set["s_in_b"].id not in ids


@pytest.mark.django_db
def test_response_shape(users_set, cohort_setup):
    c = _auth(users_set["teacher_in"])
    resp = c.get(URL)
    assert resp.status_code == 200
    rows = resp.json()["results"]
    assert rows
    for row in rows:
        assert set(row).issuperset({
            "id", "email", "name", "handle",
            "cohort_id", "cohort_name",
            "pr_count", "prs_waiting_feedback", "avg_score",
        })
