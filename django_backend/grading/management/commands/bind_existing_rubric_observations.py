"""
One-shot backfill: walk all DRAFTED GradingSessions and run
bind_rubric_to_observations on each so the student trajectory has data
without waiting for teachers to manually regenerate drafts.

Safe to re-run: bind_rubric_to_observations is idempotent via the
(grading_session, user, skill) update_or_create key.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from grading.models import GradingSession
from grading.services.skill_binding import bind_rubric_to_observations


class Command(BaseCommand):
    help = (
        "Bind SkillObservation rows for every GradingSession that has "
        "ai_draft_scores but never had the binding run (e.g., sessions "
        "drafted before the skill_binding feature shipped)."
    )

    # State filter default. Originally drafted-only, but in practice the
    # binding is also useful for sessions that have already moved on
    # (reviewing, partial, posted) — they all have ai_draft_scores and
    # may have been drafted before a Skill seed change made the binding
    # finally succeed. Empty string = all states with scores.
    DEFAULT_STATES = "drafted,reviewing,partial,posted"

    def add_arguments(self, parser):
        parser.add_argument(
            "--state",
            default=self.DEFAULT_STATES,
            help=(
                "Comma-separated list of session states to target. "
                f"Default: {self.DEFAULT_STATES}. Pass --state=all to "
                "ignore state and bind every session with scores."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be bound without writing.",
        )

    def handle(self, *args, **opts):
        state_arg = (opts["state"] or "").strip().lower()
        dry = opts["dry_run"]

        qs = GradingSession.objects.exclude(ai_draft_scores={}).exclude(
            ai_draft_scores__isnull=True,
        )
        if state_arg and state_arg != "all":
            states = [s.strip() for s in state_arg.split(",") if s.strip()]
            qs = qs.filter(state__in=states)

        total_sessions = qs.count()
        self.stdout.write(
            f"Found {total_sessions} session(s) with state={state_arg or 'all'} "
            f"and non-empty ai_draft_scores."
        )

        total_obs = 0
        for session in qs.iterator():
            if dry:
                self.stdout.write(
                    f"  [dry-run] session={session.id} "
                    f"criteria={list((session.ai_draft_scores or {}).keys())}"
                )
                continue
            try:
                n = bind_rubric_to_observations(session)
                total_obs += n
                self.stdout.write(
                    f"  session={session.id} → {n} observations"
                )
            except Exception as e:  # noqa: BLE001
                self.stderr.write(
                    f"  session={session.id} FAILED: {e}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {total_sessions} session(s) processed, "
                f"{total_obs} observation(s) bound."
            )
        )
