"""
Iteration-tracking migration:

  1. Add PostedComment.resolved_at + resolved_by_student fields so the
     pull_request_review_thread handler can track per-comment resolution
     state for the teacher-facing "N/M resolved" indicator AND to seed
     the LearningProof verifier later.

  2. One-shot data cleanup — any GradingSession with iteration_number > 1
     whose parent Submission.status == GRADED is a bogus iteration that
     was spawned by the old weak `synchronize` trigger after the PR was
     already merged. Mark those DISCARDED and clear superseded_by on the
     nearest non-discarded predecessor.
"""
from django.db import migrations, models


def _cleanup_bogus_iterations_from_merged_prs(apps, schema_editor):
    """
    Idempotent cleanup: if a Submission is GRADED (merged), any iteration
    beyond #1 is bogus. Mark them DISCARDED and untangle the supersedes
    chain on the real iter-1 row.
    """
    GradingSession = apps.get_model("grading", "GradingSession")
    Submission = apps.get_model("grading", "Submission")

    bogus = GradingSession.objects.filter(
        iteration_number__gt=1,
        submission__status="graded",
    ).select_related("submission").order_by("submission_id", "iteration_number")

    touched_submissions = set()
    for s in bogus:
        if s.state != "discarded":
            s.state = "discarded"
            s.save(update_fields=["state", "updated_at"])
        touched_submissions.add(s.submission_id)

    # For each affected submission, find the nearest non-discarded predecessor
    # (usually iteration 1) and clear its superseded_by pointer so it becomes
    # the canonical current session again.
    for sub_id in touched_submissions:
        predecessors = GradingSession.objects.filter(
            submission_id=sub_id,
        ).exclude(state="discarded").order_by("iteration_number")
        for pred in predecessors:
            if pred.superseded_by_id is not None:
                # Only clear pointers to discarded sessions.
                if GradingSession.objects.filter(
                    pk=pred.superseded_by_id, state="discarded",
                ).exists():
                    pred.superseded_by = None
                    pred.save(update_fields=["superseded_by", "updated_at"])


def _reverse_cleanup(apps, schema_editor):
    """No-op reverse: cleanup is destructive-looking but only flips state to
    DISCARDED; we don't know the original states, so don't try to restore."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("grading", "0008_grading_session_iterations"),
    ]

    operations = [
        migrations.AddField(
            model_name="postedcomment",
            name="resolved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="postedcomment",
            name="resolved_by_student",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(
            _cleanup_bogus_iterations_from_merged_prs,
            _reverse_cleanup,
        ),
    ]
