"""
Tests for the seed_e2e_grading management command.

Covers:
  1. Happy path: creates 1 Cohort, 1 Rubric, 1 Course, 1 CohortMembership
  2. Idempotent: running twice adds no rows
  3. Dry-run: prints plan, touches no DB rows
  4. Missing org: fails cleanly, no partial writes
  5. Missing teacher: fails cleanly
  6. Missing student: fails cleanly
  7. Student in a DIFFERENT cohort: fails, refuses silent migration
  8. Student in the SAME cohort, different repo_url: updates + logs change
"""
from __future__ import annotations

from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from grading.models import Cohort, CohortMembership, Course, Rubric

User = get_user_model()


@pytest.fixture
def seed_scaffold(db):
    from users.models import Organization

    org = Organization.objects.create(name="ITEC", slug="itec")
    teacher = User.objects.create_user(
        username="teach_e2e",
        email="teacher_e2e@ex.com",
        password="pw",
        role="teacher",
        organization=org,
    )
    student = User.objects.create_user(
        username="stud_e2e",
        email="student_e2e@ex.com",
        password="pw",
        role="developer",
        organization=org,
    )
    return {"org": org, "teacher": teacher, "student": student}


def _run(**extra):
    out = StringIO()
    err = StringIO()
    opts = {
        "org_slug": "itec",
        "teacher_email": "teacher_e2e@ex.com",
        "student_email": "student_e2e@ex.com",
        "repo_url": "https://github.com/inno8/codelens-test",
        "cohort_name": "E2E Dogfood",
        "course_name": "E2E Test Course",
        "stdout": out,
        "stderr": err,
    }
    opts.update(extra)
    call_command("seed_e2e_grading", **opts)
    return out.getvalue()


@pytest.mark.django_db
class TestSeedE2EGrading:
    def test_happy_path_creates_scaffolding(self, seed_scaffold):
        out = _run()
        assert Cohort.objects.count() == 1
        assert Rubric.objects.count() == 1
        assert Course.objects.count() == 1
        assert CohortMembership.objects.count() == 1

        cohort = Cohort.objects.get()
        assert cohort.name == "E2E Dogfood"
        assert cohort.org == seed_scaffold["org"]

        rubric = Rubric.objects.get()
        assert len(rubric.criteria) == 4
        assert {c["id"] for c in rubric.criteria} == {
            "readability", "error_handling", "security", "testing",
        }
        assert rubric.owner == seed_scaffold["teacher"]

        course = Course.objects.get()
        assert course.cohort == cohort
        assert course.owner == seed_scaffold["teacher"]
        assert course.rubric == rubric
        assert course.source_control_type == Course.SourceControlType.GITHUB_ORG

        membership = CohortMembership.objects.get()
        assert membership.student == seed_scaffold["student"]
        assert membership.cohort == cohort
        assert membership.student_repo_url == "https://github.com/inno8/codelens-test"

        assert "ready" in out

    def test_idempotent_double_run(self, seed_scaffold):
        _run()
        pre = (
            Cohort.objects.count(),
            Rubric.objects.count(),
            Course.objects.count(),
            CohortMembership.objects.count(),
        )
        _run()
        post = (
            Cohort.objects.count(),
            Rubric.objects.count(),
            Course.objects.count(),
            CohortMembership.objects.count(),
        )
        assert pre == post == (1, 1, 1, 1)

    def test_dry_run_no_writes(self, seed_scaffold):
        out = _run(dry_run=True)
        assert "DRY-RUN" in out
        assert Cohort.objects.count() == 0
        assert Rubric.objects.count() == 0
        assert Course.objects.count() == 0
        assert CohortMembership.objects.count() == 0

    def test_missing_org_errors(self, seed_scaffold):
        with pytest.raises(CommandError) as exc_info:
            _run(org_slug="does-not-exist")
        assert "does-not-exist" in str(exc_info.value)
        assert Cohort.objects.count() == 0
        assert CohortMembership.objects.count() == 0

    def test_missing_teacher_errors(self, seed_scaffold):
        with pytest.raises(CommandError) as exc_info:
            _run(teacher_email="nobody@ex.com")
        assert "nobody@ex.com" in str(exc_info.value)
        assert Cohort.objects.count() == 0

    def test_missing_student_errors(self, seed_scaffold):
        with pytest.raises(CommandError) as exc_info:
            _run(student_email="nobody@ex.com")
        assert "nobody@ex.com" in str(exc_info.value)
        assert Cohort.objects.count() == 0

    def test_student_in_different_cohort_errors(self, seed_scaffold):
        other_cohort = Cohort.objects.create(
            org=seed_scaffold["org"], name="Other Klas"
        )
        CohortMembership.objects.create(
            cohort=other_cohort,
            student=seed_scaffold["student"],
            student_repo_url="https://github.com/foo/bar",
        )
        with pytest.raises(CommandError) as exc_info:
            _run()
        assert "already has a CohortMembership" in str(exc_info.value)
        # No new cohort/course should be created
        assert Cohort.objects.count() == 1
        assert Course.objects.count() == 0
        # Membership unchanged
        m = CohortMembership.objects.get()
        assert m.cohort == other_cohort
        assert m.student_repo_url == "https://github.com/foo/bar"

    def test_repo_url_update_in_same_cohort(self, seed_scaffold):
        _run()
        # Re-run with a new repo_url
        out = _run(repo_url="https://github.com/inno8/codelens-test-2")
        assert CohortMembership.objects.count() == 1
        m = CohortMembership.objects.get()
        assert m.student_repo_url == "https://github.com/inno8/codelens-test-2"
        assert "Updated CohortMembership repo_url" in out
