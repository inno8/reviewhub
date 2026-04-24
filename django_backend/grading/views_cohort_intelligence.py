"""
Cohort-level intelligence endpoints — the teacher's "what's happening in my
klas this week?" view. Distinct from the grading inbox (per-PR) and the
student profile (one-student deep-dive) — this is per-cohort aggregation.

Endpoints:
  GET /api/grading/cohorts/<cohort_id>/overview/

Permission: same helper used by CohortRecurringErrorsView — teacher owning
a course in the cohort, admin in the same org, or superuser.  Cross-org
returns 404 (isolation pattern).  Students get 403 (cohort exists but they
can't see aggregate intelligence).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.http import Http404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Cohort, CohortMembership, Course, GradingSession, Submission
from .views_student_intelligence import (
    CREBO_SKILL_SLUGS,
    _build_criterion_meta_for_student,
    _can_view_cohort_intelligence,
)

User = get_user_model()


# "Op opleidingsniveau" = score 3 on 1-4 rubric ≈ 75 on bayesian 0-100.
# A student with bayesian_score < 75 is "below niveau" for that skill.
BAYES_ON_NIVEAU = 75.0

# Band thresholds for EINDBEOORDELING (matches rubric level labels).
def _band_for_score(avg_score_1to4: float) -> str:
    """Map a 0-4 rubric average → Dutch band label."""
    if avg_score_1to4 < 1.75:
        return "onvoldoende"
    if avg_score_1to4 < 2.5:
        return "net-aan"
    if avg_score_1to4 < 3.5:
        return "voldoende"
    return "goed"


def _bayes_to_rubric(bayes_0to100: float) -> float:
    """Convert a 0-100 Bayesian score back to the 1-4 rubric scale.

    Rough inverse of the linear mapping used when rubric scores are blended
    into SkillMetric.bayesian_score (score 1 → 25, 2 → 50, 3 → 75, 4 → 100).
    """
    return round(max(0.0, min(4.0, bayes_0to100 / 25.0)), 2)


class CohortOverviewView(APIView):
    """
    GET /api/grading/cohorts/<cohort_id>/overview/

    Returns the teacher's cohort dashboard:
      - Cohort header (name, course name, student count, org slug)
      - Activity summary: PRs this sprint, waiting feedback, posted
      - weakest_criteria (top-3 criteria where the cohort is lowest)
      - cohort_patterns (patterns appearing in 2+ students)
      - students (per-student summary row)
      - weekly_activity (8 weeks of PR count + avg score)

    "This sprint" is interpreted as the last 14 days (calendar window).
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, cohort_id: int):
        from evaluations.models import Pattern
        from skills.models import SkillMetric

        # Fetch cohort scoped by org (cross-org → 404).
        try:
            cohort = (
                Cohort.objects
                .select_related("org")
                .prefetch_related("courses", "courses__rubric")
                .get(pk=cohort_id)
            )
        except Cohort.DoesNotExist:
            raise Http404("cohort not found")

        user = request.user
        if not getattr(user, "is_superuser", False):
            user_org = getattr(user, "organization_id", None)
            if user_org is None or cohort.org_id != user_org:
                raise Http404("cohort not found")

        if not _can_view_cohort_intelligence(user, cohort):
            # Student enrolled here → 403 (role-gated, not enumerating).
            is_enrolled_student = CohortMembership.objects.filter(
                cohort=cohort, student=user, removed_at__isnull=True
            ).exists()
            if is_enrolled_student:
                return Response(
                    {"detail": "Teacher or admin role required for this view."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            raise Http404("cohort not found")

        # ── Active students in the cohort ────────────────────────────────
        memberships = list(
            CohortMembership.objects
            .filter(cohort=cohort, removed_at__isnull=True)
            .select_related("student")
            .order_by("joined_at")
        )
        students = [m.student for m in memberships]
        student_ids = [s.id for s in students]
        student_count = len(student_ids)

        # Criterion display metadata: seed from any student in the cohort.
        # All students in a cohort share the same courses/rubrics, so using
        # the first student yields the correct slug→name+kerntaak map.
        if students:
            criterion_meta = _build_criterion_meta_for_student(students[0])
        else:
            from .rubric_defaults import CREBO_RUBRIC_CRITERIA
            criterion_meta = {
                c["id"]: {"name": c["name"], "kerntaak": c.get("kerntaak")}
                for c in CREBO_RUBRIC_CRITERIA
            }

        now = timezone.now()
        sprint_start = now - timedelta(days=14)
        eight_weeks_ago = now - timedelta(weeks=8)
        four_weeks_ago = now - timedelta(weeks=4)

        # ── Cohort + course header info ──────────────────────────────────
        courses = list(cohort.courses.filter(archived_at__isnull=True))
        if courses:
            course_name = ", ".join(c.name for c in courses)
        else:
            course_name = None

        # ── Activity counts ──────────────────────────────────────────────
        subs_in_cohort_qs = Submission.objects.filter(
            course__cohort=cohort, student_id__in=student_ids
        )
        sessions_in_cohort_qs = GradingSession.objects.filter(
            submission__in=subs_in_cohort_qs
        )

        prs_this_sprint = subs_in_cohort_qs.filter(created_at__gte=sprint_start).count()
        prs_waiting_feedback = sessions_in_cohort_qs.filter(
            state__in=[
                GradingSession.State.PENDING,
                GradingSession.State.DRAFTING,
                GradingSession.State.DRAFTED,
                GradingSession.State.REVIEWING,
                GradingSession.State.PARTIAL,
            ]
        ).count()
        prs_posted_this_sprint = sessions_in_cohort_qs.filter(
            state=GradingSession.State.POSTED,
            posted_at__gte=sprint_start,
        ).count()

        # ── Per-skill aggregation across all students ────────────────────
        # For each Crebo slug, gather bayesian_scores + confidence_weighted
        # avg across the cohort, count students < "op niveau" threshold.
        metrics_qs = (
            SkillMetric.objects
            .filter(user_id__in=student_ids, skill__slug__in=CREBO_SKILL_SLUGS)
            .select_related("skill")
        )

        # slug → {student_id: [(score, weight)]}
        per_slug_student: dict[str, dict[int, list[tuple[float, float]]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for m in metrics_qs:
            if m.observation_count <= 0:
                continue
            score = m.bayesian_score
            if score is None:
                continue
            weight = float(max(m.observation_count, 1))
            per_slug_student[m.skill.slug][m.user_id].append((float(score), weight))

        weakest_rows = []
        for slug in CREBO_SKILL_SLUGS:
            meta = criterion_meta.get(slug, {})
            per_student = per_slug_student.get(slug, {})
            if not per_student:
                continue
            student_scores_bayes: list[float] = []
            students_below = 0
            for sid, pairs in per_student.items():
                total_w = sum(w for _s, w in pairs) or 1.0
                weighted = sum(s * w for s, w in pairs) / total_w
                student_scores_bayes.append(weighted)
                if weighted < BAYES_ON_NIVEAU:
                    students_below += 1
            cohort_avg_bayes = sum(student_scores_bayes) / len(student_scores_bayes)
            avg_rubric = _bayes_to_rubric(cohort_avg_bayes)

            # Recurring-patterns-in-this-skill-category count:
            # pattern_type is a rough category label; count distinct pattern_keys
            # where ≥2 students in cohort are affected AND pattern_type matches
            # the skill category heuristic.  We fall back to 0 if no mapping.
            recurring_patterns_count = 0  # filled in after the pattern block

            weakest_rows.append({
                "slug": slug,
                "display_name": meta.get("name") or slug.replace("_", " ").title(),
                "kerntaak": meta.get("kerntaak"),
                "avg_bayesian": round(cohort_avg_bayes, 1),
                "avg_score": avg_rubric,
                "students_below_niveau": students_below,
                "recurring_patterns_count": recurring_patterns_count,
                "trend": "stable",  # v1: trend computed below per-skill
            })

        # Per-skill trend over the last 4 weeks vs prior 4 weeks.
        from skills.models import SkillObservation
        recent_obs = (
            SkillObservation.objects
            .filter(
                user_id__in=student_ids,
                skill__slug__in=CREBO_SKILL_SLUGS,
                created_at__gte=four_weeks_ago,
            )
            .select_related("skill")
        )
        prior_obs = (
            SkillObservation.objects
            .filter(
                user_id__in=student_ids,
                skill__slug__in=CREBO_SKILL_SLUGS,
                created_at__gte=eight_weeks_ago,
                created_at__lt=four_weeks_ago,
            )
            .select_related("skill")
        )
        recent_by_slug: dict[str, list[float]] = defaultdict(list)
        prior_by_slug: dict[str, list[float]] = defaultdict(list)
        for o in recent_obs:
            recent_by_slug[o.skill.slug].append(float(o.weighted_score))
        for o in prior_obs:
            prior_by_slug[o.skill.slug].append(float(o.weighted_score))

        def _avg(xs):
            return sum(xs) / len(xs) if xs else None

        for row in weakest_rows:
            r = _avg(recent_by_slug.get(row["slug"], []))
            p = _avg(prior_by_slug.get(row["slug"], []))
            if r is not None and p is not None:
                d = r - p
                row["trend"] = "up" if d > 2 else ("down" if d < -2 else "stable")
            # else leave "stable"

        # Sort ascending by avg_bayesian; take 3 lowest.
        weakest_rows.sort(key=lambda r: (r["avg_bayesian"], r["slug"]))
        weakest_criteria = weakest_rows[:3]

        # ── Cohort patterns (≥2 students affected) ───────────────────────
        patterns_qs = (
            Pattern.objects
            .filter(user_id__in=student_ids, is_resolved=False)
        )
        by_key: dict[str, dict] = {}
        for p in patterns_qs:
            bucket = by_key.setdefault(p.pattern_key, {
                "pattern_key": p.pattern_key,
                "pattern_type": p.pattern_type,
                "users": set(),
                "total_frequency": 0,
                "last_seen": None,
            })
            bucket["users"].add(p.user_id)
            bucket["total_frequency"] += int(p.frequency or 0)
            if p.last_seen and (bucket["last_seen"] is None or p.last_seen > bucket["last_seen"]):
                bucket["last_seen"] = p.last_seen

        cohort_patterns = []
        for b in by_key.values():
            affected = len(b["users"])
            if affected < 2:
                continue
            days_ago = (now - b["last_seen"]).days if b["last_seen"] else None
            cohort_patterns.append({
                "pattern_key": b["pattern_key"],
                "pattern_type": b["pattern_type"],
                "affected_student_count": affected,
                "total_frequency": b["total_frequency"],
                "last_seen_days_ago": days_ago,
            })
        cohort_patterns.sort(
            key=lambda r: (-r["affected_student_count"], -r["total_frequency"], r["pattern_key"])
        )
        cohort_patterns = cohort_patterns[:10]

        # Back-fill recurring_patterns_count on weakest_criteria by rough
        # pattern_type → skill slug mapping.
        TYPE_TO_SLUG = {
            "security": "veiligheid",
            "validation": "veiligheid",
            "testing": "testen",
            "error_handling": "code_kwaliteit",
            "code_quality": "code_kwaliteit",
        }
        pattern_counts_by_slug: dict[str, int] = defaultdict(int)
        for cp in cohort_patterns:
            slug = TYPE_TO_SLUG.get(cp["pattern_type"])
            if slug:
                pattern_counts_by_slug[slug] += 1
        for row in weakest_criteria:
            row["recurring_patterns_count"] = pattern_counts_by_slug.get(row["slug"], 0)

        # Rename back to the response shape.
        weakest_out = [
            {
                "skill_slug": r["slug"],
                "display_name": r["display_name"],
                "kerntaak": r["kerntaak"],
                "avg_score": r["avg_score"],
                "students_below_niveau": r["students_below_niveau"],
                "recurring_patterns_count": r["recurring_patterns_count"],
                "trend": r["trend"],
            }
            for r in weakest_criteria
        ]

        # ── Per-student rows ─────────────────────────────────────────────
        # Last submission + open-session counts per student.
        last_sub_by_student: dict[int, object] = {}
        for sub_created, sid in subs_in_cohort_qs.values_list("created_at", "student_id"):
            cur = last_sub_by_student.get(sid)
            if cur is None or sub_created > cur:
                last_sub_by_student[sid] = sub_created

        waiting_by_student: dict[int, int] = defaultdict(int)
        for sess_sid in sessions_in_cohort_qs.filter(
            state__in=[
                GradingSession.State.PENDING,
                GradingSession.State.DRAFTING,
                GradingSession.State.DRAFTED,
                GradingSession.State.REVIEWING,
                GradingSession.State.PARTIAL,
            ]
        ).values_list("submission__student_id", flat=True):
            waiting_by_student[sess_sid] += 1

        students_out = []
        for s in students:
            # per-skill aggregates for this student (from metrics_qs)
            this_student_slug_agg: dict[str, tuple[float, float]] = {}
            for slug in CREBO_SKILL_SLUGS:
                pairs = per_slug_student.get(slug, {}).get(s.id, [])
                if not pairs:
                    continue
                total_w = sum(w for _sc, w in pairs) or 1.0
                weighted = sum(sc * w for sc, w in pairs) / total_w
                this_student_slug_agg[slug] = (weighted, total_w)

            if this_student_slug_agg:
                scores_b = [v[0] for v in this_student_slug_agg.values()]
                eindniveau_bayes = sum(scores_b) / len(scores_b)
                eindniveau = _bayes_to_rubric(eindniveau_bayes)
                band = _band_for_score(eindniveau)
            else:
                eindniveau_bayes = None
                eindniveau = None
                band = None

            # Strongest / weakest criterion
            strongest = None
            weakest = None
            if this_student_slug_agg:
                best_slug = max(this_student_slug_agg.items(), key=lambda kv: kv[1][0])
                worst_slug = min(this_student_slug_agg.items(), key=lambda kv: kv[1][0])
                strongest = {
                    "slug": best_slug[0],
                    "score": _bayes_to_rubric(best_slug[1][0]),
                }
                weakest = {
                    "slug": worst_slug[0],
                    "score": _bayes_to_rubric(worst_slug[1][0]),
                }

            # Trend for this student: last-4w vs prior-4w avg weighted_score.
            student_recent = [
                float(o.weighted_score) for o in recent_obs if o.user_id == s.id
            ]
            student_prior = [
                float(o.weighted_score) for o in prior_obs if o.user_id == s.id
            ]
            r = _avg(student_recent)
            p = _avg(student_prior)
            if r is not None and p is not None:
                d = r - p
                trend = "up" if d > 2 else ("down" if d < -2 else "stable")
            else:
                trend = "stable"

            # last-PR days ago
            last_sub = last_sub_by_student.get(s.id)
            last_pr_days_ago = (now - last_sub).days if last_sub else None

            students_out.append({
                "id": s.id,
                "name": getattr(s, "display_name", "") or s.username or s.email,
                "email": s.email,
                "eindniveau": eindniveau,
                "band": band,
                "trend": trend,
                "last_pr_days_ago": last_pr_days_ago,
                "prs_waiting_feedback": waiting_by_student.get(s.id, 0),
                "strongest_criterion": strongest,
                "weakest_criterion": weakest,
            })

        # ── Weekly activity (last 8 weeks) ───────────────────────────────
        # Normalise to Monday for consistent buckets.
        start_monday = (eight_weeks_ago - timedelta(days=eight_weeks_ago.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        # PR count per week
        pr_by_week: dict[str, int] = defaultdict(int)
        for created_at in subs_in_cohort_qs.filter(
            created_at__gte=start_monday
        ).values_list("created_at", flat=True):
            wk = (created_at - timedelta(days=created_at.weekday())).date().isoformat()
            pr_by_week[wk] += 1

        # Avg score per week: pull sessions with final_scores or ai_draft_scores.
        score_by_week: dict[str, list[float]] = defaultdict(list)
        for sess in sessions_in_cohort_qs.filter(
            created_at__gte=start_monday
        ).only("created_at", "final_scores", "ai_draft_scores"):
            src = sess.final_scores or sess.ai_draft_scores or {}
            numeric = []
            for v in src.values():
                if isinstance(v, dict) and isinstance(v.get("score"), (int, float)):
                    numeric.append(float(v["score"]))
                elif isinstance(v, (int, float)):
                    numeric.append(float(v))
            if numeric:
                wk = (sess.created_at - timedelta(days=sess.created_at.weekday())).date().isoformat()
                score_by_week[wk].append(sum(numeric) / len(numeric))

        weekly_activity = []
        cur = start_monday
        end_monday = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        while cur <= end_monday:
            wk_key = cur.date().isoformat()
            avg = sum(score_by_week.get(wk_key, [])) / len(score_by_week[wk_key]) if score_by_week.get(wk_key) else None
            weekly_activity.append({
                "week_start": wk_key,
                "pr_count": pr_by_week.get(wk_key, 0),
                "avg_score": round(avg, 2) if avg is not None else None,
            })
            cur += timedelta(weeks=1)

        return Response({
            "cohort": {
                "id": cohort.id,
                "name": cohort.name,
                "course_name": course_name,
                "student_count": student_count,
                "org_slug": getattr(cohort.org, "slug", None),
            },
            "activity": {
                "prs_this_sprint": prs_this_sprint,
                "prs_waiting_feedback": prs_waiting_feedback,
                "prs_posted_this_sprint": prs_posted_this_sprint,
            },
            "weakest_criteria": weakest_out,
            "cohort_patterns": cohort_patterns,
            "students": students_out,
            "weekly_activity": weekly_activity,
        })
