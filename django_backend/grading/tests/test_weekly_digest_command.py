"""
Workstream I1 — send_weekly_digest management command tests.

Uses Django's locmem email backend (auto-enabled under pytest-django) to
verify the command populates `mail.outbox` with the expected subject and
body content.
"""
from __future__ import annotations

from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from grading.models import (
    Cohort, Course, GradingSession, Rubric, Submission,
)

User = get_user_model()


@pytest.fixture
def seeded_world(db):
    from users.models import Organization

    org = Organization.objects.create(name="Digest Org", slug="digest-org")
    teacher = User.objects.create_user(
        username="digest_teacher", email="digest_teacher@ex.com", password="pw",
        role="teacher", organization=org,
    )
    student = User.objects.create_user(
        username="digest_student", email="digest_student@ex.com", password="pw",
        role="developer", organization=org,
    )
    cohort = Cohort.objects.create(org=org, name="Digest Cohort")
    rubric = Rubric.objects.create(org=org, owner=teacher, name="R")
    course = Course.objects.create(
        org=org, cohort=cohort, owner=teacher, name="Digest Course", rubric=rubric,
    )
    submission = Submission.objects.create(
        org=org, course=course, student=student,
        repo_full_name="x/y", pr_number=99,
        pr_url="https://github.com/x/y/pull/99",
        head_branch="feat",
    )
    GradingSession.objects.create(
        org=org, submission=submission, rubric=rubric,
        state=GradingSession.State.POSTED,
        ai_draft_generated_at=timezone.now() - timedelta(hours=1),
        posted_at=timezone.now() - timedelta(hours=1),
        docent_review_time_seconds=240,
    )
    return {"org": org}


@pytest.mark.django_db
def test_command_sends_email_with_subject_and_body(seeded_world):
    out = StringIO()
    call_command("send_weekly_metrics_digest", "--email=ops@example.com", stdout=out)

    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert "ops@example.com" in msg.to
    assert "Digest Org" in msg.subject
    assert "Weekly Report" in msg.subject
    # Plaintext body has the report
    assert "Digest Org" in msg.body
    assert "Sessions started" in msg.body
    # HTML alternative attached
    assert any(ct == "text/html" for _, ct in msg.alternatives)


@pytest.mark.django_db
def test_command_no_recipients_is_idempotent_noop(seeded_world, monkeypatch):
    monkeypatch.delenv("WEEKLY_DIGEST_RECIPIENTS", raising=False)
    out = StringIO()
    call_command("send_weekly_metrics_digest", stdout=out)
    assert len(mail.outbox) == 0
    assert "No recipients" in out.getvalue()
