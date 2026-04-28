"""
Tests for grading.services.skill_binding.bind_rubric_to_observations.

Covers the 8 behaviors documented in the task spec:
  1. Happy path: 4 criteria → 4 SkillObservations
  2. Score mapping: 1/2/3/4 → 25/50/75/100
  3. Missing Skill → skip gracefully (warning, no crash)
  4. Virtual Project: get_or_create per repo (reused on re-bind)
  5. Idempotency: re-run bind → observations updated in place, not duplicated
  6. Uses ai_draft_generated_at for created_at (not wall-clock now())
  7. No ai_draft_scores → returns 0, no crash
  8. Bind failure doesn't fail the view (generate_draft wraps in try/except)
"""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

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
from grading.services.skill_binding import bind_rubric_to_observations
from projects.models import Project
from skills.models import Skill, SkillCategory, SkillObservation
from users.models import Organization

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────
def _ensure_skill(slug: str, *, cat_slug: str = "codeq_sb"):
    cat, _ = SkillCategory.objects.get_or_create(
        slug=cat_slug, defaults={"name": cat_slug.upper(), "order": 0},
    )
    skill, _ = Skill.objects.get_or_create(
        slug=slug, defaults={"category": cat, "name": slug, "order": 0},
    )
    return skill


@pytest.fixture
def env(db):
    """Org, teacher, student, cohort, course, rubric, Submission, GradingSession, Evaluation linked."""
    org = Organization.objects.create(name="Test Org SB", slug="test-org-sb")
    teacher = User.objects.create_user(
        username="t_sb", email="t_sb@ex.com", password="pw",
        role="teacher", organization=org,
    )
    student = User.objects.create_user(
        username="s_sb", email="s_sb@ex.com", password="pw",
        role="developer", organization=org,
    )
    rubric = Rubric.objects.create(
        org=org, owner=teacher, name="R",
        criteria=[{"id": "readability", "name": "R", "weight": 1,
                   "levels": [{"score": 1}, {"score": 4}]}],
    )
    cohort = Cohort.objects.create(org=org, name="Klas SB")
    course = Course.objects.create(
        org=org, cohort=cohort, owner=teacher, name="Backend", rubric=rubric,
    )
    CohortMembership.objects.create(cohort=cohort, student=student)

    submission = Submission.objects.create(
        org=org, course=course, student=student,
        repo_full_name="acme/proj-sb", pr_number=1,
        pr_url="https://github.com/acme/proj-sb/pull/1",
        base_branch="main", head_branch="feat/sb",
    )
    session = GradingSession.objects.create(
        org=org, submission=submission, rubric=rubric,
        state=GradingSession.State.DRAFTED,
    )

    # Evaluation needs a Project — create a distinct one (different repo) so
    # we can tell the virtual-Project path later reuses the "acme/proj-sb"
    # one, not this eval-helper Project.
    eval_project = Project.objects.create(
        name="eval-helper", repo_owner="helper", repo_name="helper-repo",
        created_by=teacher,
    )
    evaluation = Evaluation.objects.create(
        project=eval_project, author=student,
        commit_sha="a" * 40, branch="feat/sb",
        author_name="s_sb", author_email="s_sb@ex.com",
    )
    SessionEvaluation.objects.create(
        grading_session=session, evaluation=evaluation,
    )

    # Seed the 4 rubric criterion Skills
    for slug in ["readability", "error_handling", "security", "testing"]:
        _ensure_skill(slug)

    return {
        "org": org, "teacher": teacher, "student": student,
        "rubric": rubric, "cohort": cohort, "course": course,
        "submission": submission, "session": session,
        "evaluation": evaluation,
    }


def _set_scores(session, scores: dict, *, generated_at=None):
    session.ai_draft_scores = {
        k: {"score": v, "evidence": "q"} for k, v in scores.items()
    }
    session.ai_draft_generated_at = generated_at or timezone.now()
    session.save(update_fields=["ai_draft_scores", "ai_draft_generated_at"])


# ─────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_happy_path_creates_four_observations(env):
    _set_scores(env["session"], {
        "readability": 3, "error_handling": 2, "security": 4, "testing": 1,
    })

    count = bind_rubric_to_observations(env["session"])

    assert count == 4
    assert SkillObservation.objects.filter(
        grading_session=env["session"], user=env["student"],
    ).count() == 4


@pytest.mark.django_db
@pytest.mark.parametrize("raw,expected_quality", [
    (1, 25.0), (2, 50.0), (3, 75.0), (4, 100.0),
])
def test_score_mapping(env, raw, expected_quality):
    _set_scores(env["session"], {"readability": raw})

    count = bind_rubric_to_observations(env["session"])

    assert count == 1
    obs = SkillObservation.objects.get(
        grading_session=env["session"], skill__slug="readability",
    )
    assert obs.quality_score == expected_quality


@pytest.mark.django_db
def test_missing_skill_skipped_gracefully(env):
    # Criterion id that doesn't match any Skill slug
    _set_scores(env["session"], {
        "readability": 3, "nonexistent_skill_xyz": 2,
    })

    count = bind_rubric_to_observations(env["session"])

    # One observation for readability; the unknown criterion is skipped.
    assert count == 1
    assert not SkillObservation.objects.filter(
        skill__slug="nonexistent_skill_xyz",
    ).exists()


@pytest.mark.django_db
def test_virtual_project_created_then_reused(env):
    # No Project for acme/proj-sb exists yet (eval-helper has a different repo).
    assert not Project.objects.filter(
        repo_owner="acme", repo_name="proj-sb",
    ).exists()

    _set_scores(env["session"], {"readability": 3})
    bind_rubric_to_observations(env["session"])

    # Virtual project created.
    assert Project.objects.filter(
        repo_owner="acme", repo_name="proj-sb",
    ).count() == 1

    # Re-bind — should reuse, not create a second row.
    _set_scores(env["session"], {"readability": 4})
    bind_rubric_to_observations(env["session"])
    assert Project.objects.filter(
        repo_owner="acme", repo_name="proj-sb",
    ).count() == 1


@pytest.mark.django_db
def test_idempotent_rebind_updates_in_place(env):
    _set_scores(env["session"], {"readability": 2})
    bind_rubric_to_observations(env["session"])
    assert SkillObservation.objects.filter(
        grading_session=env["session"],
    ).count() == 1
    obs_before = SkillObservation.objects.get(grading_session=env["session"])
    assert obs_before.quality_score == 50.0

    # Teacher regenerates draft with a new score.
    _set_scores(env["session"], {"readability": 4})
    bind_rubric_to_observations(env["session"])

    # Still exactly one row — quality_score updated in place.
    qs = SkillObservation.objects.filter(grading_session=env["session"])
    assert qs.count() == 1
    assert qs.get().quality_score == 100.0


@pytest.mark.django_db
def test_created_at_uses_ai_draft_generated_at(env):
    # Pick a timestamp in the past so we can tell it wasn't just now().
    past = timezone.now() - timedelta(days=3)
    _set_scores(env["session"], {"readability": 3}, generated_at=past)

    bind_rubric_to_observations(env["session"])

    obs = SkillObservation.objects.get(grading_session=env["session"])
    # SQLite datetime precision: allow a few microseconds of slack.
    assert abs((obs.created_at - past).total_seconds()) < 1.0


@pytest.mark.django_db
def test_empty_scores_returns_zero(env):
    env["session"].ai_draft_scores = {}
    env["session"].save(update_fields=["ai_draft_scores"])

    count = bind_rubric_to_observations(env["session"])

    assert count == 0
    assert SkillObservation.objects.filter(
        grading_session=env["session"],
    ).count() == 0


@pytest.mark.django_db
def test_bind_failure_does_not_break_caller(env):
    """
    Simulates the generate_draft view's try/except: even if bind explodes,
    the caller continues. We monkey-patch update_or_create to raise and
    assert the wrapper pattern (as used in views.py) swallows it.
    """
    _set_scores(env["session"], {"readability": 3})

    import logging
    log = logging.getLogger("grading.test")

    with patch(
        "skills.models.SkillObservation.objects.update_or_create",
        side_effect=RuntimeError("boom"),
    ):
        # Same pattern as views.py generate_draft after persisting the draft.
        try:
            bind_rubric_to_observations(env["session"])
        except Exception as e:  # noqa: BLE001
            log.warning("skill binding failed: %s", e)
            # The view's wrapper catches this — test passes as long as we
            # don't propagate the exception to the HTTP response path.

    # No observations created due to the raise.
    assert SkillObservation.objects.filter(
        grading_session=env["session"],
    ).count() == 0


@pytest.mark.django_db
def test_regrade_updates_skill_metric_bayesian_score(env):
    """
    Regression test for the B3 blocker found by the pre-pitch review:

    Before the fix, bind_rubric_to_observations only called
    SkillMetric.update_bayesian when SkillObservation.update_or_create
    returned `created=True`. On regrade (teacher regenerates a draft and
    the score changes) the observation row was updated in place but the
    metric's bayesian_score was never adjusted — so the radar showed
    the old score forever, even if the regrade went down.

    The fix replaces the create-only increment with a full replay via
    skills.services.metric_recompute.recompute_metric, which is the only
    correct strategy because update_bayesian is order-sensitive.

    This test pins the behavior: regrade with a worse score MUST move
    bayesian_score downward.
    """
    from skills.models import SkillMetric

    # First grade: score=4 (quality=100).
    _set_scores(env["session"], {"readability": 4})
    bind_rubric_to_observations(env["session"])

    metric = SkillMetric.objects.get(
        user=env["student"], skill__slug="readability",
    )
    high_score = metric.bayesian_score
    assert high_score > 50.0  # moved toward 100 from the 50 prior
    assert metric.observation_count == 1

    # Teacher regenerates the draft and rescores criterion to 1 (quality=25).
    _set_scores(env["session"], {"readability": 1})
    bind_rubric_to_observations(env["session"])

    metric.refresh_from_db()
    # The radar must now reflect the regrade — strictly lower than before.
    assert metric.bayesian_score < high_score, (
        f"regrade with worse score did not move bayesian_score down "
        f"(was {high_score}, now {metric.bayesian_score})"
    )
    # Replay starts from the prior, so observation_count is the count of
    # observations replayed, not cumulative across binds.
    assert metric.observation_count == 1


@pytest.mark.django_db
def test_regrade_no_double_count_on_observation_count(env):
    """
    Companion to the regrade test: re-binding the same session twice
    with the same scores must not inflate observation_count. The replay
    resets to 0 and counts the (deduped, update_or_create-driven) row
    set, so observation_count stays at 1 across N rebinds.
    """
    from skills.models import SkillMetric

    _set_scores(env["session"], {"readability": 3})
    bind_rubric_to_observations(env["session"])
    bind_rubric_to_observations(env["session"])
    bind_rubric_to_observations(env["session"])

    metric = SkillMetric.objects.get(
        user=env["student"], skill__slug="readability",
    )
    assert metric.observation_count == 1
