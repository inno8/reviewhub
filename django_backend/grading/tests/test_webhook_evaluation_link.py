"""
Tests for Evaluation + SessionEvaluation creation in the grading webhook.

The webhook used to create just Submission + GradingSession. Without a
linked Evaluation, skill_binding (which needs SessionEvaluation →
Evaluation) silently returned 0 and SkillObservations never got written.
These tests lock in the new behavior:

  1. Webhook creates Submission + GradingSession + Evaluation + SessionEvaluation
  2. Webhook redelivery (same delivery_id) doesn't create duplicate Evaluations
  3. A second PR on the same repo creates a distinct Evaluation (different commit)
  4. Two PRs on the same repo reuse the same virtual Project
  5. backfill_evaluation_links creates links + SkillObservations for legacy sessions
  6. backfill_evaluation_links is idempotent (re-run is a no-op)
"""
from __future__ import annotations

import json

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from io import StringIO
from rest_framework.test import APIClient

from evaluations.models import Evaluation
from grading.models import (
    Cohort,
    CohortMembership,
    Course,
    GradingSession,
    Rubric,
    SessionEvaluation,
    Submission,
)
from projects.models import Project
from skills.models import Skill, SkillCategory, SkillObservation
from users.models import Organization

User = get_user_model()


# ── fixtures ────────────────────────────────────────────────────────
@pytest.fixture
def membership(db):
    org = Organization.objects.create(name="Evl Org", slug="evl-org")
    teacher = User.objects.create_user(
        username="t_evl", email="t_evl@ex.com", password="pw",
        role="teacher", organization=org,
    )
    student = User.objects.create_user(
        username="s_evl", email="s_evl@ex.com", password="pw",
        role="developer", organization=org,
    )
    rubric = Rubric.objects.create(
        org=org, owner=teacher, name="R-evl",
        criteria=[
            {"id": "readability", "name": "R", "weight": 1,
             "levels": [{"score": 1}, {"score": 4}]}
        ],
    )
    cohort = Cohort.objects.create(org=org, name="Evl Klas")
    Course.objects.create(
        org=org, cohort=cohort, owner=teacher,
        name="Evl Backend", rubric=rubric,
    )
    m = CohortMembership.objects.create(
        cohort=cohort, student=student,
        student_repo_url="https://github.com/s_evl/assignment-evl",
    )
    return m


def _make_payload(*, pr_number: int = 1, sha: str = "sha-abc-123",
                  repo: str = "s_evl/assignment-evl", action: str = "opened"):
    return {
        "action": action,
        "number": pr_number,
        "pull_request": {
            "number": pr_number, "state": "open", "merged": False,
            "title": f"PR {pr_number} title",
            "html_url": f"https://github.com/{repo}/pull/{pr_number}",
            "head": {"ref": f"feat/pr{pr_number}", "sha": sha},
            "base": {"ref": "main"},
            "user": {"login": "s_evl"},
        },
        "repository": {
            "full_name": repo,
            "html_url": f"https://github.com/{repo}",
        },
    }


def _post(client: APIClient, payload: dict, delivery_id: str = "d-1"):
    return client.post(
        "/api/grading/webhooks/github/",
        data=json.dumps(payload).encode(),
        content_type="application/json",
        HTTP_X_GITHUB_DELIVERY=delivery_id,
        HTTP_X_GITHUB_EVENT="pull_request",
    )


# ── tests ───────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_webhook_creates_evaluation_and_link(membership):
    """PR opened → Submission + GradingSession + Evaluation + SessionEvaluation all exist."""
    client = APIClient()
    resp = _post(client, _make_payload(pr_number=42, sha="deadbeef"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["matched"] is True

    submission = Submission.objects.get(pr_number=42)
    session = GradingSession.objects.get(submission=submission)

    # Evaluation created
    evaluation = Evaluation.objects.get(commit_sha="deadbeef")
    assert evaluation.author_id == membership.student_id
    assert evaluation.project.repo_owner == "s_evl"
    assert evaluation.project.repo_name == "assignment-evl"

    # SessionEvaluation link
    link = SessionEvaluation.objects.get(grading_session=session)
    assert link.evaluation_id == evaluation.id


@pytest.mark.django_db
def test_webhook_redelivery_is_idempotent(membership):
    """Second POST with same delivery_id: no duplicate Evaluations."""
    client = APIClient()
    payload = _make_payload(pr_number=7, sha="samesha")
    _post(client, payload, delivery_id="dup-1")
    n_evals_after_first = Evaluation.objects.count()
    n_links_after_first = SessionEvaluation.objects.count()

    # Same delivery_id → webhook dedupe short-circuits
    resp = _post(client, payload, delivery_id="dup-1")
    assert resp.status_code == 200
    assert resp.json().get("deduped") is True

    assert Evaluation.objects.count() == n_evals_after_first
    assert SessionEvaluation.objects.count() == n_links_after_first


@pytest.mark.django_db
def test_second_pr_creates_distinct_evaluation(membership):
    """Two PRs on the same repo → two distinct Evaluations (different commit_sha)."""
    client = APIClient()
    _post(client, _make_payload(pr_number=1, sha="sha-one"), delivery_id="d-pr1")
    _post(client, _make_payload(pr_number=2, sha="sha-two"), delivery_id="d-pr2")

    assert Evaluation.objects.filter(commit_sha="sha-one").count() == 1
    assert Evaluation.objects.filter(commit_sha="sha-two").count() == 1
    assert SessionEvaluation.objects.count() == 2


@pytest.mark.django_db
def test_two_prs_share_virtual_project(membership):
    """Two PRs on the same repo reuse the same virtual Project row."""
    client = APIClient()
    _post(client, _make_payload(pr_number=1, sha="aa"), delivery_id="dp-1")
    _post(client, _make_payload(pr_number=2, sha="bb"), delivery_id="dp-2")

    projects = Project.objects.filter(
        repo_owner="s_evl", repo_name="assignment-evl",
    )
    assert projects.count() == 1
    # Both evaluations point at that single project.
    assert Evaluation.objects.filter(project=projects.first()).count() == 2


@pytest.mark.django_db
def test_backfill_creates_links_and_observations(membership):
    """
    Legacy session (created before webhook wrote links) → backfill command
    creates the Evaluation + SessionEvaluation and runs skill_binding to
    populate SkillObservations.
    """
    # Hand-build a legacy session: Submission + GradingSession, NO Evaluation.
    org = membership.cohort.org
    course = Course.objects.get(cohort=membership.cohort)
    submission = Submission.objects.create(
        org=org, course=course, student=membership.student,
        repo_full_name="s_evl/assignment-evl", pr_number=999,
        pr_url="https://github.com/s_evl/assignment-evl/pull/999",
        pr_title="Legacy PR", base_branch="main", head_branch="feat/legacy",
    )
    from django.utils import timezone
    session = GradingSession.objects.create(
        org=org, submission=submission, rubric=course.rubric,
        state=GradingSession.State.DRAFTED,
        ai_draft_scores={"readability": {"score": 3, "evidence": "ok"}},
        ai_draft_generated_at=timezone.now(),
    )
    # Ensure the Skill for the criterion exists (skill_binding lookup).
    cat, _ = SkillCategory.objects.get_or_create(
        slug="codeq_evl", defaults={"name": "CQ", "order": 0},
    )
    Skill.objects.get_or_create(
        slug="readability",
        defaults={"category": cat, "name": "Readability", "order": 0},
    )

    assert SessionEvaluation.objects.filter(grading_session=session).count() == 0

    out = StringIO()
    call_command("backfill_evaluation_links", stdout=out)

    # Evaluation + link now exist.
    assert SessionEvaluation.objects.filter(grading_session=session).count() == 1
    assert Evaluation.objects.filter(author=membership.student).count() == 1

    # SkillObservation populated.
    obs = SkillObservation.objects.filter(
        grading_session=session, user=membership.student, skill__slug="readability",
    )
    assert obs.count() == 1
    assert obs.first().quality_score == 75.0  # 3 → 75


@pytest.mark.django_db
def test_backfill_is_idempotent(membership):
    """Re-running backfill produces no new Evaluations or links."""
    org = membership.cohort.org
    course = Course.objects.get(cohort=membership.cohort)
    submission = Submission.objects.create(
        org=org, course=course, student=membership.student,
        repo_full_name="s_evl/assignment-evl", pr_number=501,
        pr_url="https://github.com/s_evl/assignment-evl/pull/501",
        pr_title="Re-run PR", base_branch="main", head_branch="feat/rerun",
    )
    GradingSession.objects.create(
        org=org, submission=submission, rubric=course.rubric,
        state=GradingSession.State.PENDING,
    )

    out = StringIO()
    call_command("backfill_evaluation_links", stdout=out)

    evals_after_first = Evaluation.objects.count()
    links_after_first = SessionEvaluation.objects.count()

    call_command("backfill_evaluation_links", stdout=StringIO())

    assert Evaluation.objects.count() == evals_after_first
    assert SessionEvaluation.objects.count() == links_after_first
