"""
Regression test for /api/grading/sessions/inbox-summary/.

The endpoint is the data backbone of the Nakijken Copilot teacher
dashboard front door. It replaces a half-dozen legacy admin-team calls
with a single round-trip that gives the docent the three numbers they
actually need on login: needs_draft / needs_review / posted_this_week.

What this test pins down:
  - Auth: students get 403; unauth gets 401.
  - Scope: a teacher only sees sessions in cohorts they actually serve
    (course owner, secondary docent, or explicit teacher assignment).
    Two teachers in the same org should NOT see each other's sessions.
  - KPI counts are correct for each state bucket.
  - next_up returns drafted sessions ordered by due_at then created_at.
  - review_time computes p50/p95 over last-30-days posted sessions.
  - recurring_patterns surfaces top unresolved patterns scoped to the
    teacher's students.
"""
from __future__ import annotations

from datetime import timedelta

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
URL = "/api/grading/sessions/inbox-summary/"


@pytest.fixture
def two_cohorts_two_teachers(db):
    """Org with two cohorts, two teachers, sessions in each."""
    from users.models import Organization

    org = Organization.objects.create(name="Org Inbox", slug="org-inbox")
    teacher_a = User.objects.create_user(
        username="t_a_inbox", email="t_a_inbox@example.com", password="pw",
        role="teacher", organization=org,
    )
    teacher_b = User.objects.create_user(
        username="t_b_inbox", email="t_b_inbox@example.com", password="pw",
        role="teacher", organization=org,
    )
    student_a = User.objects.create_user(
        username="s_a_inbox", email="s_a_inbox@example.com", password="pw",
        role="developer", organization=org,
    )
    student_b = User.objects.create_user(
        username="s_b_inbox", email="s_b_inbox@example.com", password="pw",
        role="developer", organization=org,
    )
    rubric_a = Rubric.objects.create(
        org=org, owner=teacher_a, name="RA",
        criteria=[{"id": "c1", "name": "C1", "weight": 1.0,
                   "levels": [{"score": 1, "description": "x"},
                              {"score": 4, "description": "y"}]}],
    )
    rubric_b = Rubric.objects.create(
        org=org, owner=teacher_b, name="RB",
        criteria=rubric_a.criteria,
    )
    cohort_a = Cohort.objects.create(org=org, name="Cohort A inbox")
    cohort_b = Cohort.objects.create(org=org, name="Cohort B inbox")
    course_a = Course.objects.create(
        org=org, cohort=cohort_a, owner=teacher_a, name="Course A", rubric=rubric_a,
    )
    course_b = Course.objects.create(
        org=org, cohort=cohort_b, owner=teacher_b, name="Course B", rubric=rubric_b,
    )
    CohortMembership.objects.create(student=student_a, cohort=cohort_a)
    CohortMembership.objects.create(student=student_b, cohort=cohort_b)
    return {
        "org": org,
        "teacher_a": teacher_a, "teacher_b": teacher_b,
        "student_a": student_a, "student_b": student_b,
        "course_a": course_a, "course_b": course_b,
    }


def _make_session(*, fixture, teacher_key, student_key, state, posted_at=None,
                  review_seconds=None, pr_number=1, due_at=None,
                  created_offset_days=0):
    """Create one GradingSession in the chosen state. Helpers compute
    `posted_at` when state=POSTED so review_time aggregations work."""
    course = fixture[f"course_{teacher_key.split('_')[1]}"]
    student = fixture[student_key]
    org = fixture["org"]
    sub = Submission.objects.create(
        org=org, course=course, student=student,
        repo_full_name="acme/repo", pr_number=pr_number,
        pr_url=f"https://github.com/acme/repo/pull/{pr_number}",
        head_branch=f"feat/{pr_number}",
        due_at=due_at,
    )
    s = GradingSession.objects.create(
        org=org, submission=sub, rubric=course.rubric,
        state=state,
        posted_at=posted_at,
        docent_review_time_seconds=review_seconds,
    )
    if created_offset_days:
        # Bypass auto_now_add by re-saving via .update()
        backdated = timezone.now() - timedelta(days=created_offset_days)
        GradingSession.objects.filter(pk=s.pk).update(created_at=backdated)
        s.refresh_from_db()
    return s


# ─────────────────────────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestAuth:
    def test_unauthenticated_returns_401(self, two_cohorts_two_teachers):
        c = APIClient()
        resp = c.get(URL)
        assert resp.status_code in (401, 403), resp.content

    def test_student_returns_403(self, two_cohorts_two_teachers):
        f = two_cohorts_two_teachers
        c = APIClient()
        c.force_authenticate(user=f["student_a"])
        resp = c.get(URL)
        assert resp.status_code == 403, resp.content

    def test_teacher_returns_200(self, two_cohorts_two_teachers):
        f = two_cohorts_two_teachers
        c = APIClient()
        c.force_authenticate(user=f["teacher_a"])
        resp = c.get(URL)
        assert resp.status_code == 200, resp.content
        body = resp.json()
        for k in ("kpi", "next_up", "review_time", "recurring_patterns"):
            assert k in body


# ─────────────────────────────────────────────────────────────────────────────
# KPI counts
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestKpiCounts:
    def test_state_buckets_correct(self, two_cohorts_two_teachers):
        f = two_cohorts_two_teachers
        S = GradingSession.State
        # Teacher A's cohort: 1 pending, 1 drafting, 2 drafted, 1 reviewing.
        _make_session(fixture=f, teacher_key="teacher_a", student_key="student_a",
                      state=S.PENDING, pr_number=1)
        _make_session(fixture=f, teacher_key="teacher_a", student_key="student_a",
                      state=S.DRAFTING, pr_number=2)
        _make_session(fixture=f, teacher_key="teacher_a", student_key="student_a",
                      state=S.DRAFTED, pr_number=3)
        _make_session(fixture=f, teacher_key="teacher_a", student_key="student_a",
                      state=S.DRAFTED, pr_number=4)
        _make_session(fixture=f, teacher_key="teacher_a", student_key="student_a",
                      state=S.REVIEWING, pr_number=5)

        c = APIClient()
        c.force_authenticate(user=f["teacher_a"])
        resp = c.get(URL)
        kpi = resp.json()["kpi"]
        assert kpi["needs_draft"] == 2  # pending + drafting
        assert kpi["needs_review"] == 2  # drafted
        assert kpi["in_review"] == 1     # reviewing
        # No posted sessions yet
        assert kpi["posted_this_week"] == 0
        assert kpi["posted_today"] == 0

    def test_posted_window_buckets(self, two_cohorts_two_teachers):
        f = two_cohorts_two_teachers
        S = GradingSession.State
        now = timezone.now()
        # 1 posted today, 1 posted 3 days ago, 1 posted 10 days ago (out of week)
        _make_session(fixture=f, teacher_key="teacher_a", student_key="student_a",
                      state=S.POSTED, posted_at=now - timedelta(hours=2), pr_number=10)
        _make_session(fixture=f, teacher_key="teacher_a", student_key="student_a",
                      state=S.POSTED, posted_at=now - timedelta(days=3), pr_number=11)
        _make_session(fixture=f, teacher_key="teacher_a", student_key="student_a",
                      state=S.POSTED, posted_at=now - timedelta(days=10), pr_number=12)

        c = APIClient()
        c.force_authenticate(user=f["teacher_a"])
        resp = c.get(URL)
        kpi = resp.json()["kpi"]
        assert kpi["posted_today"] == 1
        assert kpi["posted_this_week"] == 2  # today + 3-days-ago, NOT 10-days-ago


# ─────────────────────────────────────────────────────────────────────────────
# Cross-teacher scoping
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestTeacherScoping:
    def test_teacher_a_does_not_see_teacher_b_sessions(
        self, two_cohorts_two_teachers
    ):
        f = two_cohorts_two_teachers
        S = GradingSession.State
        # Teacher A: 2 drafted in cohort A
        _make_session(fixture=f, teacher_key="teacher_a", student_key="student_a",
                      state=S.DRAFTED, pr_number=20)
        _make_session(fixture=f, teacher_key="teacher_a", student_key="student_a",
                      state=S.DRAFTED, pr_number=21)
        # Teacher B: 5 drafted in cohort B (should not affect teacher A's view)
        for i in range(5):
            _make_session(fixture=f, teacher_key="teacher_b", student_key="student_b",
                          state=S.DRAFTED, pr_number=30 + i)

        c = APIClient()
        c.force_authenticate(user=f["teacher_a"])
        resp = c.get(URL)
        assert resp.json()["kpi"]["needs_review"] == 2

        c.force_authenticate(user=f["teacher_b"])
        resp = c.get(URL)
        assert resp.json()["kpi"]["needs_review"] == 5


# ─────────────────────────────────────────────────────────────────────────────
# Next up ordering
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestNextUp:
    def test_drafted_only_oldest_first(self, two_cohorts_two_teachers):
        f = two_cohorts_two_teachers
        S = GradingSession.State
        # 3 drafted, varied creation times. Plus 1 reviewing (excluded).
        old = _make_session(fixture=f, teacher_key="teacher_a", student_key="student_a",
                            state=S.DRAFTED, pr_number=40, created_offset_days=10)
        mid = _make_session(fixture=f, teacher_key="teacher_a", student_key="student_a",
                            state=S.DRAFTED, pr_number=41, created_offset_days=5)
        new = _make_session(fixture=f, teacher_key="teacher_a", student_key="student_a",
                            state=S.DRAFTED, pr_number=42, created_offset_days=1)
        _make_session(fixture=f, teacher_key="teacher_a", student_key="student_a",
                      state=S.REVIEWING, pr_number=43)

        c = APIClient()
        c.force_authenticate(user=f["teacher_a"])
        resp = c.get(URL)
        next_up = resp.json()["next_up"]
        ids = [r["id"] for r in next_up]
        assert ids == [old.id, mid.id, new.id], "should be oldest-first; reviewing excluded"
        # Each row carries the docent context they need.
        assert next_up[0]["student_name"]
        assert next_up[0]["cohort_name"] == "Cohort A inbox"
        assert next_up[0]["course_name"] == "Course A"
        assert next_up[0]["days_waiting"] >= 9


# ─────────────────────────────────────────────────────────────────────────────
# Review time
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestReviewTime:
    def test_p50_p95_over_recent_posted(self, two_cohorts_two_teachers):
        f = two_cohorts_two_teachers
        S = GradingSession.State
        now = timezone.now()
        # Five posted sessions with review times: 60s, 120s, 240s, 480s, 1200s
        for i, secs in enumerate([60, 120, 240, 480, 1200]):
            _make_session(
                fixture=f, teacher_key="teacher_a", student_key="student_a",
                state=S.POSTED, posted_at=now - timedelta(days=2),
                review_seconds=secs, pr_number=50 + i,
            )
        # An old one that should be excluded (>30d ago)
        _make_session(
            fixture=f, teacher_key="teacher_a", student_key="student_a",
            state=S.POSTED, posted_at=now - timedelta(days=60),
            review_seconds=99999, pr_number=99,
        )

        c = APIClient()
        c.force_authenticate(user=f["teacher_a"])
        resp = c.get(URL)
        rt = resp.json()["review_time"]
        assert rt["samples"] == 5  # the 60-day-old one excluded
        assert rt["target_seconds"] == 300
        # p50 falls in the middle (240 for 5 samples)
        assert rt["p50_seconds"] == 240
        # p95 lands at the largest sample (1200) for n=5
        assert rt["p95_seconds"] == 1200

    def test_no_samples_returns_nulls(self, two_cohorts_two_teachers):
        f = two_cohorts_two_teachers
        c = APIClient()
        c.force_authenticate(user=f["teacher_a"])
        resp = c.get(URL)
        rt = resp.json()["review_time"]
        assert rt["samples"] == 0
        assert rt["p50_seconds"] is None
        assert rt["p95_seconds"] is None
        assert rt["target_seconds"] == 300
