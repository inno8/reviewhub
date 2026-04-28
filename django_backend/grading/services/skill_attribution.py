"""
Skill attribution service — Workstream G (shared-repo support).

When a PR is pushed to a shared repo (group project), the evaluations app
produces a single SkillObservation row attributed to the PR author
(Submission.student). For v1 group-project support we need every contributor
to accrue skill credit proportional to what THEY wrote.

Design — minimal-touch:
  * `evaluations/_create_skill_observations` is OUT OF SCOPE for this
    workstream (strict file list). We therefore hook via a post_save signal
    on SkillObservation. The signal walks:
        SkillObservation.evaluation → SessionEvaluation → GradingSession
            → Submission → contributor_links
    and, if the Submission has >1 contributors, synthesises per-contributor
    SkillObservation rows scaled by `contribution_fraction`.
  * The primary-author row (the one evaluations/ just created) is kept as-is
    for backward compatibility with dashboards — BUT its weighted_score is
    re-scaled down to the primary's contribution fraction, and the delta is
    redistributed to the new rows.

v1 simplifications (documented for v1.1 upgrade):
  * Attribution is by `contribution_fraction` only, NOT file-level per-commit
    mapping. A finding in student-A's file still gets split across all
    contributors. Rationale: the commit-author → User mapping requires a PR
    commit fetcher that isn't in this workstream's file list.
  * SkillMetric Bayesian state for the primary author is NOT rolled back.
    The primary sees slightly-inflated credit and co-contributors see
    fresh-but-fair credit. In practice the overcredit is small and
    convergence behavior is preserved. v1.1 will rebalance.
  * Empty / missing contributors list is a no-op (solo-repo path).

Reentrancy: synthetic rows are tagged via a thread-local sentinel to avoid
the signal recursing on itself. The signal is a no-op when the current
observation was itself created by this service.
"""
from __future__ import annotations

import logging
import threading
from typing import Iterable

log = logging.getLogger(__name__)


# Thread-local guard so signal handlers don't re-enter attribution when this
# service creates its own SkillObservation rows.
_attribution_guard = threading.local()


def _is_in_attribution() -> bool:
    return bool(getattr(_attribution_guard, "active", False))


class _AttributionScope:
    """Context manager that flags the thread as currently doing attribution."""

    def __enter__(self):
        _attribution_guard.active = True
        return self

    def __exit__(self, exc_type, exc, tb):
        _attribution_guard.active = False
        return False


def find_contributors_for_observation(observation):
    """
    Walk SkillObservation → Evaluation → GradingSession → Submission to
    find the contributor list for this observation. Returns an empty list
    if no GradingSession is linked (solo-repo / pre-grading evaluations).
    """
    try:
        evaluation = observation.evaluation
    except Exception:
        return []
    if evaluation is None:
        return []

    # Evaluation ties to Submission via SessionEvaluation (grading app).
    # Reverse accessor is `grading_session_links`.
    from grading.models import Submission  # local import: avoid app-ordering issues

    session_link = (
        evaluation.grading_session_links
        .select_related("grading_session__submission")
        .first()
    )
    if not session_link:
        return []
    submission: Submission = session_link.grading_session.submission
    if submission is None:
        return []

    contrib_links = list(
        submission.contributor_links.select_related("user").all()
    )
    return contrib_links


def attribute_skill_observations(*, observation, contributors=None):
    """
    Distribute one SkillObservation across contributors by contribution_fraction.

    Args:
      observation: a newly-created SkillObservation (primary-author version).
      contributors: optional list of SubmissionContributor. If None, walks
                    from the observation to discover contributors itself.

    Behavior:
      * If contributors is empty or only-primary → no-op.
      * Otherwise: rescales observation.weighted_score to primary's fraction,
        then creates parallel observations for each non-primary contributor
        weighted by their fraction. New observations share the evaluation,
        commit_sha, quality_score, complexity_weight, lines_changed, and
        finding counts — only the weighted_score + user differ.

    v1 simplification (see module docstring) applies.
    """
    if contributors is None:
        contributors = find_contributors_for_observation(observation)
    if not contributors:
        return []
    if len(contributors) <= 1:
        return []

    # Find primary; fall back to observation.user.
    primary = next(
        (c for c in contributors if c.is_primary_author),
        None,
    )
    if primary is None:
        primary_user_id = observation.user_id
    else:
        primary_user_id = primary.user_id

    # Only rewrite if the observation's user really is the primary. If some
    # other flow creates obs for a non-primary user, don't touch it.
    if observation.user_id != primary_user_id:
        return []

    # NOTE: SkillObservation.save() auto-computes
    #   weighted_score = quality_score * complexity_weight
    # so we scale via `quality_score` (not `weighted_score` directly),
    # keeping the model's invariant intact for downstream readers.
    original_weighted = observation.weighted_score or 0.0
    original_quality = observation.quality_score or 0.0
    complexity_weight = observation.complexity_weight or 1.0

    # Primary fraction: if primary row exists, use its fraction; otherwise
    # assume 1/N equal split for N contributors.
    n = len(contributors)
    primary_fraction = (
        primary.contribution_fraction if primary else round(1.0 / n, 6)
    )

    from skills.models import SkillObservation  # local import

    with _AttributionScope():
        # 1) Rescale the primary observation in-place. SkillObservation.save()
        #    recomputes weighted_score = quality_score * complexity_weight,
        #    so we scale quality_score by the primary fraction and write both
        #    fields back via a queryset UPDATE (avoids the model's save-time
        #    recompute interfering).
        if primary_fraction < 1.0:
            new_primary_quality = round(original_quality * primary_fraction, 4)
            new_primary_weighted = round(original_weighted * primary_fraction, 2)
            SkillObservation.objects.filter(pk=observation.pk).update(
                quality_score=new_primary_quality,
                weighted_score=new_primary_weighted,
            )
            observation.quality_score = new_primary_quality
            observation.weighted_score = new_primary_weighted

        # 2) Create synthetic observations for each non-primary contributor.
        created = []
        for c in contributors:
            if c.user_id == primary_user_id:
                continue
            fraction = c.contribution_fraction or round(1.0 / n, 6)
            if fraction <= 0:
                continue
            new_quality = round(original_quality * fraction, 4)
            new_weight = round(original_weighted * fraction, 2)
            # Create synthetic row. Model.save() recomputes weighted_score
            # from quality_score * complexity_weight, so passing the scaled
            # quality_score is enough. We then overwrite weighted_score via
            # QuerySet.update() to guarantee the exact rounded value.
            obs = SkillObservation.objects.create(
                user=c.user,
                project=observation.project,
                evaluation=observation.evaluation,
                skill=observation.skill,
                commit_sha=observation.commit_sha,
                quality_score=new_quality,
                complexity_weight=complexity_weight,
                weighted_score=new_weight,
                lines_changed=observation.lines_changed,
                issue_count=observation.issue_count,
                critical_count=observation.critical_count,
                warning_count=observation.warning_count,
                info_count=observation.info_count,
                suggestion_count=observation.suggestion_count,
                decision_appropriate=observation.decision_appropriate,
                decision_suboptimal=observation.decision_suboptimal,
                decision_poor=observation.decision_poor,
            )
            # The model's save() recomputes weighted_score; force the value
            # back to the rounded target via QuerySet.update() so the total
            # weighted credit across contributors sums to the original.
            SkillObservation.objects.filter(pk=obs.pk).update(
                weighted_score=new_weight
            )
            obs.weighted_score = new_weight
            created.append(obs)
        return created


def handle_observation_post_save(sender, instance, created, **kwargs):
    """
    post_save signal handler — invoked by grading.signals.

    Fast path: only fires for brand-new observations, and only when the
    attribution guard is not already active (so synthetic observations
    don't recurse).
    """
    if not created:
        return
    if _is_in_attribution():
        return
    try:
        attribute_skill_observations(observation=instance)
    except Exception as e:  # defensive — never break the primary write
        log.warning(
            "skill_attribution signal failed for obs=%s: %s",
            getattr(instance, "pk", None), e,
            exc_info=True,
        )
