"""
Regression test: every student's skill_radar shows the same canonical
SkillCategory list, regardless of which categories they have metrics
in.

Bug seen Apr 25 2026 (student-side QA pass): tester showed 8 radar
spokes (legacy 8-cat seed), Webdev cohort students showed 5 (only
where the dogfood seeder created metrics). Flipping between students
mid-pitch made the radar visibly different shapes.

Fix: iterate over every SkillCategory that has at least one Skill,
not just categories the student has metrics for. Empty categories
render as score=0, confidence=0, is_preliminary=True — the radar
chart de-emphasizes them visually but the spoke is there.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from grading.models import (
    Cohort,
    CohortMembership,
    Course,
    Rubric,
)
from skills.models import Skill, SkillCategory, SkillMetric

User = get_user_model()


@pytest.fixture
def student_with_partial_metrics(db):
    """Student with skill metrics in only 2 of N existing categories.
    The radar should still show all N spokes (with the empty ones at
    score=0, is_preliminary=True)."""
    from projects.models import Project
    from users.models import Organization

    org = Organization.objects.create(name="Org Radar", slug="org-radar")
    teacher = User.objects.create_user(
        username="t_radar", email="t_radar@example.com", password="pw",
        role="teacher", organization=org,
    )
    student = User.objects.create_user(
        username="s_radar", email="s_radar@example.com", password="pw",
        role="developer", organization=org,
    )
    rubric = Rubric.objects.create(
        org=org, owner=teacher, name="R",
        criteria=[{
            "id": "c1", "name": "C1", "weight": 1.0,
            "levels": [{"score": 1, "description": "x"}, {"score": 4, "description": "y"}],
        }],
    )
    cohort = Cohort.objects.create(org=org, name="Cohort Radar")
    Course.objects.create(
        org=org, cohort=cohort, owner=teacher, name="Course Radar", rubric=rubric,
    )
    CohortMembership.objects.create(student=student, cohort=cohort)

    # Create 4 categories. Student has metrics in only 2.
    cat_alpha = SkillCategory.objects.create(name="Alpha", slug="alpha", color="#aaaaaa")
    cat_beta = SkillCategory.objects.create(name="Beta", slug="beta", color="#bbbbbb")
    cat_gamma = SkillCategory.objects.create(name="Gamma", slug="gamma", color="#cccccc")
    cat_empty = SkillCategory.objects.create(name="EmptyCategory", slug="empty_cat", color="#dddddd")
    # cat_empty has NO skills under it — should NOT appear in the radar.

    skill_a = Skill.objects.create(category=cat_alpha, name="A1", slug="alpha_one")
    skill_b = Skill.objects.create(category=cat_beta, name="B1", slug="beta_one")
    Skill.objects.create(category=cat_gamma, name="G1", slug="gamma_one")
    # No skill under cat_empty.

    project = Project.objects.create(
        provider="github", repo_owner="test", repo_name="radar",
        name="Radar Test", repo_url="https://github.com/test/radar",
        created_by=teacher,
    )
    SkillMetric.objects.create(
        user=student, project=project, skill=skill_a,
        bayesian_score=80.0, confidence=0.30, observation_count=5, trend="stable",
    )
    SkillMetric.objects.create(
        user=student, project=project, skill=skill_b,
        bayesian_score=60.0, confidence=0.20, observation_count=4, trend="up",
    )
    # No metric for Gamma — that category should still render with score=0.

    return {"teacher": teacher, "student": student}


@pytest.mark.django_db
class TestRadarCanonicalCategories:
    def test_radar_includes_categories_without_metrics(self, student_with_partial_metrics):
        """Student has metrics in 2 of 3 populated categories. Radar must
        show all 3 spokes — the third with score=0, is_preliminary=True."""
        f = student_with_partial_metrics
        c = APIClient()
        c.force_authenticate(user=f["teacher"])
        resp = c.get(f"/api/grading/students/{f['student'].id}/snapshot/")
        assert resp.status_code == 200, resp.content
        radar = resp.json()["skill_radar"]
        names = {r["category"] for r in radar}
        assert "Alpha" in names
        assert "Beta" in names
        assert "Gamma" in names, "Empty-data category dropped — radar shape inconsistent"

    def test_empty_category_no_skills_excluded(self, student_with_partial_metrics):
        """A SkillCategory with zero Skill rows must NOT appear (no data
        to show, ever)."""
        f = student_with_partial_metrics
        c = APIClient()
        c.force_authenticate(user=f["teacher"])
        resp = c.get(f"/api/grading/students/{f['student'].id}/snapshot/")
        radar = resp.json()["skill_radar"]
        names = {r["category"] for r in radar}
        assert "EmptyCategory" not in names

    def test_no_metric_category_renders_zero_preliminary(self, student_with_partial_metrics):
        """Gamma has a Skill but the student has no metric for it. The
        spoke must render with score=0 and is_preliminary=True so the
        frontend mutes it."""
        f = student_with_partial_metrics
        c = APIClient()
        c.force_authenticate(user=f["teacher"])
        resp = c.get(f"/api/grading/students/{f['student'].id}/snapshot/")
        radar = resp.json()["skill_radar"]
        gamma = next(r for r in radar if r["category"] == "Gamma")
        assert gamma["score"] == 0.0
        assert gamma["confidence"] == 0.0
        assert gamma["is_preliminary"] is True
        assert gamma["level_label"] is None

    def test_metric_category_keeps_real_score(self, student_with_partial_metrics):
        """Sanity: categories with real metrics still report real scores."""
        f = student_with_partial_metrics
        c = APIClient()
        c.force_authenticate(user=f["teacher"])
        resp = c.get(f"/api/grading/students/{f['student'].id}/snapshot/")
        radar = resp.json()["skill_radar"]
        alpha = next(r for r in radar if r["category"] == "Alpha")
        assert alpha["score"] == 80.0
        assert alpha["confidence"] == 0.30
        assert alpha["is_preliminary"] is False
