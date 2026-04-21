"""
Tests for grading.services.skill_attribution — Workstream G.

Verifies per-contributor SkillObservation fan-out from a primary-author
observation via the post_save signal wired in grading/signals.py.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from grading.models import (
    Cohort,
    CohortMembership,
    Course,
    GradingSession,
    Rubric,
    SessionEvaluation,
    Submission,
    SubmissionContributor,
)

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────
# Shared test setup helpers
# ─────────────────────────────────────────────────────────────────────
def _seed_skill(slug="clean_code"):
    from skills.models import Skill, SkillCategory
    cat, _ = SkillCategory.objects.get_or_create(
        slug="code_quality_sa",
        defaults={"name": "Code Quality SA", "order": 0},
    )
    skill, _ = Skill.objects.get_or_create(
        slug=slug, defaults={"category": cat, "name": slug, "order": 0},
    )
    return skill


def _make_submission_with_contributors(*, fractions: list[float]):
    """
    Build a Submission wired to an Evaluation (via SessionEvaluation) with
    N contributors whose fractions are supplied. Returns
    (submission, contributors, evaluation, project).
    """
    from users.models import Organization
    from projects.models import Project, ProjectMember
    from evaluations.models import Evaluation

    n = len(fractions)
    assert n >= 1

    org = Organization.objects.create(
        name=f"SA Org {id(fractions)}", slug=f"sa-org-{id(fractions)}",
    )
    teacher = User.objects.create_user(
        username=f"sa_teacher_{id(fractions)}",
        email=f"sa_teach_{id(fractions)}@ex.com",
        password="pw", role="teacher", organization=org,
    )
    rubric = Rubric.objects.create(
        org=org, owner=teacher, name="R",
        criteria=[{"id": "r", "name": "R", "weight": 1,
                   "levels": [{"score": 1}, {"score": 4}]}],
    )
    cohort = Cohort.objects.create(org=org, name="C")
    course = Course.objects.create(
        org=org, cohort=cohort, owner=teacher, name="Course", rubric=rubric,
    )

    students = []
    for i in range(n):
        s = User.objects.create_user(
            username=f"sa_stu_{id(fractions)}_{i}",
            email=f"stu_{id(fractions)}_{i}@ex.com",
            password="pw", role="developer", organization=org,
        )
        CohortMembership.objects.create(cohort=cohort, student=s)
        students.append(s)

    project = Project.objects.create(
        name=f"Proj {id(fractions)}",
        repo_owner="team",
        repo_name=f"proj-{id(fractions)}",
        created_by=students[0],
    )
    ProjectMember.objects.create(
        project=project, user=students[0], role="owner",
        git_email=students[0].email,
    )

    submission = Submission.objects.create(
        org=org, course=course, student=students[0],
        repo_full_name=f"team/proj-{id(fractions)}",
        pr_number=1,
        pr_url=f"https://github.com/team/proj-{id(fractions)}/pull/1",
        head_branch="feat",
    )

    # Create contributor links.
    contribs = []
    for i, (s, frac) in enumerate(zip(students, fractions)):
        link = SubmissionContributor.objects.create(
            submission=submission, user=s,
            is_primary_author=(i == 0),
            contribution_fraction=frac,
        )
        contribs.append(link)

    evaluation = Evaluation.objects.create(
        project=project, author=students[0], commit_sha="sha-sa",
        branch="main", author_name=students[0].username,
        author_email=students[0].email,
        overall_score=80.0, status="completed", files_changed=1,
    )

    # Wire Evaluation → GradingSession (required for the signal to walk back).
    session = GradingSession.objects.create(
        org=org, submission=submission, rubric=rubric,
        state=GradingSession.State.DRAFTED,
    )
    SessionEvaluation.objects.create(
        grading_session=session, evaluation=evaluation,
    )

    return {
        "submission": submission,
        "contributors": contribs,
        "students": students,
        "evaluation": evaluation,
        "project": project,
        "session": session,
    }


def _make_primary_observation(ctx, *, weighted_score=70.0):
    """Create the primary-author SkillObservation the way evaluations/ would."""
    from skills.models import SkillObservation
    skill = _seed_skill()
    return SkillObservation.objects.create(
        user=ctx["students"][0],
        project=ctx["project"],
        evaluation=ctx["evaluation"],
        skill=skill,
        commit_sha="sha-sa",
        quality_score=weighted_score,
        complexity_weight=1.0,
        weighted_score=weighted_score,
        lines_changed=100,
        issue_count=1,
        critical_count=0, warning_count=1, info_count=0, suggestion_count=0,
        decision_appropriate=0, decision_suboptimal=0, decision_poor=0,
    )


# ─────────────────────────────────────────────────────────────────────
# Single contributor — no fan-out
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestSingleContributor:
    def test_solo_contributor_keeps_full_weight(self):
        from skills.models import SkillObservation
        ctx = _make_submission_with_contributors(fractions=[1.0])
        obs = _make_primary_observation(ctx, weighted_score=70.0)

        all_obs = SkillObservation.objects.filter(evaluation=ctx["evaluation"])
        assert all_obs.count() == 1  # No fan-out because only 1 contributor.
        obs.refresh_from_db()
        assert obs.weighted_score == 70.0


# ─────────────────────────────────────────────────────────────────────
# Two contributors 50/50
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestTwoContributorsEqualSplit:
    def test_two_contributors_half_weight_each(self):
        from skills.models import SkillObservation
        ctx = _make_submission_with_contributors(fractions=[0.5, 0.5])
        _make_primary_observation(ctx, weighted_score=80.0)

        all_obs = list(
            SkillObservation.objects.filter(evaluation=ctx["evaluation"])
        )
        assert len(all_obs) == 2
        by_user = {o.user_id: o for o in all_obs}
        for stu in ctx["students"]:
            assert stu.id in by_user
            assert abs(by_user[stu.id].weighted_score - 40.0) < 0.1


# ─────────────────────────────────────────────────────────────────────
# Three contributors 60/30/10
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestThreeContributorsWeighted:
    def test_three_contributors_weighted_fractions(self):
        from skills.models import SkillObservation
        ctx = _make_submission_with_contributors(fractions=[0.6, 0.3, 0.1])
        _make_primary_observation(ctx, weighted_score=100.0)

        all_obs = {
            o.user_id: o
            for o in SkillObservation.objects.filter(evaluation=ctx["evaluation"])
        }
        assert len(all_obs) == 3
        expected = [60.0, 30.0, 10.0]
        for stu, exp in zip(ctx["students"], expected):
            assert abs(all_obs[stu.id].weighted_score - exp) < 0.2, (
                f"expected ~{exp} for {stu.email}, got {all_obs[stu.id].weighted_score}"
            )


# ─────────────────────────────────────────────────────────────────────
# Fractions sum invariant
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestFractionSumInvariant:
    @pytest.mark.parametrize("fractions", [
        [1.0],
        [0.5, 0.5],
        [0.4, 0.3, 0.3],
        [0.25, 0.25, 0.25, 0.25],
    ])
    def test_sum_of_weighted_scores_matches_original(self, fractions):
        from skills.models import SkillObservation
        ctx = _make_submission_with_contributors(fractions=fractions)
        original_score = 100.0
        _make_primary_observation(ctx, weighted_score=original_score)

        obs_list = list(
            SkillObservation.objects.filter(evaluation=ctx["evaluation"])
        )
        total = sum(o.weighted_score for o in obs_list)
        # Fan-out should preserve the total weighted credit within rounding.
        assert abs(total - original_score) < 1.0, (
            f"fractions={fractions}, got total={total}"
        )


# ─────────────────────────────────────────────────────────────────────
# Defensive: no contributors (pre-grading evaluation)
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestDefensiveNoContributors:
    def test_observation_without_grading_session_is_unchanged(self):
        """
        If a SkillObservation is created for an Evaluation that has no
        SessionEvaluation (no grading yet), the signal must be a no-op.
        """
        from skills.models import SkillObservation
        from projects.models import Project, ProjectMember
        from evaluations.models import Evaluation

        user = User.objects.create_user(
            username="lonely_g", email="lonely@ex.com", password="pw",
        )
        project = Project.objects.create(
            name="LonelyProj", repo_owner="u", repo_name="p", created_by=user,
        )
        ProjectMember.objects.create(
            project=project, user=user, role="owner", git_email=user.email,
        )
        evaluation = Evaluation.objects.create(
            project=project, author=user, commit_sha="loner",
            branch="main", author_name="u", author_email=user.email,
            overall_score=80.0, status="completed", files_changed=1,
        )
        skill = _seed_skill("clean_code_alone")
        obs = SkillObservation.objects.create(
            user=user, project=project, evaluation=evaluation, skill=skill,
            commit_sha="loner", quality_score=70.0, complexity_weight=1.0,
            weighted_score=70.0, lines_changed=10, issue_count=0,
        )
        # Still exactly one observation, weight unchanged.
        assert SkillObservation.objects.filter(evaluation=evaluation).count() == 1
        obs.refresh_from_db()
        assert obs.weighted_score == 70.0


# ─────────────────────────────────────────────────────────────────────
# Reentrancy: the signal must not recurse when creating synthetic rows
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestSignalReentrancy:
    def test_synthetic_rows_do_not_fan_out_further(self):
        from skills.models import SkillObservation
        ctx = _make_submission_with_contributors(fractions=[0.5, 0.5])
        _make_primary_observation(ctx, weighted_score=50.0)
        # 2 contributors → exactly 2 SkillObservations for this evaluation.
        # If the signal had recursed, we would see >2.
        assert SkillObservation.objects.filter(evaluation=ctx["evaluation"]).count() == 2
