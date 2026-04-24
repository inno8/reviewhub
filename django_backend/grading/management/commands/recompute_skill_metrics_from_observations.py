"""
backfill_skill_metrics — recompute SkillMetric.bayesian_score from existing
SkillObservation rows.

Why this exists
---------------
Before commit X (the live-flow rollup fix in
grading/services/skill_binding.py), the webhook → grading → skill_binding
pipeline created SkillObservation rows but did NOT call
SkillMetric.update_bayesian. Result: students whose data only came through
that path had observation_count=0 on every metric, which made their
StudentSnapshotView radar + per-criterion bars + trajectory render empty
even when they had completed multiple POSTED grading sessions.

The dogfood seeders (`seed_dogfood_cohort`, etc.) ran their own rollup
explicitly so seeded students were unaffected — but `tester@reviewhub.com`
and any future live-flow user hit the bug.

What this does
--------------
For every (user, skill) pair that has at least one SkillObservation:

1. Reset the SkillMetric to its prior (score=50.0, bayesian_score=None,
   observation_count=0, confidence=0).
2. Iterate the user's observations for that skill in chronological order
   and call SkillMetric.update_bayesian per observation.
3. Save.

Idempotent. Re-running produces identical metrics regardless of how many
times you've run it before.

Usage
-----
    python manage.py backfill_skill_metrics                    # all users
    python manage.py backfill_skill_metrics --user tester@x.io # one user
    python manage.py backfill_skill_metrics --dry-run          # preview
"""
from __future__ import annotations

from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = (
        "Recompute SkillMetric.bayesian_score from SkillObservation rows. "
        "Fixes empty radars / per-criterion bars when the live grading "
        "flow's rollup wasn't wired up yet."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            help="Limit to a single user by email. Default: all users with observations.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print the plan without writing to the DB.",
        )

    def handle(self, *args, **opts):
        from django.contrib.auth import get_user_model
        from skills.models import SkillMetric, SkillObservation

        User = get_user_model()
        dry = opts["dry_run"]

        # ── target users ──
        if opts.get("user"):
            users_qs = User.objects.filter(email__iexact=opts["user"])
            if not users_qs.exists():
                self.stdout.write(
                    self.style.WARNING(f"No user with email {opts['user']!r}")
                )
                return
        else:
            user_ids = (
                SkillObservation.objects
                .values_list("user_id", flat=True)
                .distinct()
            )
            users_qs = User.objects.filter(pk__in=user_ids)

        total_users = 0
        total_metrics = 0
        total_observations = 0

        for user in users_qs.order_by("email"):
            obs_qs = (
                SkillObservation.objects
                .filter(user=user)
                .select_related("skill", "project")
                .order_by("created_at", "id")
            )
            if not obs_qs.exists():
                continue

            # Group observations per (skill, project) — SkillMetric is unique
            # on (user, project, skill).
            grouped: dict[tuple[int, int], list[SkillObservation]] = defaultdict(list)
            for obs in obs_qs:
                grouped[(obs.skill_id, obs.project_id)].append(obs)

            self.stdout.write(
                f"\n[{user.email}] observations={obs_qs.count()} "
                f"unique (skill,project) groups={len(grouped)}"
            )
            total_users += 1

            if dry:
                for (skill_id, project_id), obs_list in grouped.items():
                    skill_slug = obs_list[0].skill.slug
                    self.stdout.write(
                        f"  [dry] would replay {len(obs_list)} obs into "
                        f"metric (skill={skill_slug}, project={project_id})"
                    )
                continue

            for (skill_id, project_id), obs_list in grouped.items():
                with transaction.atomic():
                    metric, _created = SkillMetric.objects.get_or_create(
                        user=user,
                        project_id=project_id,
                        skill_id=skill_id,
                        defaults={"score": 50.0},
                    )
                    # Reset state so replay is deterministic. bayesian_score
                    # is NOT NULL — use 50.0 as the prior to satisfy the
                    # constraint while update_bayesian rebuilds it.
                    metric.score = 50.0
                    metric.bayesian_score = 50.0
                    metric.confidence = 0.0
                    metric.observation_count = 0
                    # Keep level_label / trend / proven_concepts / relapsed_concepts
                    # alone — they're computed by other paths and don't
                    # depend on this rollup.
                    metric.save(update_fields=[
                        "score",
                        "bayesian_score",
                        "confidence",
                        "observation_count",
                    ])
                    for obs in obs_list:
                        try:
                            metric.update_bayesian(
                                obs.weighted_score or obs.quality_score or 50.0,
                                obs.complexity_weight or 1.0,
                            )
                        except Exception as e:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"  obs={obs.id} update_bayesian failed: {e}"
                                )
                            )
                total_metrics += 1
                total_observations += len(obs_list)

        self.stdout.write("")
        if dry:
            self.stdout.write(self.style.WARNING("DRY-RUN — no writes."))
        else:
            self.stdout.write(self.style.SUCCESS("Backfill complete."))
        self.stdout.write(
            f"  users:        {total_users}\n"
            f"  metrics:      {total_metrics}\n"
            f"  observations: {total_observations}"
        )
