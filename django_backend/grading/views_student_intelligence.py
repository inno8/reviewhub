"""
Workstream D — Teacher-facing student intelligence endpoints.

These endpoints power the grading-app UI (StudentSnapshotPanel on the
session detail view + TeacherStudentProfileView at /grading/students/{id}).
They are deliberately shaped for the teacher's "what does this student
need from me right now" question, not the student's own dashboard.

Endpoints:
  GET /api/grading/students/<student_id>/snapshot/
  GET /api/grading/students/<student_id>/trajectory/?weeks=12
  GET /api/grading/students/<student_id>/pr-history/?limit=20

Permission: see `grading.permissions.can_view_student`. Cross-org and
non-authorised access returns 404 (not 403) — same pattern as the rest
of the grading isolation surface.

Design decisions:
  - Read-only. No new migrations. Aggregates existing SkillMetric,
    SkillObservation, LearningProof (skills app) and GradingSession,
    Submission (grading app) + Pattern (evaluations app).
  - Aggregation is across all projects for the student, not filtered by
    cohort/course. v1 does not split SkillMetric by cohort.
  - Suggested interventions is a placeholder for v1.1 — always returns [].
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count
from django.http import Http404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CohortMembership, GradingSession
from .permissions import can_view_student

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────
def _get_student_or_404(requesting_user, student_id: int):
    """
    Resolve student + run visibility check. 404 on miss *or* denied —
    follows existing cross-org isolation pattern.
    """
    try:
        student = User.objects.select_related("organization").get(pk=student_id)
    except User.DoesNotExist:
        raise Http404("student not found")
    if not can_view_student(requesting_user, student):
        raise Http404("student not found")
    return student


def _student_cohort(student):
    """Active cohort membership for a student, or None."""
    m = CohortMembership.objects.filter(
        student=student, removed_at__isnull=True
    ).select_related("cohort").first()
    return m.cohort if m else None


def _student_ref(student, with_cohort: bool = False):
    data = {
        "id": student.id,
        "name": getattr(student, "display_name", "") or student.username or student.email,
        "email": student.email,
    }
    if with_cohort:
        cohort = _student_cohort(student)
        data["cohort"] = (
            {"id": cohort.id, "name": cohort.name} if cohort else None
        )
    return data


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint 1: Snapshot
# ─────────────────────────────────────────────────────────────────────────────
class StudentSnapshotView(APIView):
    """
    GET /api/grading/students/<student_id>/snapshot/

    Lightweight bundle designed to render next to a grading session: skill
    radar by category, top-5 recurring patterns, what's trending up/down,
    and recent activity. Intended for a one-shot fetch.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, student_id: int):
        from evaluations.models import Pattern  # local import to avoid cycles
        from skills.models import SkillMetric, SkillObservation

        student = _get_student_or_404(request.user, student_id)

        # ── Skill radar ──────────────────────────────────────────────────
        # Aggregate SkillMetric per category. Prefer bayesian_score when the
        # metric has any observations — falls back to legacy `score` so early
        # students (pre-Bayesian) still show up.
        metrics = (
            SkillMetric.objects
            .filter(user=student)
            .select_related("skill__category")
        )

        cat_scores: dict[str, list[float]] = defaultdict(list)
        cat_confidences: dict[str, list[float]] = defaultdict(list)
        cat_levels: dict[str, list[str]] = defaultdict(list)
        cat_trends: dict[str, list[str]] = defaultdict(list)

        for m in metrics:
            score = m.bayesian_score if m.observation_count > 0 else m.score
            if score is None:
                continue
            cat = m.skill.category.name
            cat_scores[cat].append(float(score))
            cat_confidences[cat].append(float(m.confidence or 0.0))
            if m.level_label:
                cat_levels[cat].append(m.level_label)
            cat_trends[cat].append(m.trend or "stable")

        # Trend by category: compare last-4-weeks avg observation score vs
        # previous-4-weeks. This gives a per-category up/down/stable label
        # that's more honest than just copying the per-metric trend field.
        now = timezone.now()
        recent_cut = now - timedelta(weeks=4)
        prior_cut = now - timedelta(weeks=8)
        recent_obs = (
            SkillObservation.objects
            .filter(user=student, created_at__gte=recent_cut)
            .select_related("skill__category")
        )
        prior_obs = (
            SkillObservation.objects
            .filter(user=student, created_at__gte=prior_cut, created_at__lt=recent_cut)
            .select_related("skill__category")
        )

        recent_by_cat: dict[str, list[float]] = defaultdict(list)
        prior_by_cat: dict[str, list[float]] = defaultdict(list)
        for o in recent_obs:
            recent_by_cat[o.skill.category.name].append(float(o.weighted_score))
        for o in prior_obs:
            prior_by_cat[o.skill.category.name].append(float(o.weighted_score))

        def _avg(xs):
            return sum(xs) / len(xs) if xs else None

        radar = []
        trending_up: list[str] = []
        trending_down: list[str] = []
        for cat, scores in cat_scores.items():
            avg_score = round(sum(scores) / len(scores), 1)
            avg_conf = round(
                sum(cat_confidences[cat]) / len(cat_confidences[cat]), 2
            ) if cat_confidences[cat] else 0.0
            # Prefer a level label that appears; else None.
            level = cat_levels[cat][0] if cat_levels[cat] else None

            # Trend: per-category delta across the two 4-week windows.
            r_avg = _avg(recent_by_cat.get(cat, []))
            p_avg = _avg(prior_by_cat.get(cat, []))
            if r_avg is not None and p_avg is not None:
                delta = r_avg - p_avg
                if delta > 2:
                    trend = "up"
                    trending_up.append(cat)
                elif delta < -2:
                    trend = "down"
                    trending_down.append(cat)
                else:
                    trend = "stable"
            else:
                # Fall back to the dominant per-metric trend in this cat.
                trend_counts: dict[str, int] = defaultdict(int)
                for t in cat_trends[cat]:
                    trend_counts[t] += 1
                trend = max(trend_counts, key=trend_counts.get) if trend_counts else "stable"

            radar.append({
                "category": cat,
                "score": avg_score,
                "confidence": avg_conf,
                "level_label": level,
                "trend": trend,
            })

        radar.sort(key=lambda r: r["category"])

        # ── Recurring patterns (top-5 unresolved) ────────────────────────
        patterns_qs = (
            Pattern.objects
            .filter(user=student, is_resolved=False)
            .order_by("-frequency", "-last_seen")[:5]
        )
        recurring = []
        for p in patterns_qs:
            days_ago = (
                (now - p.last_seen).days if p.last_seen else None
            )
            # Crude severity: high frequency → warning, else info.
            severity = "warning" if p.frequency >= 3 else "info"
            recurring.append({
                "pattern_key": p.pattern_key,
                "pattern_type": p.pattern_type,
                "frequency": p.frequency,
                "last_seen_days_ago": days_ago,
                "severity": severity,
            })

        # ── Recent activity ──────────────────────────────────────────────
        thirty_days_ago = now - timedelta(days=30)
        prs_last_30d = (
            GradingSession.objects
            .filter(
                submission__student=student,
                created_at__gte=thirty_days_ago,
            )
            .count()
        )
        # Avg bayesian_score across all metrics with observations.
        bayes_rows = [
            m.bayesian_score for m in metrics
            if m.observation_count > 0 and m.bayesian_score is not None
        ]
        avg_bayes = round(sum(bayes_rows) / len(bayes_rows), 1) if bayes_rows else 0.0

        return Response({
            "student": _student_ref(student, with_cohort=True),
            "skill_radar": radar,
            "recurring_patterns": recurring,
            "trending_up": trending_up,
            "trending_down": trending_down,
            "recent_activity": {
                "prs_last_30d": prs_last_30d,
                "avg_bayesian_score": avg_bayes,
            },
            # v1.1 placeholder: recommender lives in a future skill/service.
            "suggested_interventions": [],
        })


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint 2: Trajectory
# ─────────────────────────────────────────────────────────────────────────────
class StudentTrajectoryView(APIView):
    """
    GET /api/grading/students/<student_id>/trajectory/?weeks=12

    Weekly aggregated skill evolution + milestones for a timeline UI.
    Reuses the per-category bucketing logic from DeveloperJourneyView but
    aggregates weekly (not per-day) so the UI can draw clean trend lines.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, student_id: int):
        from evaluations.models import Evaluation, Finding
        from skills.models import LearningProof, SkillObservation

        student = _get_student_or_404(request.user, student_id)

        try:
            weeks = int(request.query_params.get("weeks", 12))
        except (TypeError, ValueError):
            weeks = 12
        weeks = max(1, min(weeks, 52))

        now = timezone.now()
        start = now - timedelta(weeks=weeks)
        # Normalise to Monday at 00:00 for consistent bucketing.
        start_monday = (start - timedelta(days=start.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        # ── Weekly skill evolution ───────────────────────────────────────
        obs_qs = (
            SkillObservation.objects
            .filter(user=student, created_at__gte=start_monday)
            .select_related("skill__category")
        )
        # Bucket: { week_start_str: { category: [scores] } }
        buckets: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        for o in obs_qs:
            wk = (o.created_at - timedelta(days=o.created_at.weekday())).date()
            buckets[wk.isoformat()][o.skill.category.name].append(float(o.weighted_score))

        # PR + finding counts per week (cheap aggregation).
        evals = Evaluation.objects.for_user(student).filter(created_at__gte=start_monday)
        evals_by_week: dict[str, int] = defaultdict(int)
        for ev_created in evals.values_list("created_at", flat=True):
            wk = (ev_created - timedelta(days=ev_created.weekday())).date()
            evals_by_week[wk.isoformat()] += 1

        findings_by_week: dict[str, int] = defaultdict(int)
        findings_qs = (
            Finding.objects
            .filter(evaluation__in=evals)
            .values_list("created_at", flat=True)
        )
        for f_created in findings_qs:
            wk = (f_created - timedelta(days=f_created.weekday())).date()
            findings_by_week[wk.isoformat()] += 1

        # Build ordered week list (chronological — oldest first).
        weeks_out = []
        cur = start_monday
        end_monday = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        while cur <= end_monday:
            wk_key = cur.date().isoformat()
            cat_avgs = {
                cat: round(sum(scores) / len(scores), 1)
                for cat, scores in buckets.get(wk_key, {}).items()
            }
            weeks_out.append({
                "week_start": wk_key,
                "avg_score_per_category": cat_avgs,
                "prs_count": evals_by_week.get(wk_key, 0),
                "findings_count": findings_by_week.get(wk_key, 0),
            })
            cur += timedelta(weeks=1)

        # ── Milestones (learning proofs) ─────────────────────────────────
        proof_qs = (
            LearningProof.objects
            .filter(user=student)
            .select_related("skill")
            .order_by("created_at")
        )
        milestones = []
        for p in proof_qs:
            if p.status == "proven" and p.proven_at:
                milestones.append({
                    "date": p.proven_at.date().isoformat(),
                    "event": "Concept proven",
                    "skill": p.skill.name,
                })
            elif p.status == "reinforced" and p.proven_at:
                milestones.append({
                    "date": p.proven_at.date().isoformat(),
                    "event": "Concept reinforced",
                    "skill": p.skill.name,
                })
            elif p.status == "relapsed" and p.relapsed_at:
                milestones.append({
                    "date": p.relapsed_at.date().isoformat(),
                    "event": "Relapse detected",
                    "skill": p.skill.name,
                })
        # Chronological.
        milestones.sort(key=lambda m: m["date"] or "")

        return Response({
            "student": _student_ref(student),
            "weeks": weeks_out,
            "milestones": milestones,
        })


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint 3: PR history
# ─────────────────────────────────────────────────────────────────────────────
class StudentPRHistoryView(APIView):
    """
    GET /api/grading/students/<student_id>/pr-history/?limit=20

    Recent grading sessions for this student, shaped for a timeline list UI.
    Uses OrgScopedManager on GradingSession so a requesting teacher can only
    see sessions within their own org (belt-and-braces; visibility is also
    checked by _get_student_or_404).
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, student_id: int):
        student = _get_student_or_404(request.user, student_id)

        try:
            limit = int(request.query_params.get("limit", 20))
        except (TypeError, ValueError):
            limit = 20
        limit = max(1, min(limit, 100))

        # Scope via org. The requester always has the same org as the
        # student at this point (checked above), so for_user is safe.
        qs = (
            GradingSession.objects
            .for_user(request.user)
            .filter(submission__student=student)
            .select_related("submission", "submission__course")
            .order_by("-created_at", "-id")[:limit]
        )

        rows = []
        for s in qs:
            sub = s.submission
            # rubric_score_avg: mean of final_scores if populated, else
            # mean of ai_draft_scores — numeric "score" fields only.
            source = s.final_scores or s.ai_draft_scores or {}
            numeric = []
            for v in source.values():
                if isinstance(v, dict) and isinstance(v.get("score"), (int, float)):
                    numeric.append(float(v["score"]))
                elif isinstance(v, (int, float)):
                    numeric.append(float(v))
            avg_score = round(sum(numeric) / len(numeric), 2) if numeric else None

            rows.append({
                "id": s.id,
                "pr_url": sub.pr_url,
                "pr_number": sub.pr_number,
                "pr_title": sub.pr_title or "",
                "repo_full_name": sub.repo_full_name,
                "submitted_at": sub.created_at.isoformat() if sub.created_at else None,
                "graded_at": s.posted_at.isoformat() if s.posted_at else None,
                "state": s.state,
                "rubric_score_avg": avg_score,
                "findings_count": len(s.ai_draft_comments or []),
                "course_name": sub.course.name if sub.course else None,
            })

        return Response({
            "student": _student_ref(student),
            "sessions": rows,
        })
