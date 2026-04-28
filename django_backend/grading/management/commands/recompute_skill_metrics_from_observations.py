"""
recompute_skill_metrics_from_observations — recompute SkillMetric.bayesian_score from existing
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
    python manage.py recompute_skill_metrics_from_observations --dry-run          # preview (always safe)
    python manage.py recompute_skill_metrics_from_observations                    # all users (SQLite/dev only)
    python manage.py recompute_skill_metrics_from_observations --user tester@x.io # one user (SQLite/dev only)
    python manage.py recompute_skill_metrics_from_observations --allow-prod       # required on non-SQLite DBs
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
        parser.add_argument(
            "--allow-prod",
            action="store_true",
            help=(
                "Required to run on a production-flavoured DATABASE_URL. The "
                "command resets every targeted SkillMetric to the 50.0 prior "
                "before replaying observations — accidentally pointing it at "
                "prod has wiped trust scores in the past. No-op on dev/SQLite."
            ),
        )

    def handle(self, *args, **opts):
        from django.conf import settings
        from django.contrib.auth import get_user_model
        from skills.models import SkillObservation

        User = get_user_model()
        dry = opts["dry_run"]

        # ── Production safety gate ──
        # Heuristic: if the default DB engine isn't SQLite *and* the user
        # didn't pass --allow-prod, refuse. The command resets bayesian_score
        # to 50.0 for every targeted (user, project, skill) tuple before
        # replaying — running it against prod without intent loses real data
        # for the duration of the replay (and forever if observations are
        # missing). --dry-run bypasses the gate (no writes happen).
        if not dry and not opts.get("allow_prod"):
            engine = settings.DATABASES.get("default", {}).get("ENGINE", "")
            looks_like_prod = "sqlite" not in engine.lower()
            if looks_like_prod:
                self.stderr.write(self.style.ERROR(
                    "Refusing to run on a non-SQLite database without "
                    "--allow-prod. This command resets SkillMetric rows "
                    "before replaying. Pass --allow-prod if you really mean "
                    "it, or --dry-run to preview the plan."
                ))
                return

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

            from skills.services.metric_recompute import recompute_metric
            from skills.models import Skill

            for (skill_id, project_id), obs_list in grouped.items():
                # Resolve the FK rows once — recompute_metric accepts
                # instances, not ids, so it can be called from any caller
                # (live grading flow, seed scripts, this command).
                skill = obs_list[0].skill
                project = obs_list[0].project
                with transaction.atomic():
                    try:
                        recompute_metric(user, project, skill)
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  recompute failed user={user.email} skill={skill.slug}: {e}"
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
