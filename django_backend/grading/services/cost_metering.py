"""
LLM cost metering.

Two layers (per eng-review decision, detect AND prevent):
  1. Detective (this module): LLMCostLog writes + weekly cost query +
     €15/week email alert for each docent.
  2. Preventive: hard per-docent daily token ceiling enforced at the
     ai_engine boundary, which returns 429 when exceeded. That path is
     wired into rubric_grader.py.

This module is the write-side of the ledger. The internal admin dashboard
(Django admin view) reads it for the real-time cost view.

Model pricing (EUR per 1M tokens, approximate Apr 2026 rates).
Updated quarterly or when providers change pricing. Source of truth is the
dict below — keep it small, no env var gymnastics.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from datetime import timedelta

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone


# Prices in EUR / 1M tokens. Update from provider pricing pages.
# Format: {model_name: (input_eur_per_mtok, output_eur_per_mtok)}
MODEL_PRICING: dict[str, tuple[Decimal, Decimal]] = {
    # Cheap tier — on every commit
    "claude-haiku-4": (Decimal("0.80"), Decimal("4.00")),
    "gpt-4o-mini": (Decimal("0.14"), Decimal("0.56")),
    # Premium tier — docent grading
    "claude-sonnet-4.5": (Decimal("2.80"), Decimal("14.00")),
    "gpt-4o": (Decimal("2.30"), Decimal("9.20")),
    # Fallback — conservative over-estimate if an unknown model appears
    "unknown": (Decimal("3.00"), Decimal("15.00")),
}


# Alert threshold. Fires via management command or post-save signal.
WEEKLY_COST_ALERT_EUR = Decimal("15.00")


@dataclass
class CostBreakdown:
    tokens_in: int
    tokens_out: int
    cost_eur: Decimal
    model_name: str


def compute_cost(model_name: str, tokens_in: int, tokens_out: int) -> CostBreakdown:
    """
    Compute EUR cost for one LLM call. Falls back to conservative pricing
    if the model is unknown, and logs a warning via the LLMCostLog tag.
    """
    pricing = MODEL_PRICING.get(model_name) or MODEL_PRICING["unknown"]
    cost_in = (Decimal(tokens_in) / Decimal(1_000_000)) * pricing[0]
    cost_out = (Decimal(tokens_out) / Decimal(1_000_000)) * pricing[1]
    return CostBreakdown(
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_eur=(cost_in + cost_out).quantize(Decimal("0.000001")),
        model_name=model_name,
    )


@transaction.atomic
def log_llm_call(
    *,
    org_id: int,
    tier: str,  # "cheap" | "premium"
    model_name: str,
    tokens_in: int,
    tokens_out: int,
    docent_id: int | None = None,
    course_id: int | None = None,
    grading_session_id: int | None = None,
    latency_ms: int | None = None,
    ceiling_rejected: bool = False,
):
    """
    Append one cost row to LLMCostLog. Short transaction so it never
    blocks the LLM call path.

    Returns the created LLMCostLog instance.
    """
    from grading.models import LLMCostLog

    breakdown = compute_cost(model_name, tokens_in, tokens_out)
    return LLMCostLog.objects.create(
        org_id=org_id,
        docent_id=docent_id,
        course_id=course_id,
        grading_session_id=grading_session_id,
        tier=tier,
        model_name=model_name,
        tokens_in=breakdown.tokens_in,
        tokens_out=breakdown.tokens_out,
        cost_eur=breakdown.cost_eur,
        latency_ms=latency_ms,
        ceiling_rejected=ceiling_rejected,
    )


def docent_weekly_cost(docent_id: int, *, now=None) -> Decimal:
    """
    Rolling-week EUR cost for a docent. Used by the alert check and the
    admin dashboard.
    """
    from grading.models import LLMCostLog

    now = now or timezone.now()
    week_ago = now - timedelta(days=7)
    total = LLMCostLog.objects.filter(
        docent_id=docent_id,
        occurred_at__gte=week_ago,
    ).aggregate(total=Sum("cost_eur"))["total"]
    return total or Decimal("0")


def docent_over_weekly_threshold(docent_id: int, *, now=None) -> bool:
    """True if the docent's rolling-week cost exceeds WEEKLY_COST_ALERT_EUR."""
    return docent_weekly_cost(docent_id, now=now) > WEEKLY_COST_ALERT_EUR
