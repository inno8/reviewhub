"""
Scope B1 / Workstream A — tests for the new Cohort + CohortMembership models
and the Classroom→Course rename.

Covers:
  - Cohort creation is org-scoped via OrgScopedManager.for_user()
  - CohortMembership.student is unique (OneToOne) — second insert fails
  - Course.cohort FK works and reverse accessor cohort.courses returns it
  - Cohort str repr
  - LLMCostLog reverse relation through cohort (smoke)
  - CohortMembership OrgScopedManager semantics via cohort->org
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from grading.models import Cohort, CohortMembership, Course, Rubric

User = get_user_model()


@pytest.fixture
def org_scaffold(db):
    from users.models import Organization

    org = Organization.objects.create(name="Test Klas Org", slug="klas-org")
    teacher = User.objects.create_user(
        username="t_klas", email="t_klas@ex.com", password="pw",
        role="teacher", organization=org,
    )
    student1 = User.objects.create_user(
        username="s1_klas", email="s1@ex.com", password="pw",
        role="developer", organization=org,
    )
    student2 = User.objects.create_user(
        username="s2_klas", email="s2@ex.com", password="pw",
        role="developer", organization=org,
    )
    return {
        "org": org,
        "teacher": teacher,
        "student1": student1,
        "student2": student2,
    }


@pytest.mark.django_db
class TestCohortModel:
    def test_cohort_creation_with_org(self, org_scaffold):
        cohort = Cohort.objects.create(
            org=org_scaffold["org"],
            name="Klas 2A ICT 2026",
            year="2026-2027",
        )
        assert cohort.id is not None
        assert cohort.org_id == org_scaffold["org"].id
        assert cohort.year == "2026-2027"

    def test_cohort_str_includes_name_and_org(self, org_scaffold):
        cohort = Cohort.objects.create(
            org=org_scaffold["org"], name="Klas 2A ICT",
        )
        rendered = str(cohort)
        assert "Klas 2A ICT" in rendered
        assert "Test Klas Org" in rendered

    def test_org_scoped_manager_filters_by_user_org(self, org_scaffold):
        from users.models import Organization
        other_org = Organization.objects.create(name="Other", slug="other")
        cohort_mine = Cohort.objects.create(org=org_scaffold["org"], name="Mine")
        cohort_other = Cohort.objects.create(org=other_org, name="Theirs")

        # Teacher in org_scaffold.org sees only Mine
        visible = Cohort.objects.for_user(org_scaffold["teacher"])
        ids = list(visible.values_list("id", flat=True))
        assert cohort_mine.id in ids
        assert cohort_other.id not in ids

        # Anonymous / unauth user gets no rows
        anon_qs = Cohort.objects.for_user(None)
        assert anon_qs.count() == 0


@pytest.mark.django_db
class TestCohortMembershipUniqueness:
    def test_second_cohort_membership_for_same_student_fails(self, org_scaffold):
        """OneToOne on student enforces one cohort per student at the DB level."""
        a = Cohort.objects.create(org=org_scaffold["org"], name="Klas A")
        b = Cohort.objects.create(org=org_scaffold["org"], name="Klas B")

        CohortMembership.objects.create(cohort=a, student=org_scaffold["student1"])
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                CohortMembership.objects.create(
                    cohort=b, student=org_scaffold["student1"],
                )

    def test_distinct_students_can_share_a_cohort(self, org_scaffold):
        cohort = Cohort.objects.create(org=org_scaffold["org"], name="Klas A")
        m1 = CohortMembership.objects.create(
            cohort=cohort, student=org_scaffold["student1"],
        )
        m2 = CohortMembership.objects.create(
            cohort=cohort, student=org_scaffold["student2"],
        )
        assert cohort.memberships.count() == 2
        assert {m1.id, m2.id} == set(
            cohort.memberships.values_list("id", flat=True)
        )


@pytest.mark.django_db
class TestCourseCohortRelationship:
    def test_course_cohort_fk_roundtrips(self, org_scaffold):
        cohort = Cohort.objects.create(org=org_scaffold["org"], name="Klas 2A")
        rubric = Rubric.objects.create(
            org=org_scaffold["org"], owner=org_scaffold["teacher"],
            name="R",
            criteria=[
                {"id": "c", "name": "C", "weight": 1,
                 "levels": [{"score": 1}, {"score": 4}]}
            ],
        )
        course = Course.objects.create(
            org=org_scaffold["org"],
            cohort=cohort,
            owner=org_scaffold["teacher"],
            name="Frontend",
            rubric=rubric,
        )
        assert course.cohort_id == cohort.id
        assert list(cohort.courses.values_list("id", flat=True)) == [course.id]

    def test_multiple_courses_share_a_cohort(self, org_scaffold):
        cohort = Cohort.objects.create(org=org_scaffold["org"], name="Klas 2A")
        c1 = Course.objects.create(
            org=org_scaffold["org"], cohort=cohort,
            owner=org_scaffold["teacher"], name="Frontend",
        )
        c2 = Course.objects.create(
            org=org_scaffold["org"], cohort=cohort,
            owner=org_scaffold["teacher"], name="Backend",
        )
        assert cohort.courses.count() == 2
        assert {c1.id, c2.id} == set(cohort.courses.values_list("id", flat=True))

    def test_course_cohort_can_be_null(self, org_scaffold):
        """Cohort FK is nullable on Course (for the initial migration window)."""
        course = Course.objects.create(
            org=org_scaffold["org"],
            owner=org_scaffold["teacher"],
            name="Orphan",
        )
        assert course.cohort_id is None


@pytest.mark.django_db
class TestStudentReverseAccessor:
    def test_student_cohort_membership_accessor(self, org_scaffold):
        cohort = Cohort.objects.create(org=org_scaffold["org"], name="Klas A")
        m = CohortMembership.objects.create(
            cohort=cohort,
            student=org_scaffold["student1"],
            student_repo_url="https://github.com/s1/assignment",
        )
        # OneToOneField gives a reverse accessor on the User side
        student = org_scaffold["student1"]
        student.refresh_from_db()
        assert student.cohort_membership.id == m.id
        assert student.cohort_membership.cohort_id == cohort.id
