"""
Signal handlers that keep the DeveloperProfile in sync with reality.

Why this file exists:

The DeveloperProfile is the "doctor of the student" — a teacher's
single-glance summary of where a developer stands and how they're
trending. Originally it was only updated when a batch job finished
processing a historical repo. That meant on Day 1 a student got a
fresh profile, then it sat frozen forever while the student kept
learning and getting PR reviews. Teachers would see Day-1 data
months later and make wrong intervention decisions.

The fix: hook into Evaluation.post_save and refresh the profile every
time an evaluation completes. The evaluation pipeline writes
COMPLETED status from two places:
  - The /webhook/ AI engine callback (per-commit auto-review)
  - The batch processor (historical repo replay)

Both reach this signal. We filter to "status transitioned to
COMPLETED" so we don't refresh on every save (e.g. PROCESSING → COMPLETED
should fire; PROCESSING re-saved as PROCESSING shouldn't).
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='evaluations.Evaluation', dispatch_uid='batch.refresh_profile_on_evaluation')
def refresh_profile_on_evaluation(sender, instance, created, **kwargs):
    """
    Refresh the author's DeveloperProfile whenever a completed evaluation
    is saved. No-op when:
      - The evaluation has no author (anonymous push, ingest gap)
      - The evaluation isn't COMPLETED yet (still pending / processing)

    Failures are logged but never raised — the profile is a derived
    artifact and we never want a profile-refresh bug to block the
    underlying evaluation save (which is the source of truth).
    """
    from evaluations.models import Evaluation
    from .services import refresh_profile_for_user

    if not getattr(instance, 'author_id', None):
        return
    if getattr(instance, 'status', None) != Evaluation.Status.COMPLETED:
        return

    try:
        refresh_profile_for_user(instance.author)
    except Exception as e:
        logger.warning(
            "Failed to refresh DeveloperProfile for user_id=%s after "
            "evaluation_id=%s: %s",
            instance.author_id, instance.pk, e,
        )
