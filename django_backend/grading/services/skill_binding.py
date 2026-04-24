"""
Bind rubric grading results to SkillObservation rows.

v1: each criterion in the rubric maps 1:1 to a Skill (by slug). The 1-4
criterion score is mapped to a 0-100 quality_score. Runs after
rubric_grader.generate_draft saves ai_draft_scores on the GradingSession.

Design decisions (v1 pragmas — documented in the commit that added this):

  * Virtual Project pattern. SkillObservation.project is a non-nullable FK
    to the legacy projects.Project model. The new Leera grading flow has
    no Project — it centres on Cohort/Course/Submission. Rather than make
    project nullable (ripples through evaluations/*), we get_or_create a
    "virtual" Project per (repo_owner, repo_name) and reuse it across all
    grading sessions for that repo. Document this so readers aren't
    surprised to see Projects appearing for repos that no one ever set up
    via the legacy UI.

  * Representative Evaluation. SkillObservation.evaluation is also a
    non-nullable FK. We pick the most recent SessionEvaluation linked to
    this GradingSession (the latest commit in the PR). If the session has
    no linked Evaluations, binding is a no-op and logs a warning — the
    webhook path always creates at least one, so this only fires if the
    session was hand-crafted.

  * Idempotency. The new (nullable) skills.SkillObservation.grading_session
    FK lets us `update_or_create` on (grading_session, user, skill) so
    re-running after a draft regeneration updates in place instead of
    duplicating. Observations created before this FK existed (legacy
    evaluations-app writes) are untouched.

  * Failure isolation. The calling view wraps bind_rubric_to_observations
    in try/except — a failure here must never break the grading flow.
"""
from __future__ import annotations

import logging
from typing import Iterable

from django.db import transaction

log = logging.getLogger(__name__)


# Map 1-4 rubric score → 0-100 quality_score.
# 1 (poor) → 25, 2 (below) → 50, 3 (good) → 75, 4 (excellent) → 100.
_SCORE_TO_QUALITY = {1: 25.0, 2: 50.0, 3: 75.0, 4: 100.0}


def _map_score(raw) -> float | None:
    """Map a 1-4 rubric score to a 0-100 quality_score, or None if invalid."""
    try:
        as_int = int(raw)
    except (TypeError, ValueError):
        return None
    return _SCORE_TO_QUALITY.get(as_int)


def _get_or_create_virtual_project(submission):
    """
    Backwards-compatible shim — the real implementation lives in
    grading.services.virtual_project so the grading webhook can share it.
    """
    from grading.services.virtual_project import get_or_create_virtual_project

    return get_or_create_virtual_project(submission)


def _pick_representative_evaluation(grading_session):
    """Most-recent Evaluation linked to the session, or None."""
    link = (
        grading_session.session_evaluations
        .select_related("evaluation")
        .order_by("-evaluation__created_at")
        .first()
    )
    return link.evaluation if link else None


def bind_rubric_to_observations(grading_session) -> int:
    """
    Create/update SkillObservation rows for each rubric criterion in the
    GradingSession's ai_draft_scores.

    Returns the count of observations created or updated. Returns 0
    (without raising) on any of:
      * grading_session.ai_draft_scores is empty / falsy
      * no Skill matches a criterion slug (per-criterion skip, warning)
      * no Evaluation linked to the session (entire binding skipped)
    """
    from skills.models import Skill, SkillMetric, SkillObservation

    scores = grading_session.ai_draft_scores or {}
    if not scores:
        return 0

    submission = grading_session.submission
    student = submission.student

    evaluation = _pick_representative_evaluation(grading_session)
    if evaluation is None:
        log.warning(
            "skill_binding: session=%s has no linked Evaluation, skipping",
            grading_session.id,
        )
        return 0

    project = _get_or_create_virtual_project(submission)

    # Prefer the timestamp when the draft actually finished; fall back to now.
    generated_at = grading_session.ai_draft_generated_at
    commit_sha = (evaluation.commit_sha or "")[:40]

    count = 0
    with transaction.atomic():
        for criterion_id, detail in scores.items():
            # Detail may be {"score": int, "evidence": "..."} or a bare int.
            if isinstance(detail, dict):
                raw = detail.get("score")
            else:
                raw = detail
            quality = _map_score(raw)
            if quality is None:
                log.info(
                    "skill_binding: criterion=%s score=%r not mappable, skipping",
                    criterion_id, raw,
                )
                continue

            try:
                skill = Skill.objects.get(slug=criterion_id)
            except Skill.DoesNotExist:
                log.warning(
                    "skill_binding: no Skill for slug=%s (session=%s), skipping",
                    criterion_id, grading_session.id,
                )
                continue

            defaults = {
                "user": student,
                "project": project,
                "evaluation": evaluation,
                "skill": skill,
                "commit_sha": commit_sha,
                "quality_score": quality,
                "complexity_weight": 1.0,
            }
            obs, created = SkillObservation.objects.update_or_create(
                grading_session=grading_session,
                user=student,
                skill=skill,
                defaults=defaults,
            )
            # Pin created_at to the draft generation time so trajectory views
            # plot by when the grading happened, not when binding ran.
            if generated_at and obs.created_at != generated_at:
                SkillObservation.objects.filter(pk=obs.pk).update(
                    created_at=generated_at
                )

            # Fold this observation into the Bayesian rollup so the student
            # snapshot, per-criterion bars, and trajectory chart pick it up.
            # Only on NEWLY-created observations: if a draft regenerates and
            # update_or_create returns existing, skipping prevents
            # double-counting against observation_count.
            #
            # Caveat: the legacy bind_existing_rubric_observations management
            # command + the seed_dogfood_cohort flow do their own metric
            # rollup explicitly. This in-line update covers the live webhook
            # → grading → binding path that previously left
            # SkillMetric.observation_count at 0 (visible bug: tester's
            # /grading/students/5 profile rendered as empty radar even after
            # multiple POSTED sessions).
            if created:
                try:
                    metric, _ = SkillMetric.objects.get_or_create(
                        user=student,
                        project=project,
                        skill=skill,
                        defaults={"score": 50.0},
                    )
                    metric.update_bayesian(quality, 1.0)
                except Exception as e:
                    # Never break the grading flow on a metric-rollup hiccup.
                    log.warning(
                        "skill_binding: SkillMetric rollup failed user=%s skill=%s: %s",
                        student.id, skill.slug, e,
                    )
            count += 1

    log.info(
        "skill_binding: session=%s bound %d observations",
        grading_session.id, count,
    )
    return count
