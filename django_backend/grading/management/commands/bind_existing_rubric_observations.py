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

    def add_arguments(self, parser):
        parser.add_argument(
            "--state",
            default=GradingSession.State.DRAFTED,
            help="Session state to target (default: drafted).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be bound without writing.",
        )

    def handle(self, *args, **opts):
        state = opts["state"]
        dry = opts["dry_run"]

        qs = GradingSession.objects.filter(state=state).exclude(
            ai_draft_scores={}
        )
        total_sessions = qs.count()
        self.stdout.write(
            f"Found {total_sessions} session(s) with state={state} "
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
