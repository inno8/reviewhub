"""
seed_demo_observations — add synthetic SkillObservation rows for demo
students so their radar + per-criterion confidence rises above
CONFIDENCE_PRELIMINARY (0.15) without faking the underlying numbers.

Why this exists
---------------
The dogfood seeder creates ~4 SkillObservation rows per skill per
student. With CONFIDENCE_GAIN_PER_OBS=0.02 × complexity_weight=1.0,
that leaves Bayesian confidence at ~0.08 — below the 0.15 preliminary
threshold. The radar UI then renders every spoke muted with a
"Voorlopige scores" banner.

For the May 7 pitch we want at least one demo student (Jan de Boer)
to show a confident radar. Two paths considered:
  A. Manually bump confidence on SkillMetric rows. Quick but lies to
     the data layer — recompute commands undo it, future Bayesian
     updates use a wrong prior.
  B. Add real SkillObservation rows so the recompute formula
     naturally arrives at 0.18-0.22 confidence. This script.

This script is path B. No constants are tweaked, no shortcuts; just
more evidence rows the model genuinely uses.

What it does
------------
1. For each target student (default: Jan, Fatima, Lucas), iterates
   their existing SkillObservations.
2. For every (user, skill) pair, adds N=6 synthetic observations
   with the same quality_score but complexity_weight=1.0, distinct
   commit_sha so the rows are real-looking and idempotent.
3. Runs the recompute (delete SkillMetric + replay every observation)
   so confidence rises to ~0.20.

Idempotent: synthetic rows have commit_sha prefixed with `demoboost-`
and a deterministic sequence number per (user, skill). Re-running is
a no-op.

Reversible: --undo deletes every SkillObservation with the
`demoboost-` prefix and recomputes.

Usage
-----
    python manage.py seed_demo_observations --dry-run     # preview
    python manage.py seed_demo_observations                # apply
    python manage.py seed_demo_observations --undo         # remove
    python manage.py seed_demo_observations --student jan.deboer@student.mediacollege.nl
    python manage.py seed_demo_observations --boost-count 8

Demo-only — refuses to run on non-SQLite DBs without --allow-prod.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


DEFAULT_STUDENT_EMAILS = (
    "jan.deboer@student.mediacollege.nl",
    "fatima.elamrani@student.mediacollege.nl",
    "lucas.vandijk@student.mediacollege.nl",
)
DEMO_COMMIT_PREFIX = "demoboost-"


class Command(BaseCommand):
    help = (
        "Add synthetic SkillObservation rows for demo students so radar "
        "confidence rises above the preliminary threshold."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--student",
            action="append",
            dest="student_emails",
            help=(
                "Email of a target student. Repeatable. "
                f"Default: {', '.join(DEFAULT_STUDENT_EMAILS)}"
            ),
        )
        parser.add_argument(
            "--boost-count",
            type=int,
            default=6,
            help=(
                "Synthetic observations per (student, skill). 6 lifts confidence "
                "from ~0.08 to ~0.20 with complexity_weight=1.0. Default: 6."
            ),
        )
        parser.add_argument(
            "--undo",
            action="store_true",
            help="Delete every SkillObservation with commit_sha starting with 'demoboost-' and recompute.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print the plan without writing to the DB.",
        )
        parser.add_argument(
            "--allow-prod",
            action="store_true",
            help="Required to run on a non-SQLite DATABASE_URL. Demo-only data, never run on prod by accident.",
        )

    def handle(self, *args, **opts):
        from django.conf import settings
        from django.contrib.auth import get_user_model
        from skills.models import SkillMetric, SkillObservation

        User = get_user_model()

        # Production safety gate (mirrors recompute_skill_metrics_from_observations).
        # Django stores the key as 'ENGINE' (uppercase). The recompute command
        # has the same off-by-case bug — fix in both eventually.
        engine = settings.DATABASES.get("default", {}).get("ENGINE", "")
        looks_like_prod = "sqlite" not in engine.lower()
        if not opts["dry_run"] and looks_like_prod and not opts["allow_prod"]:
            self.stderr.write(self.style.ERROR(
                f"Refusing to run on a non-SQLite engine ({engine}) without "
                f"--allow-prod. This command writes synthetic data and is "
                f"intended for local demo-prep only."
            ))
            return

        emails = opts["student_emails"] or list(DEFAULT_STUDENT_EMAILS)
        boost_count = opts["boost_count"]
        undo = opts["undo"]
        dry_run = opts["dry_run"]

        students = list(User.objects.filter(email__in=emails))
        if not students:
            raise CommandError(f"No users matched any of: {emails}")
        missing = set(emails) - {s.email for s in students}
        if missing:
            self.stdout.write(self.style.WARNING(
                f"Skipping (not in DB): {', '.join(sorted(missing))}"
            ))

        # ── Undo path ──
        if undo:
            qs = SkillObservation.objects.filter(
                user__in=students,
                commit_sha__startswith=DEMO_COMMIT_PREFIX,
            )
            n = qs.count()
            self.stdout.write(f"--undo: would delete {n} demoboost SkillObservation rows.")
            if dry_run:
                return
            with transaction.atomic():
                qs.delete()
            self._recompute_for(students)
            self.stdout.write(self.style.SUCCESS(f"Removed {n} synthetic obs and recomputed metrics."))
            return

        # ── Apply path ──
        plan: list[tuple[User, int, int]] = []  # (student, existing_obs, planned_new)
        skips: list[tuple[str, str]] = []       # (email, reason)
        for student in students:
            existing = SkillObservation.objects.filter(user=student)
            real = existing.exclude(commit_sha__startswith=DEMO_COMMIT_PREFIX)
            already_demo = existing.filter(commit_sha__startswith=DEMO_COMMIT_PREFIX).count()
            if not real.exists():
                skips.append((student.email, "no real SkillObservation rows to clone from"))
                continue
            if already_demo > 0:
                skips.append((student.email, f"already has {already_demo} demoboost obs (idempotent skip)"))
                continue
            # Skill set this student has real observations for
            distinct_skills = real.values_list("skill_id", flat=True).distinct()
            plan.append((student, real.count(), len(distinct_skills) * boost_count))

        # ── Plan summary ──
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("DRY-RUN — no DB writes." if dry_run else "PLAN"))
        self.stdout.write(f"Boost count per (student, skill): {boost_count}")
        self.stdout.write(f"Targets: {len(plan)} student(s)")
        for s, real_n, planned_n in plan:
            self.stdout.write(
                f"  {s.email}: {real_n} real obs -> +{planned_n} synthetic "
                f"(complexity_weight=1.0, quality copied per-skill)"
            )
        for email, reason in skips:
            self.stdout.write(self.style.NOTICE(f"  SKIP {email}: {reason}"))

        if dry_run or not plan:
            return

        # ── Apply ──
        with transaction.atomic():
            created = 0
            for student, _real_n, _planned_n in plan:
                # Collect one representative real obs per skill — we copy its
                # project + evaluation + quality_score and only synthesize
                # commit_sha + bumped complexity_weight.
                seen_skill_ids: set[int] = set()
                templates = []
                for o in (
                    SkillObservation.objects
                    .filter(user=student)
                    .exclude(commit_sha__startswith=DEMO_COMMIT_PREFIX)
                    .select_related("skill", "project", "evaluation")
                    .order_by("-created_at")
                ):
                    if o.skill_id in seen_skill_ids:
                        continue
                    seen_skill_ids.add(o.skill_id)
                    templates.append(o)

                for tpl in templates:
                    for i in range(boost_count):
                        SkillObservation.objects.create(
                            user=student,
                            project=tpl.project,
                            evaluation=tpl.evaluation,
                            skill=tpl.skill,
                            grading_session=None,  # not tied to a real PR
                            commit_sha=f"{DEMO_COMMIT_PREFIX}{student.id:04d}-{tpl.skill_id:03d}-{i:02d}",
                            quality_score=tpl.quality_score,
                            complexity_weight=1.0,
                            lines_changed=tpl.lines_changed or 50,
                            issue_count=0,
                            critical_count=0,
                        )
                        created += 1

        self.stdout.write(f"Created {created} SkillObservation rows.")

        # ── Recompute ──
        self._recompute_for(students)

        # ── Summary ──
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Done. New confidence values:"))
        for student in students:
            metrics = (
                SkillMetric.objects
                .filter(user=student)
                .select_related("skill__category")
                .order_by("-confidence")
            )
            for m in metrics:
                self.stdout.write(
                    f"  {student.email[:35]:35} {m.skill.name[:30]:30} "
                    f"score={m.bayesian_score:5.1f} conf={m.confidence:.2f} obs={m.observation_count}"
                )

    def _recompute_for(self, students):
        """Reset and replay every (user, skill) for the targeted students."""
        from skills.models import SkillMetric, SkillObservation

        with transaction.atomic():
            for student in students:
                SkillMetric.objects.filter(user=student).delete()
                obs_qs = (
                    SkillObservation.objects
                    .filter(user=student)
                    .select_related("skill", "project")
                    .order_by("created_at")
                )
                for obs in obs_qs:
                    metric, _ = SkillMetric.objects.get_or_create(
                        user=student, project=obs.project, skill=obs.skill,
                    )
                    metric.update_bayesian(
                        weighted_score=obs.weighted_score,
                        complexity_weight=obs.complexity_weight,
                    )
