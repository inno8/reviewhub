"""
Tests for CohortOverviewView — GET /api/grading/cohorts/<id>/overview/.

Covers:
  - Response shape contract (all expected top-level keys + nested fields)
  - Org isolation: teacher in one org → 404 for another org's cohort
  - Enrolled student in cohort → 403 (role-gated)
  - `students` array length matches active CohortMembership count
  - `weakest_criteria` capped at 3 and sorted ascending by avg_score
  - `cohort_patterns` only includes patterns affecting ≥2 students
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
def two_orgs(db):
    from users.models import Organization

    return {
        "a": Organization.objects.create(name="Org A co", slug="org-a-co"),
        "b": Organization.objects.create(name="Org B co", slug="org-b-co"),
    }


@pytest.fixture
def users_set(db, two_orgs):
    return {
        "admin_a": User.objects.create_user(
            username="admin_a_co", email="admin_a_co@x.com", password="p",
            role="admin", organization=two_orgs["a"],
        ),
        "teacher_in": User.objects.create_user(
            username="teacher_in_co", email="tin_co@x.com", password="p",
            role="teacher", organization=two_orgs["a"],
        ),
        "teacher_out": User.objects.create_user(
            username="teacher_out_co", email="tout_co@x.com", password="p",
            role="teacher", organization=two_orgs["a"],
        ),
        "teacher_b": User.objects.create_user(
            username="teacher_b_co", email="tb_co@x.com", password="p",
            role="teacher", organization=two_orgs["b"],
        ),
        "s1": User.objects.create_user(
            username="s1_co", email="s1_co@x.com", password="p",
            role="developer", organization=two_orgs["a"],
        ),
        "s2": User.objects.create_user(
            username="s2_co", email="s2_co@x.com", password="p",
            role="developer", organization=two_orgs["a"],
        ),
        "s3": User.objects.create_user(
            username="s3_co", email="s3_co@x.com", password="p",
            role="developer", organization=two_orgs["a"],
        ),
    }


@pytest.fixture
def rubric_a(db, two_orgs, users_set):
    return Rubric.objects.create(
        org=two_orgs["a"],
        owner=users_set["teacher_in"],
        name="R A co",
        criteria=[
            {
                "id": "testen", "name": "Testen", "kerntaak": "B1-K1-W4", "weight": 1.0,
                "levels": [{"score": 1, "description": "bad"}, {"score": 4, "description": "good"}],
            }
        ],
    )


@pytest.fixture
def cohort_setup(db, two_orgs, users_set, rubric_a):
    cohort_a = Cohort.objects.create(org=two_orgs["a"], name="Cohort Overview A")
    cohort_b = Cohort.objects.create(org=two_orgs["b"], name="Cohort Overview B")
    Course.objects.create(
        org=two_orgs["a"], cohort=cohort_a, owner=users_set["teacher_in"],
        name="Course Overview A", rubric=rubric_a,
    )
    # s1, s2, s3 all enrolled in cohort_a
    CohortMembership.objects.create(cohort=cohort_a, student=users_set["s1"])
    CohortMembership.objects.create(cohort=cohort_a, student=users_set["s2"])
    CohortMembership.objects.create(cohort=cohort_a, student=users_set["s3"])
    return {"cohort_a": cohort_a, "cohort_b": cohort_b}


def _auth(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


URL = "/api/grading/cohorts/{id}/overview/"


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_shape_ok(users_set, cohort_setup):
    c = _auth(users_set["teacher_in"])
    resp = c.get(URL.format(id=cohort_setup["cohort_a"].id))
    assert resp.status_code == 200, resp.content
    data = resp.json()
    for key in (
        "cohort", "activity", "weakest_criteria",
        "cohort_patterns", "students", "weekly_activity",
    ):
        assert key in data
    assert data["cohort"]["id"] == cohort_setup["cohort_a"].id
    assert data["cohort"]["student_count"] == 3
    for key in ("prs_this_sprint", "prs_waiting_feedback", "prs_posted_this_sprint"):
        assert key in data["activity"]


@pytest.mark.django_db
def test_students_array_matches_memberships(users_set, cohort_setup):
    c = _auth(users_set["teacher_in"])
    resp = c.get(URL.format(id=cohort_setup["cohort_a"].id))
    assert resp.status_code == 200
    students = resp.json()["students"]
    assert len(students) == 3
    ids_in_response = {s["id"] for s in students}
    assert ids_in_response == {
        users_set["s1"].id, users_set["s2"].id, users_set["s3"].id,
    }
    # Per-student shape
    for s in students:
        assert set(s).issuperset({
            "id", "name", "email", "eindniveau", "band", "trend",
            "last_pr_days_ago", "prs_waiting_feedback",
            "strongest_criterion", "weakest_criterion",
        })


@pytest.mark.django_db
def test_org_isolation_returns_404(users_set, cohort_setup):
    # teacher in org A asking for cohort in org B
    c = _auth(users_set["teacher_in"])
    resp = c.get(URL.format(id=cohort_setup["cohort_b"].id))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_teacher_not_in_cohort_returns_404(users_set, cohort_setup):
    # teacher_out is in org A but teaches no course in cohort_a
    c = _auth(users_set["teacher_out"])
    resp = c.get(URL.format(id=cohort_setup["cohort_a"].id))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_admin_same_org_200(users_set, cohort_setup):
    c = _auth(users_set["admin_a"])
    resp = c.get(URL.format(id=cohort_setup["cohort_a"].id))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_enrolled_student_403(users_set, cohort_setup):
    c = _auth(users_set["s1"])
    resp = c.get(URL.format(id=cohort_setup["cohort_a"].id))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_anonymous_401(cohort_setup):
    c = APIClient()
    resp = c.get(URL.format(id=cohort_setup["cohort_a"].id))
    assert resp.status_code == 401


@pytest.mark.django_db
def test_weakest_criteria_capped_and_sorted(
    users_set, cohort_setup, two_orgs, rubric_a,
):
    """
    Seed SkillMetric rows across the 6 Crebo slugs so the view has
    something to aggregate. weakest_criteria should cap at 3 and
    be sorted ascending by avg_score.
    """
    from projects.models import Project
    from skills.models import Skill, SkillCategory, SkillMetric

    cat = SkillCategory.objects.create(name="Testing co", slug="testing-co", order=1)
    # Use the Crebo slugs the view looks for.
    slugs = [
        ("testen", 25.0),          # worst
        ("veiligheid", 40.0),
        ("verbetering", 55.0),
        ("code_kwaliteit", 70.0),
        ("code_ontwerp", 80.0),
        ("samenwerking", 90.0),    # best
    ]
    skills = {
        slug: Skill.objects.create(
            category=cat, name=slug, slug=slug, order=i,
        )
        for i, (slug, _) in enumerate(slugs)
    }
    project = Project.objects.create(
        name="co-p", repo_owner="co", repo_name="p",
        created_by=users_set["teacher_in"],
    )
    # Each student gets one metric per skill, all with the same score.
    for student in (users_set["s1"], users_set["s2"], users_set["s3"]):
        for slug, score in slugs:
            SkillMetric.objects.create(
                user=student,
                project=project,
                skill=skills[slug],
                bayesian_score=score,
                observation_count=5,
                confidence=0.7,
            )

    c = _auth(users_set["teacher_in"])
    resp = c.get(URL.format(id=cohort_setup["cohort_a"].id))
    assert resp.status_code == 200
    weakest = resp.json()["weakest_criteria"]
    assert len(weakest) == 3
    slugs_returned = [w["skill_slug"] for w in weakest]
    assert slugs_returned == ["testen", "veiligheid", "verbetering"]
    # avg_score strictly ascending
    scores = [w["avg_score"] for w in weakest]
    assert scores == sorted(scores)


@pytest.mark.django_db
def test_cohort_patterns_filters_single_student(users_set, cohort_setup):
    """
    A Pattern with only 1 affected student must NOT appear.
    A Pattern key shared by 2+ students SHOULD appear.
    """
    from evaluations.models import Pattern

    # Pattern affecting only s1 — must be filtered out.
    Pattern.objects.create(
        user=users_set["s1"],
        pattern_type="security",
        pattern_key="sql-lonely",
        frequency=4,
    )
    # Pattern shared by s1 + s2 — must appear.
    Pattern.objects.create(
        user=users_set["s1"],
        pattern_type="error_handling",
        pattern_key="swallow-catch",
        frequency=3,
    )
    Pattern.objects.create(
        user=users_set["s2"],
        pattern_type="error_handling",
        pattern_key="swallow-catch",
        frequency=2,
    )

    c = _auth(users_set["teacher_in"])
    resp = c.get(URL.format(id=cohort_setup["cohort_a"].id))
    assert resp.status_code == 200
    patterns = resp.json()["cohort_patterns"]
    keys = [p["pattern_key"] for p in patterns]
    assert "swallow-catch" in keys
    assert "sql-lonely" not in keys
    shared = next(p for p in patterns if p["pattern_key"] == "swallow-catch")
    assert shared["affected_student_count"] == 2
    assert shared["total_frequency"] == 5


@pytest.mark.django_db
def test_weekly_activity_has_8_buckets(users_set, cohort_setup):
    c = _auth(users_set["teacher_in"])
    resp = c.get(URL.format(id=cohort_setup["cohort_a"].id))
    assert resp.status_code == 200
    weeks = resp.json()["weekly_activity"]
    # 8 weeks lookback → between 8 and 10 buckets depending on today's weekday.
    assert 8 <= len(weeks) <= 10
    for w in weeks:
        assert "week_start" in w and "pr_count" in w and "avg_score" in w
