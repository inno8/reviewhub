"""
Tests for the StudentTrajectoryView granularity + cohort-mean additions.

Covers:
  - Default (no new params) returns the same shape as before (back-compat).
  - ?granularity=skill returns 6 skill series keyed to Crebo slugs.
  - ?include_cohort_mean=true returns a cohort_mean sibling series.
  - Student with no CohortMembership → cohort_mean is empty list, no 500.
  - Org isolation: teacher from org A cannot access student in org B (404).
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from grading.models import Cohort, CohortMembership, Course, Rubric
from grading.views_student_intelligence import CREBO_SKILL_SLUGS

User = get_user_model()


URL = "/api/grading/students/{id}/trajectory/"


def _auth(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.fixture
def crebo_skills(db):
    """Ensure the 6 Crebo Skill rows exist."""
    from skills.models import Skill, SkillCategory

    cat, _ = SkillCategory.objects.get_or_create(
        name="Crebo", slug="crebo", defaults={"order": 99},
    )
    out = {}
    for i, slug in enumerate(CREBO_SKILL_SLUGS):
        s, _ = Skill.objects.get_or_create(
            slug=slug,
            defaults={
                "category": cat,
                "name": slug.replace("_", " ").title(),
                "order": i,
            },
        )
        out[slug] = s
    return out


@pytest.fixture
def setup_one_cohort(db, crebo_skills):
    """Single org / cohort / course / teacher / student + peers."""
    from users.models import Organization

    org = Organization.objects.create(name="Org TG", slug="org-tg")
    teacher = User.objects.create_user(
        username="teacher_tg", email="teacher_tg@x.com", password="p",
        role="teacher", organization=org,
    )
    student = User.objects.create_user(
        username="student_tg", email="student_tg@x.com", password="p",
        role="developer", organization=org,
    )
    peer1 = User.objects.create_user(
        username="peer1_tg", email="peer1_tg@x.com", password="p",
        role="developer", organization=org,
    )
    peer2 = User.objects.create_user(
        username="peer2_tg", email="peer2_tg@x.com", password="p",
        role="developer", organization=org,
    )
    rubric = Rubric.objects.create(
        org=org, owner=teacher, name="Crebo-ish",
        criteria=[
            {
                "id": "veiligheid", "name": "Veiligheid",
                "kerntaak": "B1-K1-W3",
                "weight": 1.0,
                "levels": [
                    {"score": 1, "description": "bad"},
                    {"score": 4, "description": "good"},
                ],
            },
        ],
    )
    cohort = Cohort.objects.create(org=org, name="Cohort TG")
    Course.objects.create(
        org=org, cohort=cohort, owner=teacher, name="Course TG", rubric=rubric,
    )
    CohortMembership.objects.create(cohort=cohort, student=student)
    CohortMembership.objects.create(cohort=cohort, student=peer1)
    CohortMembership.objects.create(cohort=cohort, student=peer2)
    return {
        "org": org, "teacher": teacher, "student": student,
        "peer1": peer1, "peer2": peer2,
        "cohort": cohort,
    }


def _seed_observation(user, skill, score, when):
    """Helper: create a SkillObservation and backdate created_at."""
    from projects.models import Project
    from evaluations.models import Evaluation
    from skills.models import SkillObservation

    project, _ = Project.objects.get_or_create(
        name=f"p_{user.id}", repo_owner="o",
        repo_name=f"r_{user.id}", defaults={"created_by": user},
    )
    evaluation = Evaluation.objects.create(
        project=project, author=user, commit_sha=("a" * 40),
        status="completed",
    )
    obs = SkillObservation.objects.create(
        user=user, project=project, evaluation=evaluation, skill=skill,
        commit_sha="b" * 40, quality_score=score, complexity_weight=1.0,
    )
    SkillObservation.objects.filter(pk=obs.pk).update(created_at=when)
    return obs


@pytest.mark.django_db
class TestTrajectoryBackCompat:
    def test_default_params_shape_unchanged(self, setup_one_cohort):
        student = setup_one_cohort["student"]
        c = _auth(setup_one_cohort["teacher"])
        resp = c.get(URL.format(id=student.id) + "?weeks=4")
        assert resp.status_code == 200
        data = resp.json()
        # Original required keys still present.
        assert "weeks" in data
        assert "milestones" in data
        assert "student" in data
        # Each week still has avg_score_per_category.
        for w in data["weeks"]:
            assert "avg_score_per_category" in w
            assert "prs_count" in w
            assert "findings_count" in w
        # Category mode must not leak skill series or cohort_mean.
        assert "series" not in data
        assert "cohort_mean" not in data


@pytest.mark.django_db
class TestTrajectoryGranularitySkill:
    def test_granularity_skill_returns_six_series(
        self, setup_one_cohort, crebo_skills
    ):
        student = setup_one_cohort["student"]
        now = timezone.now()
        # One obs per slug so every series has at least one bucket.
        for slug in CREBO_SKILL_SLUGS:
            _seed_observation(
                student, crebo_skills[slug], 72.0, now - timedelta(days=2),
            )

        c = _auth(setup_one_cohort["teacher"])
        resp = c.get(
            URL.format(id=student.id) + "?weeks=4&granularity=skill"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["granularity"] == "skill"
        assert "series" in data
        assert len(data["series"]) == 6
        returned_slugs = [s["skill_slug"] for s in data["series"]]
        assert returned_slugs == CREBO_SKILL_SLUGS  # stable ordered
        # Each series has display_name, kerntaak, points[].
        for s in data["series"]:
            assert "display_name" in s
            assert "kerntaak" in s
            assert "points" in s
            # Points parallel the weeks array.
            assert len(s["points"]) == len(data["weeks"])

        # The shipped-defaults rubric should yield kerntaak for veiligheid.
        veiligheid = next(s for s in data["series"] if s["skill_slug"] == "veiligheid")
        assert veiligheid["kerntaak"] == "B1-K1-W3"


@pytest.mark.django_db
class TestTrajectoryCohortMean:
    def test_include_cohort_mean_returns_sibling(
        self, setup_one_cohort, crebo_skills
    ):
        student = setup_one_cohort["student"]
        peer1 = setup_one_cohort["peer1"]
        peer2 = setup_one_cohort["peer2"]
        now = timezone.now()
        skill = crebo_skills["veiligheid"]
        # Seed obs for student + both peers.
        _seed_observation(student, skill, 60.0, now - timedelta(days=3))
        _seed_observation(peer1, skill, 80.0, now - timedelta(days=3))
        _seed_observation(peer2, skill, 70.0, now - timedelta(days=3))

        c = _auth(setup_one_cohort["teacher"])
        resp = c.get(
            URL.format(id=student.id) + "?weeks=4&include_cohort_mean=true"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "cohort_mean" in data
        # At least one series — and it must not include the student's own scores.
        # With peers scoring 80 and 70, cohort_mean avg should be 75 (not 70).
        assert len(data["cohort_mean"]) >= 1
        # Find any point with data.
        found_value = None
        for series in data["cohort_mean"]:
            for p in series["points"]:
                if p.get("avg_score") is not None:
                    found_value = p["avg_score"]
                    assert p["student_count"] == 2  # two peers (not student)
                    break
            if found_value is not None:
                break
        assert found_value is not None
        assert abs(found_value - 75.0) < 0.5

    def test_student_without_cohort_returns_empty_cohort_mean(
        self, setup_one_cohort, crebo_skills
    ):
        """Student with no CohortMembership — no 500, empty cohort_mean."""
        # Make an orphan student in the same org but no membership.
        from users.models import Organization
        org = setup_one_cohort["org"]
        orphan = User.objects.create_user(
            username="orphan_tg", email="orphan_tg@x.com", password="p",
            role="developer", organization=org,
        )
        # Admin can view any student in their org.
        admin = User.objects.create_user(
            username="admin_tg", email="admin_tg@x.com", password="p",
            role="admin", organization=org,
        )
        c = _auth(admin)
        resp = c.get(
            URL.format(id=orphan.id) + "?include_cohort_mean=true"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "cohort_mean" in data
        assert data["cohort_mean"] == []


@pytest.mark.django_db
class TestTrajectoryOrgIsolation:
    def test_cross_org_teacher_cannot_pull_trajectory(
        self, setup_one_cohort, crebo_skills
    ):
        """Teacher from a different org gets 404 even with the new params."""
        from users.models import Organization

        other_org = Organization.objects.create(name="Org Other", slug="org-other-tg")
        other_teacher = User.objects.create_user(
            username="other_teacher_tg", email="other_tg@x.com", password="p",
            role="teacher", organization=other_org,
        )
        student = setup_one_cohort["student"]

        c = _auth(other_teacher)
        resp = c.get(
            URL.format(id=student.id)
            + "?granularity=skill&include_cohort_mean=true"
        )
        assert resp.status_code == 404
