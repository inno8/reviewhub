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

from .models import Classroom, ClassroomMembership, GradingSession, LLMCostLog
from .services.cost_metering import WEEKLY_COST_ALERT_EUR


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
        total_classrooms = Classroom.objects.count()
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
                "classrooms": total_classrooms,
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
            classroom_count = Classroom.objects.filter(org=org).count()
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
                "classrooms": classroom_count,
                "teachers": teacher_count,
                "students": student_count,
                "cost_7d_eur": str(cost_7d),
            })

        return Response({"count": len(rows), "results": rows})


# ─────────────────────────────────────────────────────────────────────────────
# Per-classroom breakdown
# ─────────────────────────────────────────────────────────────────────────────
class OpsClassroomsView(views.APIView):
    """
    GET /api/grading/ops/classrooms/?org={id}
    List classrooms with student count, session count, and cost rollup.
    """

    permission_classes = [IsSuperuser]

    def get(self, request):
        week_ago = timezone.now() - timedelta(days=7)

        qs = Classroom.objects.select_related("org", "owner", "rubric")
        org_id = request.query_params.get("org")
        if org_id:
            qs = qs.filter(org_id=org_id)

        rows = []
        for c in qs:
            student_count = ClassroomMembership.objects.filter(classroom=c).count()
            sessions_total = GradingSession.objects.filter(
                submission__classroom=c,
            ).count()
            sessions_open = GradingSession.objects.filter(
                submission__classroom=c,
                state__in=[
                    GradingSession.State.PENDING,
                    GradingSession.State.DRAFTED,
                    GradingSession.State.REVIEWING,
                ],
            ).count()
            cost_7d = LLMCostLog.objects.filter(
                classroom=c, occurred_at__gte=week_ago,
            ).aggregate(total=Sum("cost_eur"))["total"] or Decimal("0")

            rows.append({
                "id": c.id,
                "name": c.name,
                "org_id": c.org_id,
                "org_name": c.org.name,
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
            classroom_count = Classroom.objects.filter(owner=t).count()
            sessions_posted_7d = GradingSession.objects.filter(
                submission__classroom__owner=t,
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
                "classrooms": classroom_count,
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
        qs = LLMCostLog.objects.select_related("docent", "org", "classroom").order_by(
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
                "classroom_name": r.classroom.name if r.classroom else None,
                "org_name": r.org.name if r.org else None,
                "occurred_at": r.occurred_at.isoformat(),
            }
            for r in qs[:limit]
        ]
        return Response({"count": len(rows), "results": rows})
