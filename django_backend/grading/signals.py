"""
Grading signal wiring — Workstream G.

Registers a post_save handler on skills.SkillObservation so that
shared-repo (group-project) PRs split per-primary-author observations
across all contributors by contribution_fraction.

We sit on the skills app's signal rather than adding hooks inside
evaluations/views.py because this workstream is deliberately scoped
to `grading/` and may not touch evaluations/.
"""
from __future__ import annotations

from django.apps import apps as django_apps
from django.db.models.signals import post_save


def connect_signals():
    """
    Called from GradingConfig.ready(). Imports are deferred here so the
    skills app is fully registered before we attach the handler.
    """
    # Local imports avoid AppRegistryNotReady at module-import time.
    from grading.services.skill_attribution import handle_observation_post_save

    SkillObservation = django_apps.get_model("skills", "SkillObservation")
    post_save.connect(
        handle_observation_post_save,
        sender=SkillObservation,
        dispatch_uid="grading.shared_repo.attribution",
    )
