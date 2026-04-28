"""
Scope B2 — GradingSession.template_hit_rate property.

The property is computed at read time from `ai_draft_comments`, so there
is no migration. It returns the share of draft comments that were served
by a template (flagged by the ai_engine draft generator).
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from grading.models import (
    Cohort, Course, GradingSession, Rubric, Submission,
)

User = get_user_model()


@pytest.fixture
def grading_scaffold(db):
    from users.models import Organization

    org = Organization.objects.create(name="B2 Hit Rate Org", slug="b2-hitrate-org")
    teacher = User.objects.create_user(
        username="t_b2hr", email="t_b2hr@ex.com", password="pw",
        role="teacher", organization=org,
    )
    student = User.objects.create_user(
        username="s_b2hr", email="s_b2hr@ex.com", password="pw",
        role="developer", organization=org,
    )
    cohort = Cohort.objects.create(org=org, name="B2HR Cohort")
    rubric = Rubric.objects.create(org=org, owner=teacher, name="R")
    course = Course.objects.create(
        org=org, cohort=cohort, owner=teacher, name="Course", rubric=rubric,
    )
    submission = Submission.objects.create(
        org=org, course=course, student=student,
        repo_full_name="x/y", pr_number=1,
        pr_url="https://github.com/x/y/pull/1",
        head_branch="feat",
    )
    return {
        "org": org, "teacher": teacher, "student": student,
        "cohort": cohort, "rubric": rubric, "course": course,
        "submission": submission,
    }


@pytest.mark.django_db
def test_template_hit_rate_is_zero_with_no_comments(grading_scaffold):
    session = GradingSession.objects.create(
        org=grading_scaffold["org"],
        submission=grading_scaffold["submission"],
        rubric=grading_scaffold["rubric"],
    )
    assert session.template_hit_rate == 0.0


@pytest.mark.django_db
def test_template_hit_rate_counts_served_by_template_flag(grading_scaffold):
    session = GradingSession.objects.create(
        org=grading_scaffold["org"],
        submission=grading_scaffold["submission"],
        rubric=grading_scaffold["rubric"],
        ai_draft_comments=[
            {"file": "a.py", "line": 1, "body": "x", "served_by_template": True},
            {"file": "a.py", "line": 2, "body": "y", "served_by_template": True},
            {"file": "a.py", "line": 3, "body": "z"},  # LLM-served
            {"file": "a.py", "line": 4, "body": "w", "served_by_template": False},
        ],
    )
    assert session.template_hit_rate == pytest.approx(2 / 4)


@pytest.mark.django_db
def test_template_hit_rate_handles_malformed_entries(grading_scaffold):
    """Non-dict entries shouldn't crash the property."""
    session = GradingSession.objects.create(
        org=grading_scaffold["org"],
        submission=grading_scaffold["submission"],
        rubric=grading_scaffold["rubric"],
        ai_draft_comments=[
            {"served_by_template": True},
            "garbage-string",
            None,
        ],
    )
    # 1 hit out of 3 entries; malformed still count toward denominator.
    assert session.template_hit_rate == pytest.approx(1 / 3)
