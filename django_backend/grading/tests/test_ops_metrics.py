"""
Workstream I1 — weekly metrics endpoint tests.

Covers permission matrix (admin/superuser/teacher/student/anon), period
parsing defaults, empty-period safety, send-rate math, null review time
handling, and multi-org aggregation for superusers.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from grading.models import (
    Cohort, Course, GradingSession, LLMCostLog, Rubric, Submission,
)

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _make_session(
    *, org, course, student, state, in_period: bool = True, review_seconds=None,
    pr_number=1, template_hits=0, total_comments=0,
):
    now = timezone.now()
    when = now - timedelta(days=1) if in_period else now - timedelta(days=30)

    submission = Submission.objects.create(
        org=org, course=course, student=student,
        repo_full_name=f"x/y{pr_number}", pr_number=pr_number,
        pr_url=f"https://github.com/x/y/pull/{pr_number}",
        head_branch="feat",
    )
    rubric = course.rubric
    comments = []
    for i in range(total_comments):
        comments.append({
            "file": "a.py", "line": i + 1, "body": f"c{i}",
            "served_by_template": i < template_hits,
        })
    session = GradingSession.objects.create(
        org=org,
        submission=submission,
        rubric=rubric,
        state=state,
        ai_draft_generated_at=when,
        ai_draft_comments=comments,
        docent_review_time_seconds=review_seconds,
        posted_at=when if state == GradingSession.State.POSTED else None,
    )
    return session


@pytest.fixture
def two_org_world(db):
    from users.models import Organization

    org_a = Organization.objects.create(name="Org A", slug="org-i1-a")
    org_b = Organization.objects.create(name="Org B", slug="org-i1-b")

    teacher_a = User.objects.create_user(
        username="i1_teacher_a", email="i1_teacher_a@ex.com", password="pw",
        role="teacher", organization=org_a,
    )
    teacher_b = User.objects.create_user(
        username="i1_teacher_b", email="i1_teacher_b@ex.com", password="pw",
        role="teacher", organization=org_b,
    )
    admin_a = User.objects.create_user(
        username="i1_admin_a", email="i1_admin_a@ex.com", password="pw",
        role="admin", organization=org_a,
    )
    student_a = User.objects.create_user(
        username="i1_student_a", email="i1_student_a@ex.com", password="pw",
        role="developer", organization=org_a,
    )
    student_b = User.objects.create_user(
        username="i1_student_b", email="i1_student_b@ex.com", password="pw",
        role="developer", organization=org_b,
    )
    superuser = User.objects.create_user(
        username="i1_super", email="i1_super@ex.com", password="pw",
        role="admin", is_superuser=True, is_staff=True,
    )

    cohort_a = Cohort.objects.create(org=org_a, name="Cohort A1")
    cohort_b = Cohort.objects.create(org=org_b, name="Cohort B1")
    rubric_a = Rubric.objects.create(org=org_a, owner=teacher_a, name="RA")
    rubric_b = Rubric.objects.create(org=org_b, owner=teacher_b, name="RB")
    course_a = Course.objects.create(
        org=org_a, cohort=cohort_a, owner=teacher_a, name="CA", rubric=rubric_a,
    )
    course_b = Course.objects.create(
        org=org_b, cohort=cohort_b, owner=teacher_b, name="CB", rubric=rubric_b,
    )

    return {
        "org_a": org_a, "org_b": org_b,
        "teacher_a": teacher_a, "teacher_b": teacher_b,
        "admin_a": admin_a, "student_a": student_a, "student_b": student_b,
        "superuser": superuser,
        "cohort_a": cohort_a, "cohort_b": cohort_b,
        "course_a": course_a, "course_b": course_b,
    }


URL = "/api/grading/ops/metrics/weekly/"


# ─────────────────────────────────────────────────────────────────────────────
# Permission tests
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_anonymous_gets_401():
    client = APIClient()
    resp = client.get(URL)
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_teacher_gets_403(two_org_world):
    client = APIClient()
    client.force_authenticate(user=two_org_world["teacher_a"])
    resp = client.get(URL)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_student_gets_403(two_org_world):
    client = APIClient()
    client.force_authenticate(user=two_org_world["student_a"])
    resp = client.get(URL)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_admin_sees_only_own_org(two_org_world):
    # One session in each org
    _make_session(
        org=two_org_world["org_a"], course=two_org_world["course_a"],
        student=two_org_world["student_a"],
        state=GradingSession.State.POSTED, review_seconds=300, pr_number=1,
    )
    _make_session(
        org=two_org_world["org_b"], course=two_org_world["course_b"],
        student=two_org_world["student_b"],
        state=GradingSession.State.POSTED, review_seconds=600, pr_number=2,
    )

    client = APIClient()
    client.force_authenticate(user=two_org_world["admin_a"])
    resp = client.get(URL)
    assert resp.status_code == 200, resp.content
    body = resp.json()

    org_ids = [o["org_id"] for o in body["orgs"]]
    assert two_org_world["org_a"].id in org_ids
    assert two_org_world["org_b"].id not in org_ids


@pytest.mark.django_db
def test_superuser_sees_all_orgs(two_org_world):
    _make_session(
        org=two_org_world["org_a"], course=two_org_world["course_a"],
        student=two_org_world["student_a"],
        state=GradingSession.State.POSTED, review_seconds=120, pr_number=1,
    )
    _make_session(
        org=two_org_world["org_b"], course=two_org_world["course_b"],
        student=two_org_world["student_b"],
        state=GradingSession.State.POSTED, review_seconds=120, pr_number=2,
    )

    client = APIClient()
    client.force_authenticate(user=two_org_world["superuser"])
    resp = client.get(URL)
    assert resp.status_code == 200
    body = resp.json()
    org_ids = {o["org_id"] for o in body["orgs"]}
    assert {two_org_world["org_a"].id, two_org_world["org_b"].id} <= org_ids


# ─────────────────────────────────────────────────────────────────────────────
# Shape + defaults
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_default_period_is_last_7_days(two_org_world):
    client = APIClient()
    client.force_authenticate(user=two_org_world["superuser"])
    resp = client.get(URL)
    assert resp.status_code == 200
    body = resp.json()
    today = timezone.localdate()
    assert body["period"]["end"] == today.isoformat()
    assert body["period"]["start"] == (today - timedelta(days=7)).isoformat()


@pytest.mark.django_db
def test_custom_period_respected(two_org_world):
    client = APIClient()
    client.force_authenticate(user=two_org_world["superuser"])
    resp = client.get(URL, {"start": "2026-01-01", "end": "2026-01-15"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["period"] == {"start": "2026-01-01", "end": "2026-01-15"}


@pytest.mark.django_db
def test_empty_period_returns_zero_counts(two_org_world):
    client = APIClient()
    client.force_authenticate(user=two_org_world["admin_a"])
    resp = client.get(URL)
    assert resp.status_code == 200
    body = resp.json()
    # Admin always sees their own org (even if empty)
    assert any(o["org_id"] == two_org_world["org_a"].id for o in body["orgs"])
    assert body["grand_totals"]["sessions_started"] == 0
    assert body["grand_totals"]["sessions_sent"] == 0
    assert body["grand_totals"]["llm_cost_eur"] == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Math
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_send_rate_math_three_of_five(two_org_world):
    # 5 started, 3 POSTED in period
    for i in range(3):
        _make_session(
            org=two_org_world["org_a"], course=two_org_world["course_a"],
            student=two_org_world["student_a"],
            state=GradingSession.State.POSTED, review_seconds=120,
            pr_number=100 + i,
        )
    for i in range(2):
        _make_session(
            org=two_org_world["org_a"], course=two_org_world["course_a"],
            student=two_org_world["student_a"],
            state=GradingSession.State.DRAFTED, review_seconds=None,
            pr_number=200 + i,
        )

    client = APIClient()
    client.force_authenticate(user=two_org_world["admin_a"])
    resp = client.get(URL)
    body = resp.json()
    org_row = next(o for o in body["orgs"] if o["org_id"] == two_org_world["org_a"].id)
    cohort_row = next(
        c for c in org_row["cohorts"]
        if c["cohort_id"] == two_org_world["cohort_a"].id
    )
    assert cohort_row["sessions_started"] == 5
    assert cohort_row["sessions_sent"] == 3
    assert cohort_row["send_rate"] == 0.6


@pytest.mark.django_db
def test_review_time_handles_nulls(two_org_world):
    # Two POSTED — one with time, one with None.
    _make_session(
        org=two_org_world["org_a"], course=two_org_world["course_a"],
        student=two_org_world["student_a"],
        state=GradingSession.State.POSTED, review_seconds=300,
        pr_number=301,
    )
    _make_session(
        org=two_org_world["org_a"], course=two_org_world["course_a"],
        student=two_org_world["student_a"],
        state=GradingSession.State.POSTED, review_seconds=None,
        pr_number=302,
    )

    client = APIClient()
    client.force_authenticate(user=two_org_world["admin_a"])
    body = client.get(URL).json()
    cohort_row = body["orgs"][0]["cohorts"][0]
    # Avg uses only the one non-null → 5.0 minutes.
    assert cohort_row["avg_review_time_minutes"] == 5.0
    assert cohort_row["median_review_time_minutes"] == 5.0


@pytest.mark.django_db
def test_no_review_times_yields_null(two_org_world):
    # One started session, not posted → review time metrics None.
    _make_session(
        org=two_org_world["org_a"], course=two_org_world["course_a"],
        student=two_org_world["student_a"],
        state=GradingSession.State.DRAFTED, review_seconds=None,
        pr_number=401,
    )

    client = APIClient()
    client.force_authenticate(user=two_org_world["admin_a"])
    body = client.get(URL).json()
    cohort_row = body["orgs"][0]["cohorts"][0]
    assert cohort_row["avg_review_time_minutes"] is None
    assert cohort_row["median_review_time_minutes"] is None


@pytest.mark.django_db
def test_grand_totals_aggregate_across_orgs(two_org_world):
    # Org A: 2 posted, 1 drafted. Org B: 1 posted.
    for i in range(2):
        _make_session(
            org=two_org_world["org_a"], course=two_org_world["course_a"],
            student=two_org_world["student_a"],
            state=GradingSession.State.POSTED, review_seconds=60,
            pr_number=500 + i,
        )
    _make_session(
        org=two_org_world["org_a"], course=two_org_world["course_a"],
        student=two_org_world["student_a"],
        state=GradingSession.State.DRAFTED, review_seconds=None,
        pr_number=600,
    )
    _make_session(
        org=two_org_world["org_b"], course=two_org_world["course_b"],
        student=two_org_world["student_b"],
        state=GradingSession.State.POSTED, review_seconds=60,
        pr_number=700,
    )

    client = APIClient()
    client.force_authenticate(user=two_org_world["superuser"])
    body = client.get(URL).json()
    assert body["grand_totals"]["sessions_started"] == 4
    assert body["grand_totals"]["sessions_sent"] == 3
    assert body["grand_totals"]["orgs_active"] == 2


@pytest.mark.django_db
def test_cost_aggregation(two_org_world):
    session = _make_session(
        org=two_org_world["org_a"], course=two_org_world["course_a"],
        student=two_org_world["student_a"],
        state=GradingSession.State.POSTED, review_seconds=60,
        pr_number=800,
    )
    LLMCostLog.objects.create(
        org=two_org_world["org_a"], docent=two_org_world["teacher_a"],
        course=two_org_world["course_a"], grading_session=session,
        tier="premium", model_name="gpt-5", cost_eur=Decimal("1.23"),
    )
    LLMCostLog.objects.create(
        org=two_org_world["org_a"], docent=two_org_world["teacher_a"],
        course=two_org_world["course_a"], grading_session=session,
        tier="cheap", model_name="gpt-5-nano", cost_eur=Decimal("0.77"),
    )

    client = APIClient()
    client.force_authenticate(user=two_org_world["admin_a"])
    body = client.get(URL).json()
    org_row = body["orgs"][0]
    assert org_row["totals"]["llm_cost_eur"] == 2.0
    cohort_row = org_row["cohorts"][0]
    assert cohort_row["llm_cost_eur"] == 2.0
    assert cohort_row["llm_cost_per_session_eur"] == 2.0


@pytest.mark.django_db
def test_teachers_active_counted_distinct(two_org_world):
    # Two sessions, same teacher (course_a.owner) → teachers_active=1.
    for i in range(2):
        _make_session(
            org=two_org_world["org_a"], course=two_org_world["course_a"],
            student=two_org_world["student_a"],
            state=GradingSession.State.POSTED, review_seconds=60,
            pr_number=900 + i,
        )

    client = APIClient()
    client.force_authenticate(user=two_org_world["admin_a"])
    body = client.get(URL).json()
    org_row = body["orgs"][0]
    assert org_row["totals"]["teachers_active"] == 1
    assert org_row["cohorts"][0]["teachers_active"] == 1


@pytest.mark.django_db
def test_template_hit_rate_averaged(two_org_world):
    # Session A: 2/4 templated = 0.5
    _make_session(
        org=two_org_world["org_a"], course=two_org_world["course_a"],
        student=two_org_world["student_a"],
        state=GradingSession.State.POSTED, review_seconds=60,
        pr_number=1000, template_hits=2, total_comments=4,
    )
    # Session B: 0/2 = 0.0
    _make_session(
        org=two_org_world["org_a"], course=two_org_world["course_a"],
        student=two_org_world["student_a"],
        state=GradingSession.State.POSTED, review_seconds=60,
        pr_number=1001, template_hits=0, total_comments=2,
    )

    client = APIClient()
    client.force_authenticate(user=two_org_world["admin_a"])
    body = client.get(URL).json()
    cohort_row = body["orgs"][0]["cohorts"][0]
    # Average of 0.5 and 0.0 = 0.25
    assert cohort_row["template_hit_rate"] == 0.25


@pytest.mark.django_db
def test_out_of_period_sessions_excluded(two_org_world):
    # One session in period, one 30 days ago.
    _make_session(
        org=two_org_world["org_a"], course=two_org_world["course_a"],
        student=two_org_world["student_a"],
        state=GradingSession.State.POSTED, review_seconds=60,
        pr_number=1100, in_period=True,
    )
    _make_session(
        org=two_org_world["org_a"], course=two_org_world["course_a"],
        student=two_org_world["student_a"],
        state=GradingSession.State.POSTED, review_seconds=60,
        pr_number=1101, in_period=False,
    )

    client = APIClient()
    client.force_authenticate(user=two_org_world["admin_a"])
    body = client.get(URL).json()
    org_row = body["orgs"][0]
    assert org_row["totals"]["sessions_started"] == 1


@pytest.mark.django_db
def test_invalid_date_param_400(two_org_world):
    client = APIClient()
    client.force_authenticate(user=two_org_world["superuser"])
    resp = client.get(URL, {"start": "not-a-date"})
    assert resp.status_code == 400
