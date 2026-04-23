"""
Cheap-tier throttle — rules A + B (eng review Section 4).

Rule A: Daily cap of 3 cheap-tier evaluations per student per day.
Rule B: Skip cheap-tier eval on commits with <10 lines changed.

Rule C (AST-fingerprint dedupe) was deferred to v1.1 on eng-review feedback.

Called from the webhook ingest path BEFORE firing a cheap-tier evaluation.
Returns ThrottleDecision(skip=True, reason=...) if the call should be
skipped. The webhook logs the skip and continues.

This is enforcement, not just detection. Combined with the hard cost
ceiling at the ai_engine boundary, v1 has two independent cost guards.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone


# Defaults — tune from cost-metering dashboard in May dogfood
DAILY_CHEAP_CAP_PER_STUDENT = 3
MIN_LINES_CHANGED = 10


@dataclass(frozen=True)
class ThrottleDecision:
    skip: bool
    reason: str = ""


def should_skip_cheap_eval(
    *,
    student_id: int,
    lines_changed: int,
    now=None,
) -> ThrottleDecision:
    """
    Gate cheap-tier LLM calls.

    Parameters
    ----------
    student_id : int
        The User.id of the student who pushed the commit.
    lines_changed : int
        Total added+removed lines in the diff.
    now : datetime, optional
        Inject for tests.
    """
    # Rule B: trivial-change filter. Applies first because it needs zero DB hits.
    if lines_changed < MIN_LINES_CHANGED:
        return ThrottleDecision(
            skip=True,
            reason=f"trivial_change ({lines_changed} < {MIN_LINES_CHANGED} lines)",
        )

    # Rule A: daily cap. Counts today's evaluations for this student.
    # Import locally to avoid circular imports at module load time.
    from grading.models import LLMCostLog

    now = now or timezone.now()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

    today_count = LLMCostLog.objects.filter(
        # Cheap-tier calls are logged with docent=null; we join through
        # grading_session → submission → student for the count. But for
        # the webhook hot path we don't have a GradingSession yet — the
        # simpler key is the submission.student_id via the recent cost logs.
        tier=LLMCostLog.Tier.CHEAP,
        occurred_at__gte=start_of_day,
        grading_session__submission__student_id=student_id,
    ).count()

    if today_count >= DAILY_CHEAP_CAP_PER_STUDENT:
        return ThrottleDecision(
            skip=True,
            reason=f"daily_cap ({today_count} ≥ {DAILY_CHEAP_CAP_PER_STUDENT} for student {student_id})",
        )

    return ThrottleDecision(skip=False)
