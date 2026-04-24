"""
Replay-based SkillMetric recomputation.

Why this exists
---------------
SkillMetric.bayesian_score is a running Bayesian estimate updated by
`update_bayesian()`. Each call is *order-sensitive* (learning rate decays
with confidence), so you can't "undo" a single observation — you have to
replay the whole history from the prior (50.0 uncertain).

This module centralizes that replay so multiple callers don't reimplement
it (skill_binding live path, the recompute_skill_metrics_from_observations
management command, and seed_dogfood_cohort which has its own variant).

Contract
--------
`recompute_metric(user, project, skill)` resets SkillMetric.bayesian_score
to the 50.0 prior and replays every SkillObservation row in chronological
order. Idempotent. Returns (metric, replayed_count).

Failure isolation
-----------------
Caller decides. The live grading path (skill_binding) wraps this in a
try/except so a rollup hiccup doesn't break the grading flow. Management
commands let it raise.
"""
from __future__ import annotations

import logging
from typing import Tuple

log = logging.getLogger(__name__)


def recompute_metric(user, project, skill) -> Tuple["object", int]:
    """
    Reset and replay the SkillMetric for one (user, project, skill) tuple.

    Returns (SkillMetric, observation_count_replayed).
    """
    from skills.models import SkillMetric, SkillObservation

    metric, _created = SkillMetric.objects.get_or_create(
        user=user,
        project=project,
        skill=skill,
        defaults={"score": 50.0},
    )

    # Reset to the uncertain prior. bayesian_score is NOT NULL, so we use
    # 50.0 instead of None. update_bayesian will overwrite this as it
    # replays observations.
    metric.score = 50.0
    metric.bayesian_score = 50.0
    metric.confidence = 0.0
    metric.observation_count = 0
    metric.save(update_fields=[
        "score",
        "bayesian_score",
        "confidence",
        "observation_count",
    ])

    obs_qs = (
        SkillObservation.objects
        .filter(user=user, skill=skill, project=project)
        .order_by("created_at", "id")
    )

    count = 0
    for obs in obs_qs:
        # Recompute weighted from quality × complexity rather than reading
        # the stored `weighted_score` field. SkillObservation.save() has a
        # known limitation: when called via Django's update_or_create with
        # `update_fields=`, the in-memory recomputation of weighted_score
        # (from the save() override) does not propagate to the DB because
        # weighted_score isn't in update_fields. So a stale weighted_score
        # can survive a quality_score change. Recomputing here makes the
        # rollup independent of that quirk.
        quality = obs.quality_score if obs.quality_score is not None else 50.0
        weight = obs.complexity_weight if obs.complexity_weight else 1.0
        weighted = quality * weight
        metric.update_bayesian(weighted, weight)
        count += 1

    return metric, count
