"""
Per-skill breakdown on the StudentSnapshotView response.

Scope: the `per_skill` array added to the snapshot alongside `skill_radar`.
Surfaces the 6 Crebo criterion slugs (code_ontwerp, code_kwaliteit,
veiligheid, testen, verbetering, samenwerking) as a stable, ordered list
regardless of which Skill rows the student happens to have metrics for.

Mirrors the fixture style of test_student_intelligence.py but keeps its
own minimal setup so it runs standalone.
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


@pytest.fixture
def ps_setup(db):
    """Minimal org + cohort + course + teacher + student + rubric."""
    from users.models import Organization

    org = Organization.objects.create(name="Org PS", slug="org-ps")
    teacher = User.objects.create_user(
        username="teacher_ps", email="teacher_ps@x.com", password="p",
        role="teacher", organization=org,
    )
    student = User.objects.create_user(
        username="student_ps", email="student_ps@x.com", password="p",
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
    cohort = Cohort.objects.create(org=org, name="Cohort PS")
    Course.objects.create(
        org=org, cohort=cohort, owner=teacher, name="Course PS", rubric=rubric,
    )
    CohortMembership.objects.create(cohort=cohort, student=student)
    return {
        "org": org, "teacher": teacher, "student": student,
        "rubric": rubric, "cohort": cohort,
    }


@pytest.fixture
def skill_rows(db):
    """Ensure the 6 Crebo skills exist with matching slugs."""
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


def _auth(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.mark.django_db
class TestPerSkillShape:
    URL = "/api/grading/students/{id}/snapshot/"

    def test_per_skill_present_with_all_six_slugs(self, ps_setup, skill_rows):
        c = _auth(ps_setup["teacher"])
        resp = c.get(self.URL.format(id=ps_setup["student"].id))
        assert resp.status_code == 200
        data = resp.json()
        assert "per_skill" in data, "per_skill must be added to snapshot"
        assert len(data["per_skill"]) == 6
        slugs = [row["skill_slug"] for row in data["per_skill"]]
        assert slugs == CREBO_SKILL_SLUGS  # stable ordered

    def test_per_skill_item_shape(self, ps_setup, skill_rows):
        c = _auth(ps_setup["teacher"])
        data = c.get(self.URL.format(id=ps_setup["student"].id)).json()
        for row in data["per_skill"]:
            for key in (
                "skill_slug", "display_name", "kerntaak",
                "bayesian_score", "confidence", "observation_count",
                "trend", "trend_delta", "level_label",
            ):
                assert key in row, f"per_skill row missing key: {key}"
            assert row["trend"] in ("up", "down", "stable")

    def test_veiligheid_kerntaak_from_rubric(self, ps_setup, skill_rows):
        """display_name + kerntaak should be sourced from the course rubric."""
        c = _auth(ps_setup["teacher"])
        data = c.get(self.URL.format(id=ps_setup["student"].id)).json()
        veiligheid = next(r for r in data["per_skill"] if r["skill_slug"] == "veiligheid")
        assert veiligheid["display_name"] == "Veiligheid"
        assert veiligheid["kerntaak"] == "B1-K1-W3"

    def test_other_slugs_fall_back_to_shipped_defaults(self, ps_setup, skill_rows):
        """Slugs not in the rubric still carry a sensible display_name from defaults."""
        c = _auth(ps_setup["teacher"])
        data = c.get(self.URL.format(id=ps_setup["student"].id)).json()
        testen = next(r for r in data["per_skill"] if r["skill_slug"] == "testen")
        assert testen["display_name"] == "Testen"
        assert testen["kerntaak"] == "B1-K1-W4"


@pytest.mark.django_db
class TestPerSkillTrend:
    URL = "/api/grading/students/{id}/snapshot/"

    def test_trend_up_with_improving_observations(self, ps_setup, skill_rows):
        """Observations improving across the 4-week boundary → trend == up."""
        from projects.models import Project
        from evaluations.models import Evaluation
        from skills.models import SkillMetric, SkillObservation

        student = ps_setup["student"]
        skill = skill_rows["veiligheid"]
        project = Project.objects.create(
            name="p", repo_owner="o", repo_name="r", created_by=student,
        )
        evaluation = Evaluation.objects.create(
            project=project, author=student, commit_sha="a" * 40,
            status="completed",
        )
        SkillMetric.objects.create(
            user=student, project=project, skill=skill,
            bayesian_score=60.0, confidence=0.3, observation_count=6,
        )

        now = timezone.now()
        # prior window: scores around 40
        for i in range(3):
            obs = SkillObservation.objects.create(
                user=student, project=project, evaluation=evaluation, skill=skill,
                commit_sha="b" * 40, quality_score=40.0, complexity_weight=1.0,
            )
            SkillObservation.objects.filter(pk=obs.pk).update(
                created_at=now - timedelta(weeks=6, days=i),
            )
        # recent window: scores around 80
        for i in range(3):
            obs = SkillObservation.objects.create(
                user=student, project=project, evaluation=evaluation, skill=skill,
                commit_sha="c" * 40, quality_score=80.0, complexity_weight=1.0,
            )
            SkillObservation.objects.filter(pk=obs.pk).update(
                created_at=now - timedelta(days=2 + i),
            )

        c = _auth(ps_setup["teacher"])
        data = c.get(self.URL.format(id=student.id)).json()
        row = next(r for r in data["per_skill"] if r["skill_slug"] == "veiligheid")
        assert row["trend"] == "up"
        assert row["trend_delta"] > 2
        assert row["observation_count"] == 6
        assert row["bayesian_score"] is not None
