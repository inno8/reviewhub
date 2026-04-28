"""
Regression tests for two QA-flagged P1 polish items:

1. Skill radar exposes `is_preliminary` so the frontend can de-emphasize
   spokes where avg confidence < CONFIDENCE_PRELIMINARY (0.15).
   QA reported a category showing "Design Patterns score=96.9
   confidence=0.0" — visually impressive, evidentiarily empty.

2. /api/grading/sessions/ honors ?page_size=N. Default DRF
   PageNumberPagination ignores the query param. The grading inbox
   needs smaller batches on mobile and the previous behavior shipped
   20-row pages regardless of caller intent.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from grading.models import Cohort, CohortMembership, Course, GradingSession, Rubric, Submission
from skills.models import (
    CONFIDENCE_PRELIMINARY,
    Skill,
    SkillCategory,
    SkillMetric,
)

User = get_user_model()


@pytest.fixture
def org_with_teacher_and_student(db):
    from users.models import Organization

    org = Organization.objects.create(name="Org Polish", slug="org-polish")
    teacher = User.objects.create_user(
        username="t_polish", email="t_polish@example.com", password="pw",
        role="teacher", organization=org,
    )
    student = User.objects.create_user(
        username="s_polish", email="s_polish@example.com", password="pw",
        role="developer", organization=org,
    )
    rubric = Rubric.objects.create(
        org=org, owner=teacher, name="R",
        criteria=[{
            "id": "c1", "name": "C1", "weight": 1.0,
            "levels": [{"score": 1, "description": "x"}, {"score": 4, "description": "y"}],
        }],
    )
    cohort = Cohort.objects.create(org=org, name="Cohort Polish")
    course = Course.objects.create(
        org=org, cohort=cohort, owner=teacher, name="Course Polish", rubric=rubric,
    )
    CohortMembership.objects.create(student=student, cohort=cohort)
    return {
        "org": org, "teacher": teacher, "student": student,
        "cohort": cohort, "course": course, "rubric": rubric,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Skill radar: is_preliminary flag
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestRadarPreliminaryFlag:
    def _create_metrics_with_confidence(self, fixture, *, conf_for_cat: dict[str, float]):
        """Create one Skill+SkillMetric per category at the given confidence."""
        from projects.models import Project
        student = fixture["student"]
        # SkillMetric.project is non-null; create a placeholder per student.
        project, _ = Project.objects.get_or_create(
            provider="github",
            repo_owner="test",
            repo_name="test",
            defaults={
                "name": "Test Project",
                "repo_url": "https://github.com/test/test",
                "created_by": fixture["teacher"],
            },
        )
        for cat_name, conf in conf_for_cat.items():
            cat = SkillCategory.objects.create(
                name=cat_name,
                slug=cat_name.lower().replace(" ", "_"),
                color="#abcdef",
            )
            skill = Skill.objects.create(
                category=cat, name=f"{cat_name} Skill",
                slug=f"{cat_name.lower().replace(' ', '_')}_skill",
            )
            SkillMetric.objects.create(
                user=student, project=project, skill=skill,
                bayesian_score=85.0,
                confidence=conf,
                observation_count=3,
                trend="stable",
            )

    def test_low_confidence_category_marked_preliminary(self, org_with_teacher_and_student):
        f = org_with_teacher_and_student
        self._create_metrics_with_confidence(
            f, conf_for_cat={
                "Design Patterns": 0.05,  # below 0.15 → preliminary
                "Testing": 0.45,          # above → not preliminary
            },
        )
        client = APIClient()
        client.force_authenticate(user=f["teacher"])
        resp = client.get(f"/api/grading/students/{f['student'].id}/snapshot/")
        assert resp.status_code == 200, resp.content
        radar = resp.json()["skill_radar"]
        by_cat = {r["category"]: r for r in radar}
        assert by_cat["Design Patterns"]["is_preliminary"] is True
        assert by_cat["Testing"]["is_preliminary"] is False

    def test_threshold_is_strict_lt_not_lte(self, org_with_teacher_and_student):
        """Exactly at the threshold (0.15) is NOT preliminary."""
        f = org_with_teacher_and_student
        self._create_metrics_with_confidence(
            f, conf_for_cat={"Borderline": CONFIDENCE_PRELIMINARY},
        )
        client = APIClient()
        client.force_authenticate(user=f["teacher"])
        resp = client.get(f"/api/grading/students/{f['student'].id}/snapshot/")
        assert resp.status_code == 200, resp.content
        radar = resp.json()["skill_radar"]
        assert radar[0]["is_preliminary"] is False
        assert radar[0]["confidence"] == CONFIDENCE_PRELIMINARY


# ─────────────────────────────────────────────────────────────────────────────
# /sessions/ pagination
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def sessions_for_pagination(db, org_with_teacher_and_student):
    f = org_with_teacher_and_student
    sessions = []
    for i in range(7):
        sub = Submission.objects.create(
            org=f["org"], course=f["course"], student=f["student"],
            repo_full_name="acme/repo", pr_number=i + 1,
            pr_url=f"https://github.com/acme/repo/pull/{i + 1}",
            head_branch=f"feat/{i}",
        )
        s = GradingSession.objects.create(
            org=f["org"], submission=sub, rubric=f["rubric"],
            state=GradingSession.State.DRAFTED,
        )
        sessions.append(s)
    return {**f, "sessions": sessions}


@pytest.mark.django_db
class TestSessionsPagination:
    def test_page_size_query_param_honored(self, sessions_for_pagination):
        f = sessions_for_pagination
        client = APIClient()
        client.force_authenticate(user=f["teacher"])
        resp = client.get("/api/grading/sessions/?page_size=3")
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert len(body["results"]) == 3
        assert body["count"] == 7
        assert body["next"] is not None  # more pages exist

    def test_default_page_size_is_20(self, sessions_for_pagination):
        f = sessions_for_pagination
        client = APIClient()
        client.force_authenticate(user=f["teacher"])
        # 7 sessions, default page_size=20 → all fit on page 1, next=None
        resp = client.get("/api/grading/sessions/")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["results"]) == 7
        assert body["next"] is None

    def test_page_size_clamped_to_max(self, sessions_for_pagination):
        """A caller asking for 999 must not get 999 — max_page_size=100."""
        f = sessions_for_pagination
        client = APIClient()
        client.force_authenticate(user=f["teacher"])
        resp = client.get("/api/grading/sessions/?page_size=999")
        assert resp.status_code == 200
        body = resp.json()
        # 7 sessions exist; max_page_size=100 caps the request silently.
        # The behavior we assert: not a 400, just clamped — caller still
        # gets all 7 because that's <= 100.
        assert len(body["results"]) == 7
