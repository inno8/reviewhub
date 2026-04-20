"""
Tests for Workstream D — student intelligence endpoints.

Endpoints covered:
  GET /api/grading/students/<student_id>/snapshot/
  GET /api/grading/students/<student_id>/trajectory/?weeks=12
  GET /api/grading/students/<student_id>/pr-history/?limit=20

Matrix:
  - teacher owning a course in student's cohort  → 200
  - teacher NOT in student's cohort              → 404
  - admin same org                               → 200
  - admin other org                              → 404
  - self                                         → 200
  - other student                                → 404
  - anonymous                                    → 401
  - cross-org isolation (both directions)
  - shape / ordering / query-param respect
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
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


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def two_orgs(db):
    from users.models import Organization

    org_a = Organization.objects.create(name="Org A", slug="org-a-si")
    org_b = Organization.objects.create(name="Org B", slug="org-b-si")
    return {"a": org_a, "b": org_b}


@pytest.fixture
def users_set(db, two_orgs):
    admin_a = User.objects.create_user(
        username="admin_a_si", email="admin_a_si@x.com", password="p",
        role="admin", organization=two_orgs["a"],
    )
    admin_b = User.objects.create_user(
        username="admin_b_si", email="admin_b_si@x.com", password="p",
        role="admin", organization=two_orgs["b"],
    )
    teacher_in = User.objects.create_user(
        username="teacher_in_si", email="tin_si@x.com", password="p",
        role="teacher", organization=two_orgs["a"],
    )
    teacher_out = User.objects.create_user(
        username="teacher_out_si", email="tout_si@x.com", password="p",
        role="teacher", organization=two_orgs["a"],
    )
    teacher_b = User.objects.create_user(
        username="teacher_b_si", email="tb_si@x.com", password="p",
        role="teacher", organization=two_orgs["b"],
    )
    student_a = User.objects.create_user(
        username="student_a_si", email="sa_si@x.com", password="p",
        role="developer", organization=two_orgs["a"],
    )
    student_other = User.objects.create_user(
        username="student_other_si", email="so_si@x.com", password="p",
        role="developer", organization=two_orgs["a"],
    )
    student_b = User.objects.create_user(
        username="student_b_si", email="sb_si@x.com", password="p",
        role="developer", organization=two_orgs["b"],
    )
    return {
        "admin_a": admin_a, "admin_b": admin_b,
        "teacher_in": teacher_in, "teacher_out": teacher_out, "teacher_b": teacher_b,
        "student_a": student_a, "student_other": student_other, "student_b": student_b,
    }


@pytest.fixture
def rubric_a(db, two_orgs, users_set):
    return Rubric.objects.create(
        org=two_orgs["a"], owner=users_set["teacher_in"], name="R A",
        criteria=[
            {
                "id": "readability", "name": "Readability", "weight": 1.0,
                "levels": [
                    {"score": 1, "description": "bad"},
                    {"score": 4, "description": "good"},
                ],
            }
        ],
    )


@pytest.fixture
def rubric_b(db, two_orgs, users_set):
    return Rubric.objects.create(
        org=two_orgs["b"], owner=users_set["teacher_b"], name="R B",
        criteria=[
            {
                "id": "readability", "name": "Readability", "weight": 1.0,
                "levels": [
                    {"score": 1, "description": "bad"},
                    {"score": 4, "description": "good"},
                ],
            }
        ],
    )


@pytest.fixture
def cohort_setup(db, two_orgs, users_set, rubric_a, rubric_b):
    """Cohort A has a Course owned by teacher_in; student_a is enrolled."""
    cohort_a = Cohort.objects.create(org=two_orgs["a"], name="Cohort A SI")
    cohort_b = Cohort.objects.create(org=two_orgs["b"], name="Cohort B SI")
    course_a = Course.objects.create(
        org=two_orgs["a"], cohort=cohort_a, owner=users_set["teacher_in"],
        name="Course A SI", rubric=rubric_a,
    )
    course_b = Course.objects.create(
        org=two_orgs["b"], cohort=cohort_b, owner=users_set["teacher_b"],
        name="Course B SI", rubric=rubric_b,
    )
    # Enroll student_a in cohort_a; student_b in cohort_b; student_other
    # is in org A but NOT in cohort_a (teacher_in should NOT see them).
    CohortMembership.objects.create(cohort=cohort_a, student=users_set["student_a"])
    CohortMembership.objects.create(cohort=cohort_b, student=users_set["student_b"])
    return {
        "cohort_a": cohort_a, "cohort_b": cohort_b,
        "course_a": course_a, "course_b": course_b,
    }


@pytest.fixture
def sessions_for_a(db, two_orgs, users_set, cohort_setup, rubric_a):
    """Create a couple of submissions + grading sessions for student_a."""
    subs = []
    now = timezone.now()
    for i in range(3):
        sub = Submission.objects.create(
            org=two_orgs["a"],
            course=cohort_setup["course_a"],
            student=users_set["student_a"],
            repo_full_name=f"student_a/repo-{i}",
            pr_number=i + 1,
            pr_url=f"https://example.test/pr/{i + 1}",
            pr_title=f"PR {i + 1}",
            head_branch="feat",
        )
        sess = GradingSession.objects.create(
            org=two_orgs["a"], submission=sub, rubric=rubric_a,
            state="drafted",
            ai_draft_scores={"readability": {"score": 3 + (i % 2), "evidence": "x"}},
            ai_draft_comments=[{"file": "a.py", "line": 1, "body": "b"}] * (i + 1),
        )
        subs.append((sub, sess))
    return subs


def _auth(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


# ─────────────────────────────────────────────────────────────────────────────
# Snapshot
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestStudentSnapshotPermissions:
    URL = "/api/grading/students/{id}/snapshot/"

    def test_anonymous_401(self, users_set, cohort_setup):
        c = APIClient()
        resp = c.get(self.URL.format(id=users_set["student_a"].id))
        assert resp.status_code == 401

    def test_teacher_in_cohort_200(self, users_set, cohort_setup):
        c = _auth(users_set["teacher_in"])
        resp = c.get(self.URL.format(id=users_set["student_a"].id))
        assert resp.status_code == 200
        data = resp.json()
        # Shape assertions
        for key in (
            "student", "skill_radar", "recurring_patterns",
            "trending_up", "trending_down", "recent_activity",
            "suggested_interventions",
        ):
            assert key in data
        assert data["student"]["id"] == users_set["student_a"].id
        assert data["student"]["cohort"] is not None
        assert data["student"]["cohort"]["name"] == cohort_setup["cohort_a"].name
        assert data["suggested_interventions"] == []

    def test_teacher_not_in_cohort_404(self, users_set, cohort_setup):
        c = _auth(users_set["teacher_out"])
        resp = c.get(self.URL.format(id=users_set["student_a"].id))
        assert resp.status_code == 404

    def test_admin_same_org_200(self, users_set, cohort_setup):
        c = _auth(users_set["admin_a"])
        resp = c.get(self.URL.format(id=users_set["student_a"].id))
        assert resp.status_code == 200

    def test_admin_other_org_404(self, users_set, cohort_setup):
        c = _auth(users_set["admin_b"])
        resp = c.get(self.URL.format(id=users_set["student_a"].id))
        assert resp.status_code == 404

    def test_self_200(self, users_set, cohort_setup):
        c = _auth(users_set["student_a"])
        resp = c.get(self.URL.format(id=users_set["student_a"].id))
        assert resp.status_code == 200
        assert resp.json()["student"]["id"] == users_set["student_a"].id

    def test_other_student_404(self, users_set, cohort_setup):
        c = _auth(users_set["student_other"])
        resp = c.get(self.URL.format(id=users_set["student_a"].id))
        assert resp.status_code == 404

    def test_cross_org_student_404(self, users_set, cohort_setup):
        """teacher_in (org A) cannot see student_b (org B)."""
        c = _auth(users_set["teacher_in"])
        resp = c.get(self.URL.format(id=users_set["student_b"].id))
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Trajectory
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestStudentTrajectory:
    URL = "/api/grading/students/{id}/trajectory/"

    def test_teacher_in_cohort_200_chronological(self, users_set, cohort_setup):
        c = _auth(users_set["teacher_in"])
        resp = c.get(self.URL.format(id=users_set["student_a"].id) + "?weeks=4")
        assert resp.status_code == 200
        data = resp.json()
        assert "weeks" in data and "milestones" in data
        # Chronological: week_start strings sort ascending
        week_starts = [w["week_start"] for w in data["weeks"]]
        assert week_starts == sorted(week_starts)
        # 4 weeks window → ~4-5 buckets (depending on today's weekday)
        assert 3 <= len(week_starts) <= 6

    def test_teacher_not_in_cohort_404(self, users_set, cohort_setup):
        c = _auth(users_set["teacher_out"])
        resp = c.get(self.URL.format(id=users_set["student_a"].id))
        assert resp.status_code == 404

    def test_admin_other_org_404(self, users_set, cohort_setup):
        c = _auth(users_set["admin_b"])
        resp = c.get(self.URL.format(id=users_set["student_a"].id))
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# PR history
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestStudentPRHistory:
    URL = "/api/grading/students/{id}/pr-history/"

    def test_teacher_in_cohort_sees_sessions(
        self, users_set, cohort_setup, sessions_for_a
    ):
        c = _auth(users_set["teacher_in"])
        resp = c.get(self.URL.format(id=users_set["student_a"].id))
        assert resp.status_code == 200
        data = resp.json()
        assert data["student"]["id"] == users_set["student_a"].id
        assert len(data["sessions"]) == 3
        # rubric_score_avg computed from ai_draft_scores when final is empty
        assert data["sessions"][0]["rubric_score_avg"] is not None
        # Newest-first by created_at. Three sessions exist; the first
        # entry returned should correspond to the last-created one.
        from grading.models import GradingSession
        expected_first = (
            GradingSession.objects
            .filter(submission__student=users_set["student_a"])
            .order_by("-created_at", "-id")
            .values_list("id", flat=True)
            .first()
        )
        assert data["sessions"][0]["id"] == expected_first

    def test_limit_respected(self, users_set, cohort_setup, sessions_for_a):
        c = _auth(users_set["teacher_in"])
        resp = c.get(self.URL.format(id=users_set["student_a"].id) + "?limit=2")
        assert resp.status_code == 200
        assert len(resp.json()["sessions"]) == 2

    def test_teacher_not_in_cohort_404(
        self, users_set, cohort_setup, sessions_for_a
    ):
        c = _auth(users_set["teacher_out"])
        resp = c.get(self.URL.format(id=users_set["student_a"].id))
        assert resp.status_code == 404

    def test_self_200(self, users_set, cohort_setup, sessions_for_a):
        c = _auth(users_set["student_a"])
        resp = c.get(self.URL.format(id=users_set["student_a"].id))
        assert resp.status_code == 200
        assert len(resp.json()["sessions"]) == 3

    def test_cross_org_isolation_on_pr_history(
        self, users_set, cohort_setup, sessions_for_a
    ):
        """admin of org B must not see student_a (org A) sessions."""
        c = _auth(users_set["admin_b"])
        resp = c.get(self.URL.format(id=users_set["student_a"].id))
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Cohort recurring errors
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def cohort_patterns(db, two_orgs, users_set, cohort_setup):
    """
    Seed Pattern rows for the cohort_a students. Three students get the
    'bare-except' pattern with frequencies 5/3/7 (total 15, 3 students).
    Two students get 'mutable-default' with 4/2. One resolved pattern
    that should be filtered out. Plus a removed membership student with
    a pattern that should be excluded.
    """
    from evaluations.models import Pattern

    # Add two more active students to cohort_a.
    student_2 = User.objects.create_user(
        username="student_a2_si", email="sa2_si@x.com", password="p",
        role="developer", organization=two_orgs["a"],
    )
    student_3 = User.objects.create_user(
        username="student_a3_si", email="sa3_si@x.com", password="p",
        role="developer", organization=two_orgs["a"],
    )
    # A student that was removed from the cohort — their patterns must
    # NOT appear in the aggregation.
    student_removed = User.objects.create_user(
        username="student_removed_si", email="srm_si@x.com", password="p",
        role="developer", organization=two_orgs["a"],
    )
    CohortMembership.objects.create(cohort=cohort_setup["cohort_a"], student=student_2)
    CohortMembership.objects.create(cohort=cohort_setup["cohort_a"], student=student_3)
    CohortMembership.objects.create(
        cohort=cohort_setup["cohort_a"],
        student=student_removed,
        removed_at=timezone.now(),
    )

    student_a = users_set["student_a"]

    # bare-except × 3 students (freqs 5, 3, 7 → total 15)
    Pattern.objects.create(
        user=student_a, pattern_type="EXCEPTION_HANDLING",
        pattern_key="bare-except", frequency=5,
    )
    Pattern.objects.create(
        user=student_2, pattern_type="EXCEPTION_HANDLING",
        pattern_key="bare-except", frequency=3,
    )
    Pattern.objects.create(
        user=student_3, pattern_type="EXCEPTION_HANDLING",
        pattern_key="bare-except", frequency=7,
    )
    # mutable-default × 2 students
    Pattern.objects.create(
        user=student_a, pattern_type="STYLE",
        pattern_key="mutable-default", frequency=4,
    )
    Pattern.objects.create(
        user=student_2, pattern_type="STYLE",
        pattern_key="mutable-default", frequency=2,
    )
    # Resolved pattern — must be filtered out
    Pattern.objects.create(
        user=student_a, pattern_type="STYLE",
        pattern_key="old-fixed-thing", frequency=99,
        is_resolved=True, resolved_at=timezone.now(),
    )
    # Removed membership → must be filtered out
    Pattern.objects.create(
        user=student_removed, pattern_type="STYLE",
        pattern_key="ghost-pattern", frequency=50,
    )
    return {
        "student_2": student_2,
        "student_3": student_3,
        "student_removed": student_removed,
    }


@pytest.mark.django_db
class TestCohortRecurringErrorsEndpoint:
    URL = "/api/grading/cohorts/{id}/recurring-errors/"

    def test_anonymous_401(self, users_set, cohort_setup):
        c = APIClient()
        resp = c.get(self.URL.format(id=cohort_setup["cohort_a"].id))
        assert resp.status_code == 401

    def test_teacher_in_cohort_200_shape(
        self, users_set, cohort_setup, cohort_patterns
    ):
        c = _auth(users_set["teacher_in"])
        resp = c.get(self.URL.format(id=cohort_setup["cohort_a"].id))
        assert resp.status_code == 200
        data = resp.json()
        assert data["cohort"]["id"] == cohort_setup["cohort_a"].id
        assert data["cohort"]["name"] == cohort_setup["cohort_a"].name
        # 3 active students: student_a + student_2 + student_3
        assert data["cohort"]["student_count"] == 3
        assert isinstance(data["top_patterns"], list)
        # bare-except should be first (3 affected > 2 affected)
        first = data["top_patterns"][0]
        assert first["pattern_key"] == "bare-except"
        assert first["affected_students"] == 3
        assert first["total_frequency"] == 15
        assert first["avg_frequency_per_student"] == 5.0
        assert first["pattern_type"] == "EXCEPTION_HANDLING"
        assert "severity" in first
        assert "example_findings" in first
        # Summary shape
        assert "summary" in data
        assert data["summary"]["most_affected_category"] == "EXCEPTION_HANDLING"

    def test_resolved_patterns_excluded(
        self, users_set, cohort_setup, cohort_patterns
    ):
        c = _auth(users_set["teacher_in"])
        resp = c.get(self.URL.format(id=cohort_setup["cohort_a"].id))
        assert resp.status_code == 200
        keys = [p["pattern_key"] for p in resp.json()["top_patterns"]]
        assert "old-fixed-thing" not in keys

    def test_removed_membership_patterns_excluded(
        self, users_set, cohort_setup, cohort_patterns
    ):
        c = _auth(users_set["teacher_in"])
        resp = c.get(self.URL.format(id=cohort_setup["cohort_a"].id))
        assert resp.status_code == 200
        keys = [p["pattern_key"] for p in resp.json()["top_patterns"]]
        assert "ghost-pattern" not in keys

    def test_teacher_not_in_cohort_404(
        self, users_set, cohort_setup, cohort_patterns
    ):
        """Same-org teacher who doesn't teach this cohort → 404 (isolation)."""
        c = _auth(users_set["teacher_out"])
        resp = c.get(self.URL.format(id=cohort_setup["cohort_a"].id))
        assert resp.status_code == 404

    def test_admin_same_org_200(
        self, users_set, cohort_setup, cohort_patterns
    ):
        c = _auth(users_set["admin_a"])
        resp = c.get(self.URL.format(id=cohort_setup["cohort_a"].id))
        assert resp.status_code == 200

    def test_admin_other_org_404(
        self, users_set, cohort_setup, cohort_patterns
    ):
        c = _auth(users_set["admin_b"])
        resp = c.get(self.URL.format(id=cohort_setup["cohort_a"].id))
        assert resp.status_code == 404

    def test_student_in_cohort_403(
        self, users_set, cohort_setup, cohort_patterns
    ):
        """student_a is enrolled but this is teacher-only intelligence."""
        c = _auth(users_set["student_a"])
        resp = c.get(self.URL.format(id=cohort_setup["cohort_a"].id))
        assert resp.status_code == 403

    def test_empty_cohort_returns_empty_list(
        self, two_orgs, users_set, cohort_setup
    ):
        """A cohort with no patterns yet still returns 200 with [] list."""
        from grading.models import Cohort as CohortModel
        empty = CohortModel.objects.create(
            org=two_orgs["a"], name="Empty Cohort SI"
        )
        from grading.models import Course as CourseModel
        CourseModel.objects.create(
            org=two_orgs["a"], cohort=empty,
            owner=users_set["teacher_in"],
            name="Empty Course",
        )
        c = _auth(users_set["teacher_in"])
        resp = c.get(self.URL.format(id=empty.id))
        assert resp.status_code == 200
        data = resp.json()
        assert data["top_patterns"] == []
        assert data["summary"]["total_unresolved_patterns"] == 0
        assert data["summary"]["most_affected_category"] is None
