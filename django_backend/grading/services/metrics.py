"""
Passive weekly metrics aggregation (Workstream I1).

Shared between the ops endpoint (ops_views.OpsWeeklyMetricsView) and the
`send_weekly_digest` management command. Pure read-only — queries existing
models, mutates nothing.

Design notes:
  - "Sessions started" = GradingSession with ai_draft_generated_at in the
    period (i.e. the docent's AI draft was produced — closest signal for
    "the teacher engaged with this session").
  - "Sessions sent" = state=POSTED AND posted_at in the period.
  - "Active teacher" = distinct Submission.course.owner among started sessions.
  - "Active cohort" = distinct Course.cohort among started sessions.
  - Cost: LLMCostLog scoped by grading_session within the period
    (occurred_at). Null-safe — LLMCostLog rows without grading_session are
    counted at org level only, not per-cohort.
  - Review time stats: computed on POSTED sessions in period with a
    non-null docent_review_time_seconds. Empty list → None for both avg
    and median (callers should treat as "no data").
  - Template hit rate: mean of GradingSession.template_hit_rate across
    STARTED sessions in the period (not only POSTED — it's a draft-time
    signal).
  - Findings: derived via SessionEvaluation → Evaluation.findings for
    sessions started in the period. Can be zero for sessions without
    linked evaluations.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from statistics import median
from typing import Any, Optional

from django.db.models import Count, Q, Sum
from django.utils import timezone


def _to_aware_dt(d: date, end_of_day: bool = False) -> datetime:
    """Turn a date into a tz-aware datetime at day boundary."""
    t = time.max if end_of_day else time.min
    naive = datetime.combine(d, t)
    return timezone.make_aware(naive, timezone.get_current_timezone())


def parse_period(start: Optional[str], end: Optional[str]) -> tuple[date, date]:
    """Parse YYYY-MM-DD query params, default to last 7 days ending today."""
    today = timezone.localdate()
    if end:
        end_d = date.fromisoformat(end)
    else:
        end_d = today
    if start:
        start_d = date.fromisoformat(start)
    else:
        start_d = end_d - timedelta(days=7)
    return start_d, end_d


def _safe_div(num: float, den: float) -> float:
    if not den:
        return 0.0
    return num / den


def _decimal_to_float(d: Optional[Decimal]) -> float:
    if d is None:
        return 0.0
    return float(d)


def _review_time_stats(sessions) -> tuple[Optional[float], Optional[float]]:
    """
    (avg, median) of docent_review_time_seconds in minutes, over POSTED
    sessions with non-null values. None when no samples.
    """
    values = [
        s.docent_review_time_seconds
        for s in sessions
        if s.docent_review_time_seconds is not None
    ]
    if not values:
        return None, None
    avg_min = sum(values) / len(values) / 60.0
    med_min = median(values) / 60.0
    return round(avg_min, 2), round(med_min, 2)


def compute_daily_breakdown(
    start: date,
    end: date,
    *,
    org_ids: Optional[list[int]] = None,
) -> dict[str, Any]:
    """
    Per-day breakdown of sessions/cost/findings across the period.

    Used by the ops dashboard to drive time-series charts. Pure read,
    same org-scoping rules as compute_weekly_metrics:
      - org_ids is None → all orgs (superuser)
      - org_ids = [id] → restricted

    Returns:
        {
          "period": {"start": ..., "end": ...},
          "days": [
            {"date": "YYYY-MM-DD",
             "sessions_started": int, "sessions_sent": int,
             "llm_cost_eur": float, "findings_total": int,
             "teachers_active": int},
            ...
          ],
          "per_org": [
            {"org_id", "org_name",
             "sessions_started", "sessions_sent", "llm_cost_eur"},
            ...
          ],
          "grand_totals": { ...same as compute_weekly_metrics }
        }
    """
    from users.models import Organization

    from ..models import GradingSession, LLMCostLog
    from evaluations.models import Finding

    start_dt = _to_aware_dt(start, end_of_day=False)
    end_dt = _to_aware_dt(end, end_of_day=True)

    started_qs = GradingSession.objects.filter(
        ai_draft_generated_at__gte=start_dt,
        ai_draft_generated_at__lte=end_dt,
    ).select_related("submission__course__owner")
    posted_qs = GradingSession.objects.filter(
        state=GradingSession.State.POSTED,
        posted_at__gte=start_dt,
        posted_at__lte=end_dt,
    )
    cost_qs = LLMCostLog.objects.filter(
        occurred_at__gte=start_dt, occurred_at__lte=end_dt,
    )

    if org_ids is not None:
        started_qs = started_qs.filter(org_id__in=org_ids)
        posted_qs = posted_qs.filter(org_id__in=org_ids)
        cost_qs = cost_qs.filter(org_id__in=org_ids)

    tz = timezone.get_current_timezone()

    def _localdate(dt):
        return timezone.localtime(dt, tz).date()

    # Per-day buckets
    started_by_day: dict[date, list] = defaultdict(list)
    posted_by_day: dict[date, int] = defaultdict(int)
    cost_by_day: dict[date, Decimal] = defaultdict(lambda: Decimal("0"))
    teachers_by_day: dict[date, set[int]] = defaultdict(set)

    for s in started_qs:
        d = _localdate(s.ai_draft_generated_at)
        started_by_day[d].append(s)
        if s.submission and s.submission.course and s.submission.course.owner_id:
            teachers_by_day[d].add(s.submission.course.owner_id)

    for s in posted_qs:
        if s.posted_at is None:
            continue
        d = _localdate(s.posted_at)
        posted_by_day[d] += 1

    for log in cost_qs:
        d = _localdate(log.occurred_at)
        cost_by_day[d] += log.cost_eur or Decimal("0")

    # Findings per day (via started sessions)
    started_ids = [s.id for ids in started_by_day.values() for s in ids]
    findings_by_session: dict[int, int] = defaultdict(int)
    if started_ids:
        rows = (
            Finding.objects
            .filter(evaluation__grading_session_links__grading_session_id__in=started_ids)
            .values("evaluation__grading_session_links__grading_session_id")
            .annotate(total=Count("id"))
        )
        for r in rows:
            findings_by_session[
                r["evaluation__grading_session_links__grading_session_id"]
            ] = r["total"]

    # Build contiguous day series (include zero days)
    days_out = []
    cursor = start
    while cursor <= end:
        started_list = started_by_day.get(cursor, [])
        findings_total = sum(findings_by_session.get(s.id, 0) for s in started_list)
        days_out.append({
            "date": cursor.isoformat(),
            "sessions_started": len(started_list),
            "sessions_sent": posted_by_day.get(cursor, 0),
            "llm_cost_eur": round(_decimal_to_float(cost_by_day.get(cursor, Decimal("0"))), 4),
            "findings_total": findings_total,
            "teachers_active": len(teachers_by_day.get(cursor, set())),
        })
        cursor = cursor + timedelta(days=1)

    # Per-org aggregation
    per_org_sessions_started: dict[int, int] = defaultdict(int)
    per_org_sessions_sent: dict[int, int] = defaultdict(int)
    per_org_cost: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))

    for s in started_qs:
        per_org_sessions_started[s.org_id] += 1
    for s in posted_qs:
        per_org_sessions_sent[s.org_id] += 1
    for log in cost_qs:
        per_org_cost[log.org_id] += log.cost_eur or Decimal("0")

    org_qs = Organization.objects.all()
    if org_ids is not None:
        org_qs = org_qs.filter(id__in=org_ids)
    org_name_by_id = {o.id: o.name for o in org_qs}

    per_org_ids = (
        set(per_org_sessions_started)
        | set(per_org_sessions_sent)
        | set(per_org_cost)
    )
    per_org_out = []
    for oid in per_org_ids:
        per_org_out.append({
            "org_id": oid,
            "org_name": org_name_by_id.get(oid, f"org#{oid}"),
            "sessions_started": per_org_sessions_started.get(oid, 0),
            "sessions_sent": per_org_sessions_sent.get(oid, 0),
            "llm_cost_eur": round(_decimal_to_float(per_org_cost.get(oid, Decimal("0"))), 4),
        })
    per_org_out.sort(key=lambda r: r["sessions_started"], reverse=True)

    # Grand totals — match weekly shape for convenience
    grand_sessions_started = sum(d["sessions_started"] for d in days_out)
    grand_sessions_sent = sum(d["sessions_sent"] for d in days_out)
    grand_cost = sum((cost_by_day.get(d, Decimal("0")) for d in cost_by_day), Decimal("0"))
    all_teachers = set()
    for tset in teachers_by_day.values():
        all_teachers |= tset
    orgs_active = sum(
        1 for r in per_org_out
        if r["sessions_started"] or r["sessions_sent"] or r["llm_cost_eur"]
    )

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "days": days_out,
        "per_org": per_org_out,
        "grand_totals": {
            "sessions_started": grand_sessions_started,
            "sessions_sent": grand_sessions_sent,
            "llm_cost_eur": round(_decimal_to_float(grand_cost), 4),
            "orgs_active": orgs_active,
            "teachers_active": len(all_teachers),
        },
    }


def compute_weekly_metrics(
    start: date,
    end: date,
    *,
    org_ids: Optional[list[int]] = None,
) -> dict[str, Any]:
    """
    Build the weekly metrics report for the given period.

    If `org_ids` is None → include all orgs (superuser path).
    Otherwise restrict to those org ids (admin path).

    Returns a dict in the documented shape — see I1 scope doc.
    """
    from users.models import Organization

    from ..models import Cohort, Course, GradingSession, LLMCostLog
    # Finding is in evaluations app — we only READ it, allowed.
    from evaluations.models import Finding

    start_dt = _to_aware_dt(start, end_of_day=False)
    end_dt = _to_aware_dt(end, end_of_day=True)

    org_qs = Organization.objects.all()
    if org_ids is not None:
        org_qs = org_qs.filter(id__in=org_ids)
    org_qs = org_qs.order_by("id")

    # Pre-pull the starting + posted session sets once, then bucket.
    started_qs = GradingSession.objects.filter(
        ai_draft_generated_at__gte=start_dt,
        ai_draft_generated_at__lte=end_dt,
    ).select_related("submission__course__cohort", "submission__course__owner", "org")
    posted_qs = GradingSession.objects.filter(
        state=GradingSession.State.POSTED,
        posted_at__gte=start_dt,
        posted_at__lte=end_dt,
    ).select_related("submission__course__cohort", "submission__course__owner", "org")

    if org_ids is not None:
        started_qs = started_qs.filter(org_id__in=org_ids)
        posted_qs = posted_qs.filter(org_id__in=org_ids)

    # Bucket by (org_id, cohort_id). Cohort can be None — put those in a
    # bucket keyed by cohort_id=None (we still surface them).
    started_by_cohort: dict[tuple[int, Optional[int]], list] = defaultdict(list)
    for s in started_qs:
        course = s.submission.course
        started_by_cohort[(s.org_id, course.cohort_id)].append(s)

    posted_by_cohort: dict[tuple[int, Optional[int]], list] = defaultdict(list)
    for s in posted_qs:
        course = s.submission.course
        posted_by_cohort[(s.org_id, course.cohort_id)].append(s)

    # Cost per cohort via grading_session.submission.course.cohort_id.
    # Single query, then bucket in Python.
    cost_logs = LLMCostLog.objects.filter(
        occurred_at__gte=start_dt,
        occurred_at__lte=end_dt,
    ).select_related("grading_session__submission__course")
    if org_ids is not None:
        cost_logs = cost_logs.filter(org_id__in=org_ids)

    cost_by_cohort: dict[tuple[int, Optional[int]], Decimal] = defaultdict(
        lambda: Decimal("0"),
    )
    cost_by_org: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    for log in cost_logs:
        cost_by_org[log.org_id] += log.cost_eur or Decimal("0")
        gs = log.grading_session
        cohort_id = None
        if gs and gs.submission_id:
            cohort_id = gs.submission.course.cohort_id
        cost_by_cohort[(log.org_id, cohort_id)] += log.cost_eur or Decimal("0")

    # Findings per started session, via SessionEvaluation → Evaluation → Findings.
    started_session_ids = [s.id for s in started_qs]
    findings_by_session: dict[int, int] = defaultdict(int)
    if started_session_ids:
        finding_rows = (
            Finding.objects
            .filter(evaluation__grading_session_links__grading_session_id__in=started_session_ids)
            .values("evaluation__grading_session_links__grading_session_id")
            .annotate(total=Count("id"))
        )
        for row in finding_rows:
            findings_by_session[row["evaluation__grading_session_links__grading_session_id"]] = row["total"]

    orgs_out: list[dict[str, Any]] = []
    grand_sessions_started = 0
    grand_sessions_sent = 0
    grand_cost = Decimal("0")
    grand_orgs_active = 0
    grand_cohorts_active = 0

    for org in org_qs:
        # Which cohorts had activity this period for this org?
        cohorts_seen: set[Optional[int]] = set()
        for (oid, cid) in started_by_cohort.keys():
            if oid == org.id:
                cohorts_seen.add(cid)
        for (oid, cid) in posted_by_cohort.keys():
            if oid == org.id:
                cohorts_seen.add(cid)
        # Include cost-only cohorts too (edge case: cost logged, draft ts null)
        for (oid, cid) in cost_by_cohort.keys():
            if oid == org.id:
                cohorts_seen.add(cid)

        cohort_name_map: dict[Optional[int], str] = {None: "(no cohort)"}
        if cohorts_seen:
            real_ids = [cid for cid in cohorts_seen if cid is not None]
            if real_ids:
                for c in Cohort.objects.filter(id__in=real_ids):
                    cohort_name_map[c.id] = c.name

        org_cohort_rows: list[dict[str, Any]] = []
        org_sessions_started = 0
        org_sessions_sent = 0
        org_teachers: set[int] = set()

        for cid in sorted(cohorts_seen, key=lambda x: (x is None, x or 0)):
            started = started_by_cohort.get((org.id, cid), [])
            posted = posted_by_cohort.get((org.id, cid), [])
            teacher_ids = {
                s.submission.course.owner_id
                for s in started
                if s.submission and s.submission.course
            }
            sessions_started = len(started)
            sessions_sent = len(posted)
            avg_rt, med_rt = _review_time_stats(posted)
            cost = cost_by_cohort.get((org.id, cid), Decimal("0"))

            # Template hit rate: mean over started sessions
            if started:
                hit_rates = [s.template_hit_rate for s in started]
                tmpl_hit_rate = round(sum(hit_rates) / len(hit_rates), 4)
            else:
                tmpl_hit_rate = 0.0

            findings_total = sum(findings_by_session.get(s.id, 0) for s in started)
            findings_per_session = (
                round(findings_total / sessions_started, 2)
                if sessions_started
                else 0.0
            )

            org_cohort_rows.append({
                "cohort_id": cid,
                "cohort_name": cohort_name_map.get(cid, f"cohort#{cid}"),
                "teachers_active": len(teacher_ids),
                "sessions_started": sessions_started,
                "sessions_sent": sessions_sent,
                "send_rate": round(_safe_div(sessions_sent, sessions_started), 4),
                "avg_review_time_minutes": avg_rt,
                "median_review_time_minutes": med_rt,
                "llm_cost_eur": round(_decimal_to_float(cost), 4),
                "llm_cost_per_session_eur": round(
                    _safe_div(_decimal_to_float(cost), sessions_started), 4,
                ),
                "template_hit_rate": tmpl_hit_rate,
                "findings_total": findings_total,
                "findings_per_session_avg": findings_per_session,
            })

            org_sessions_started += sessions_started
            org_sessions_sent += sessions_sent
            org_teachers |= teacher_ids

        org_cost = cost_by_org.get(org.id, Decimal("0"))

        # Only emit orgs that had ANY activity in this period when scoping
        # to "all" — keeps the digest readable. For the admin-scoped
        # single-org case, always emit so they see their zeros.
        had_activity = bool(
            org_sessions_started
            or org_sessions_sent
            or org_cost
            or org_cohort_rows
        )
        if org_ids is not None or had_activity:
            orgs_out.append({
                "org_id": org.id,
                "org_name": org.name,
                "cohorts": org_cohort_rows,
                "totals": {
                    "sessions_started": org_sessions_started,
                    "sessions_sent": org_sessions_sent,
                    "llm_cost_eur": round(_decimal_to_float(org_cost), 4),
                    "teachers_active": len(org_teachers),
                },
            })

            if had_activity:
                grand_orgs_active += 1
            grand_sessions_started += org_sessions_started
            grand_sessions_sent += org_sessions_sent
            grand_cost += org_cost
            grand_cohorts_active += sum(
                1 for row in org_cohort_rows if row["sessions_started"] > 0
            )

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "orgs": orgs_out,
        "grand_totals": {
            "sessions_started": grand_sessions_started,
            "sessions_sent": grand_sessions_sent,
            "llm_cost_eur": round(_decimal_to_float(grand_cost), 4),
            "orgs_active": grand_orgs_active,
            "cohorts_active": grand_cohorts_active,
        },
    }
