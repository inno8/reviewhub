"""
Backfill Evaluation + SessionEvaluation links for GradingSessions that
were created by the grading webhook BEFORE it started writing those
links itself.

Flow per session:
  1. If an attached SessionEvaluation already exists -> skip.
  2. Otherwise, get-or-create a virtual Project for the Submission's repo.
  3. Create an Evaluation with commit_sha derived from the Submission
     (head_branch -> "pr-<number>-<branch>" placeholder; real commit SHA
     is not recoverable post-hoc without refetching GitHub).
  4. Create the SessionEvaluation row.
  5. If the session already has ai_draft_scores, run
     bind_rubric_to_observations so trajectory populates immediately.

Safe to re-run: every write is idempotent (get_or_create, update_or_create).
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from grading.models import GradingSession, SessionEvaluation
from grading.services.skill_binding import bind_rubric_to_observations
from grading.services.virtual_project import get_or_create_virtual_project


def _synthetic_commit_sha(submission) -> str:
    """Reconstruct a stable commit_sha placeholder for historical sessions."""
    return f"pr-{submission.pr_number}-{submission.head_branch or 'head'}"[:40]


class Command(BaseCommand):
    help = (
        "Backfill Evaluation + SessionEvaluation for GradingSessions that "
        "were created before the webhook began writing those links. Also "
        "runs skill_binding on sessions whose drafts are already generated."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be created without writing.",
        )

    def handle(self, *args, **opts):
        from evaluations.models import Evaluation

        dry = opts["dry_run"]

        sessions = list(GradingSession.objects.select_related("submission__student").all())
        self.stdout.write(f"Scanning {len(sessions)} GradingSession(s)...")

        created_evals = 0
        created_links = 0
        bound_obs = 0
        skipped = 0

        for session in sessions:
            existing = SessionEvaluation.objects.filter(grading_session=session).first()
            if existing:
                skipped += 1
                self.stdout.write(
                    f"  session={session.id} already linked to "
                    f"evaluation={existing.evaluation_id} — skip"
                )
                # Still try skill binding if draft exists and no observations yet.
                if (
                    not dry
                    and session.ai_draft_scores
                    and session.ai_draft_generated_at
                ):
                    try:
                        n = bind_rubric_to_observations(session)
                        bound_obs += n
                        if n:
                            self.stdout.write(
                                f"    -> re-bound {n} observation(s)"
                            )
                    except Exception as e:  # noqa: BLE001
                        self.stderr.write(f"    bind FAILED: {e}")
                continue

            submission = session.submission
            if submission is None:
                self.stderr.write(
                    f"  session={session.id} has no submission — skip"
                )
                continue

            commit_sha = _synthetic_commit_sha(submission)
            if dry:
                self.stdout.write(
                    f"  [dry-run] session={session.id} submission={submission.id} "
                    f"would create Evaluation(commit_sha={commit_sha})"
                )
                continue

            project = get_or_create_virtual_project(submission)
            evaluation, ev_created = Evaluation.objects.get_or_create(
                project=project,
                commit_sha=commit_sha,
                defaults={
                    "author": submission.student,
                    "commit_message": (submission.pr_title or "")[:500],
                    "branch": (submission.head_branch or "unknown")[:100],
                    "author_name": (
                        submission.student.username or submission.student.email or ""
                    )[:100],
                    "author_email": (submission.student.email or "")[:255],
                    "status": Evaluation.Status.PENDING,
                    "llm_model": "",
                },
            )
            if ev_created:
                created_evals += 1

            _, link_created = SessionEvaluation.objects.get_or_create(
                grading_session=session,
                evaluation=evaluation,
                defaults={"included_in_draft": False},
            )
            if link_created:
                created_links += 1

            self.stdout.write(
                f"  session={session.id} -> evaluation={evaluation.id} "
                f"(eval_created={ev_created}, link_created={link_created})"
            )

            # If the draft already ran, bind observations now.
            if session.ai_draft_scores and session.ai_draft_generated_at:
                try:
                    n = bind_rubric_to_observations(session)
                    bound_obs += n
                    if n:
                        self.stdout.write(f"    -> bound {n} observation(s)")
                except Exception as e:  # noqa: BLE001
                    self.stderr.write(f"    bind FAILED: {e}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. sessions={len(sessions)} skipped={skipped} "
                f"evaluations_created={created_evals} "
                f"links_created={created_links} "
                f"skill_observations_bound={bound_obs}"
            )
        )
