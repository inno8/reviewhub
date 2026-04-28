"""
Platform Ops Dashboard API (superuser only).

Separate from the teacher/admin/student surface in views.py. This is
the internal operations panel for the platform owner (us) to monitor:
  - All orgs + their classrooms + student counts
  - Cost rollup per org / per teacher / per classroom
  - LLM call log (rolling 7/30 days)
  - Per-docent weekly spend vs alert threshold

Auth: IsSuperuser (request.user.is_superuser == True). No "ops role" —
just Django's standard superuser flag. Keeps the model simple.

v1 scope: read-only. Write paths (delete org, suspend teacher, force-
refresh cost alerts) deferred to v1.1 once we have dogfood usage signal.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Sum, F
from django.utils import timezone
from rest_framework import permissions, views
from rest_framework.response import Response

from .models import Cohort, CohortMembership, Course, GradingSession, LLMCostLog
from .permissions import _is_admin
from .services.cost_metering import WEEKLY_COST_ALERT_EUR
from .services.metrics import (
    compute_daily_breakdown,
    compute_weekly_metrics,
    parse_period,
)


# ─────────────────────────────────────────────────────────────────────────────
# Permission
# ─────────────────────────────────────────────────────────────────────────────
class IsSuperuser(permissions.BasePermission):
    """Only Django superusers can hit the ops dashboard."""

    message = "Platform operations — superuser only."

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_superuser
        )


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
class OpsSummaryView(views.APIView):
    """
    GET /api/grading/ops/summary/
    One-page dashboard header: totals across the platform.
    """

    permission_classes = [IsSuperuser]

    def get(self, request):
        from users.models import Organization, User

        now = timezone.now()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        total_orgs = Organization.objects.count()
        total_cohorts = Cohort.objects.count()
        total_courses = Course.objects.count()
        total_teachers = User.objects.filter(role="teacher").count()
        total_students = User.objects.filter(role="developer").count()

        sessions_7d = GradingSession.objects.filter(created_at__gte=week_ago).count()
        posted_7d = GradingSession.objects.filter(
            posted_at__gte=week_ago,
            state=GradingSession.State.POSTED,
        ).count()

        cost_7d = LLMCostLog.objects.filter(occurred_at__gte=week_ago).aggregate(
            total=Sum("cost_eur"),
        )["total"] or Decimal("0")
        cost_30d = LLMCostLog.objects.filter(occurred_at__gte=month_ago).aggregate(
            total=Sum("cost_eur"),
        )["total"] or Decimal("0")

        docents_over_threshold = (
            LLMCostLog.objects
            .filter(occurred_at__gte=week_ago, docent__isnull=False)
            .values("docent_id", "docent__email")
            .annotate(total=Sum("cost_eur"))
            .filter(total__gt=WEEKLY_COST_ALERT_EUR)
            .order_by("-total")
        )

        return Response({
            "platform_totals": {
                "orgs": total_orgs,
                "cohorts": total_cohorts,
                "courses": total_courses,
                # Legacy key retained for UI compat during Workstream A→B transition.
                "classrooms": total_courses,
                "teachers": total_teachers,
                "students": total_students,
            },
            "activity_7d": {
                "sessions_created": sessions_7d,
                "sessions_posted": posted_7d,
                "cost_eur": str(cost_7d),
            },
            "activity_30d": {
                "cost_eur": str(cost_30d),
            },
            "alerts": {
                "weekly_threshold_eur": str(WEEKLY_COST_ALERT_EUR),
                "docents_over_threshold": list(docents_over_threshold),
            },
            "generated_at": now.isoformat(),
        })


# ─────────────────────────────────────────────────────────────────────────────
# Per-org breakdown
# ─────────────────────────────────────────────────────────────────────────────
class OpsOrgsView(views.APIView):
    """
    GET /api/grading/ops/orgs/
    List all orgs with classroom count, teacher count, student count,
    and rolling-week cost.
    """

    permission_classes = [IsSuperuser]

    def get(self, request):
        from users.models import Organization

        week_ago = timezone.now() - timedelta(days=7)
        orgs = Organization.objects.all()

        rows = []
        for org in orgs:
            cohort_count = Cohort.objects.filter(org=org).count()
            course_count = Course.objects.filter(org=org).count()
            teacher_count = org.members.filter(role="teacher").count()
            student_count = org.members.filter(role="developer").count()
            cost_7d = LLMCostLog.objects.filter(
                org=org, occurred_at__gte=week_ago,
            ).aggregate(total=Sum("cost_eur"))["total"] or Decimal("0")

            rows.append({
                "id": org.id,
                "name": org.name,
                "slug": org.slug,
                "created_at": org.created_at.isoformat(),
                "cohorts": cohort_count,
                "courses": course_count,
                # Legacy key retained for Workstream A→B transition.
                "classrooms": course_count,
                "teachers": teacher_count,
                "students": student_count,
                "cost_7d_eur": str(cost_7d),
            })

        return Response({"count": len(rows), "results": rows})


# ─────────────────────────────────────────────────────────────────────────────
# Per-course breakdown (was per-classroom)
# ─────────────────────────────────────────────────────────────────────────────
class OpsCoursesView(views.APIView):
    """
    GET /api/grading/ops/courses/?org={id}
    List courses with student count, session count, and cost rollup.
    Student count is derived from the course's cohort (students are
    cohort-scoped, not course-scoped, post Workstream A).
    """

    permission_classes = [IsSuperuser]

    def get(self, request):
        week_ago = timezone.now() - timedelta(days=7)

        qs = Course.objects.select_related("org", "owner", "rubric", "cohort")
        org_id = request.query_params.get("org")
        if org_id:
            qs = qs.filter(org_id=org_id)

        rows = []
        for c in qs:
            student_count = (
                CohortMembership.objects.filter(cohort=c.cohort).count()
                if c.cohort_id
                else 0
            )
            sessions_total = GradingSession.objects.filter(
                submission__course=c,
            ).count()
            sessions_open = GradingSession.objects.filter(
                submission__course=c,
                state__in=[
                    GradingSession.State.PENDING,
                    GradingSession.State.DRAFTED,
                    GradingSession.State.REVIEWING,
                ],
            ).count()
            cost_7d = LLMCostLog.objects.filter(
                course=c, occurred_at__gte=week_ago,
            ).aggregate(total=Sum("cost_eur"))["total"] or Decimal("0")

            rows.append({
                "id": c.id,
                "name": c.name,
                "org_id": c.org_id,
                "org_name": c.org.name,
                "cohort_id": c.cohort_id,
                "cohort_name": c.cohort.name if c.cohort else None,
                "owner_id": c.owner_id,
                "owner_email": c.owner.email,
                "rubric_name": c.rubric.name if c.rubric else None,
                "source_control_type": c.source_control_type,
                "students": student_count,
                "sessions_total": sessions_total,
                "sessions_open": sessions_open,
                "cost_7d_eur": str(cost_7d),
                "created_at": c.created_at.isoformat(),
            })

        return Response({"count": len(rows), "results": rows})


# Legacy alias retained for any URL imports/tests still on the old name.
OpsClassroomsView = OpsCoursesView


# ─────────────────────────────────────────────────────────────────────────────
# Per-teacher cost rollup
# ─────────────────────────────────────────────────────────────────────────────
class OpsTeacherCostsView(views.APIView):
    """
    GET /api/grading/ops/teachers/
    One row per teacher (docent): classroom count, sessions-per-week,
    rolling cost. Flagged if over threshold.
    """

    permission_classes = [IsSuperuser]

    def get(self, request):
        from users.models import User

        week_ago = timezone.now() - timedelta(days=7)
        teachers = User.objects.filter(role="teacher").select_related("organization")

        rows = []
        for t in teachers:
            course_count = Course.objects.filter(owner=t).count()
            sessions_posted_7d = GradingSession.objects.filter(
                submission__course__owner=t,
                posted_at__gte=week_ago,
                state=GradingSession.State.POSTED,
            ).count()
            cost_7d = LLMCostLog.objects.filter(
                docent=t, occurred_at__gte=week_ago,
            ).aggregate(total=Sum("cost_eur"))["total"] or Decimal("0")

            rows.append({
                "id": t.id,
                "email": t.email,
                "display_name": t.display_name,
                "org_id": t.organization_id,
                "org_name": t.organization.name if t.organization else None,
                "courses": course_count,
                # Legacy key for Workstream A→B transition.
                "classrooms": course_count,
                "sessions_posted_7d": sessions_posted_7d,
                "cost_7d_eur": str(cost_7d),
                "over_threshold": cost_7d > WEEKLY_COST_ALERT_EUR,
                "threshold_eur": str(WEEKLY_COST_ALERT_EUR),
            })

        # Highest cost first so the top spenders are visible
        rows.sort(key=lambda r: Decimal(r["cost_7d_eur"]), reverse=True)
        return Response({"count": len(rows), "results": rows})


# ─────────────────────────────────────────────────────────────────────────────
# Recent LLM call log (read-only view into LLMCostLog)
# ─────────────────────────────────────────────────────────────────────────────
class OpsLLMCallLogView(views.APIView):
    """
    GET /api/grading/ops/llm-log/?limit=100&tier=premium
    Recent LLM calls across the platform for debugging / cost triage.
    """

    permission_classes = [IsSuperuser]

    def get(self, request):
        limit = min(int(request.query_params.get("limit", 100)), 500)
        qs = LLMCostLog.objects.select_related("docent", "org", "course").order_by(
            "-occurred_at",
        )
        tier = request.query_params.get("tier")
        if tier:
            qs = qs.filter(tier=tier)
        docent_id = request.query_params.get("docent")
        if docent_id:
            qs = qs.filter(docent_id=docent_id)
        org_id = request.query_params.get("org")
        if org_id:
            qs = qs.filter(org_id=org_id)

        rows = [
            {
                "id": r.id,
                "tier": r.tier,
                "model_name": r.model_name,
                "tokens_in": r.tokens_in,
                "tokens_out": r.tokens_out,
                "cost_eur": str(r.cost_eur),
                "latency_ms": r.latency_ms,
                "ceiling_rejected": r.ceiling_rejected,
                "docent_email": r.docent.email if r.docent else None,
                "course_name": r.course.name if r.course else None,
                "org_name": r.org.name if r.org else None,
                "occurred_at": r.occurred_at.isoformat(),
            }
            for r in qs[:limit]
        ]
        return Response({"count": len(rows), "results": rows})


# ─────────────────────────────────────────────────────────────────────────────
# Workstream I1 — passive weekly metrics
# ─────────────────────────────────────────────────────────────────────────────
class IsOrgAdminOrSuperuser(permissions.BasePermission):
    """Org admin OR superuser. Wider than IsSuperuser for the weekly report."""

    message = "Organization admin (or superuser) required."

    def has_permission(self, request, view) -> bool:
        return _is_admin(request.user)


class OpsWeeklyMetricsView(views.APIView):
    """
    GET /api/grading/ops/metrics/weekly/?start=YYYY-MM-DD&end=YYYY-MM-DD

    Per-org, per-cohort teacher activity + cost signals for the period.
    Admins see only their own org; superusers see all orgs.

    Defaults to last 7 days ending today if params omitted.
    """

    permission_classes = [IsOrgAdminOrSuperuser]

    def get(self, request):
        from rest_framework.exceptions import ValidationError

        try:
            start, end = parse_period(
                request.query_params.get("start"),
                request.query_params.get("end"),
            )
        except ValueError as exc:
            raise ValidationError(
                {"detail": f"Invalid date: {exc}. Expected YYYY-MM-DD."},
            )

        if start > end:
            raise ValidationError({"detail": "start must be <= end."})

        user = request.user
        if getattr(user, "is_superuser", False):
            org_ids = None  # all orgs
        else:
            org_id = getattr(user, "organization_id", None)
            org_ids = [org_id] if org_id else []

        granularity = request.query_params.get("granularity", "weekly")
        if granularity == "daily":
            report = compute_daily_breakdown(start, end, org_ids=org_ids)
        else:
            report = compute_weekly_metrics(start, end, org_ids=org_ids)
        return Response(report)
