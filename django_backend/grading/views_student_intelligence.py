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

from .models import Cohort, CohortMembership, Course, GradingSession
from .permissions import (
    ADMIN_ROLES,
    IsTeacher,
    _role,
    can_view_student,
)  # _role used by _can_view_cohort_intelligence

User = get_user_model()


# The 6 Crebo criterion slugs that the Nakijken Copilot v1 rubric ships with.
# Hardcoded (rather than imported from rubric_defaults) so the frontend can
# rely on a stable ordered list regardless of what any individual rubric
# happens to contain — this is the teacher-facing intelligence surface.
CREBO_SKILL_SLUGS = [
    "code_ontwerp",
    "code_kwaliteit",
    "veiligheid",
    "testen",
    "verbetering",
    "samenwerking",
]


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


def _build_criterion_meta_for_student(student) -> dict[str, dict]:
    """
    Map criterion slug → {"name": ..., "kerntaak": ...} by unioning the
    `criteria` JSON across every Rubric attached to a Course in the
    student's active cohort. Falls back to the shipped defaults for slugs
    not found (so new orgs with custom rubrics still get a display name).
    """
    from .rubric_defaults import CREBO_RUBRIC_CRITERIA

    meta: dict[str, dict] = {}

    # Seed from shipped defaults.
    for crit in CREBO_RUBRIC_CRITERIA:
        meta[crit["id"]] = {
            "name": crit.get("name"),
            "kerntaak": crit.get("kerntaak"),
        }

    cohort = _student_cohort(student)
    if cohort is None:
        return meta

    courses = (
        Course.objects
        .filter(cohort=cohort, rubric__isnull=False)
        .select_related("rubric")
    )
    for course in courses:
        rubric = course.rubric
        criteria = getattr(rubric, "criteria", None) or []
        for crit in criteria:
            if not isinstance(crit, dict):
                continue
            cid = crit.get("id")
            if not cid:
                continue
            # Org-level rubric takes precedence over defaults.
            meta[cid] = {
                "name": crit.get("name") or meta.get(cid, {}).get("name"),
                "kerntaak": crit.get("kerntaak") or meta.get(cid, {}).get("kerntaak"),
            }
    return meta


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
        from skills.models import LearningProof, SkillMetric, SkillObservation

        student = _get_student_or_404(request.user, student_id)

        # ── Rubric criterion metadata map (slug → {name, kerntaak}) ──────
        # Built from every Rubric attached to any Course in the student's
        # active cohort — gives us the display_name and kerntaak for each
        # Crebo slug. Falls back to rubric_defaults if nothing is wired yet.
        criterion_meta = _build_criterion_meta_for_student(student)

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

        # ── Per-skill breakdown (6 Crebo criteria) ───────────────────────
        # Mirrors the radar trend calc but per Skill slug instead of per
        # SkillCategory. Keeps a stable, ordered list of the 6 Crebo skills
        # regardless of which ones the student has metrics for yet.
        per_skill_metrics = {
            m.skill.slug: m
            for m in metrics
            if m.skill.slug in CREBO_SKILL_SLUGS
        }
        recent_by_skill: dict[str, list[float]] = defaultdict(list)
        prior_by_skill: dict[str, list[float]] = defaultdict(list)
        for o in recent_obs:
            if o.skill.slug in CREBO_SKILL_SLUGS:
                recent_by_skill[o.skill.slug].append(float(o.weighted_score))
        for o in prior_obs:
            if o.skill.slug in CREBO_SKILL_SLUGS:
                prior_by_skill[o.skill.slug].append(float(o.weighted_score))

        # Any LearningProof rows for this student, keyed by skill slug
        # (latest wins). Today this is almost always empty — the surface
        # is wired, but the flow that writes PENDING/PROVEN/… rows from
        # a Fix & Learn interaction lands post-pitch.
        proofs_by_slug: dict[str, str] = {}
        for lp in (
            LearningProof.objects
            .filter(user=student, skill__slug__in=CREBO_SKILL_SLUGS)
            .select_related("skill")
            .order_by("-updated_at")
        ):
            proofs_by_slug.setdefault(lp.skill.slug, lp.status)

        # Aggregate per-slug (multiple SkillMetric rows per slug — one per
        # project). Weighted by observation_count so a noisy low-observation
        # row doesn't drown out an established one.
        per_skill_rows: dict[str, dict] = {}
        for m in metrics:
            slug = m.skill.slug
            if slug not in CREBO_SKILL_SLUGS:
                continue
            row = per_skill_rows.setdefault(slug, {
                "score_sum": 0.0, "weight_sum": 0.0,
                "conf_sum": 0.0, "conf_weight": 0,
                "observation_count": 0, "level_label": None,
                "skill_name": m.skill.name,
            })
            w = max(m.observation_count, 1)
            score = m.bayesian_score if m.observation_count > 0 else m.score
            if score is not None:
                row["score_sum"] += float(score) * w
                row["weight_sum"] += w
            row["conf_sum"] += float(m.confidence or 0.0)
            row["conf_weight"] += 1
            row["observation_count"] += m.observation_count
            if m.level_label and not row["level_label"]:
                row["level_label"] = m.level_label

        per_skill = []
        for slug in CREBO_SKILL_SLUGS:
            meta = criterion_meta.get(slug, {})
            row = per_skill_rows.get(slug)
            if row and row["weight_sum"] > 0:
                bayes = round(row["score_sum"] / row["weight_sum"], 1)
                confidence = round(
                    row["conf_sum"] / row["conf_weight"], 3
                ) if row["conf_weight"] else 0.0
                obs_count = row["observation_count"]
                level_label = row["level_label"]
                display_name = meta.get("name") or row["skill_name"]
            else:
                # No SkillMetric for this slug yet.
                bayes = None
                confidence = 0.0
                obs_count = 0
                level_label = None
                display_name = meta.get("name") or slug.replace("_", " ").title()

            # Trend: 4-week delta of weighted_score.
            r_avg = _avg(recent_by_skill.get(slug, []))
            p_avg = _avg(prior_by_skill.get(slug, []))
            if r_avg is not None and p_avg is not None:
                delta = round(r_avg - p_avg, 1)
                if delta > 2:
                    trend = "up"
                elif delta < -2:
                    trend = "down"
                else:
                    trend = "stable"
            else:
                delta = 0.0
                trend = "stable"

            item = {
                "skill_slug": slug,
                "display_name": display_name,
                "kerntaak": meta.get("kerntaak"),
                "bayesian_score": bayes,
                "confidence": confidence,
                "observation_count": obs_count,
                "trend": trend,
                "trend_delta": delta,
                "level_label": level_label,
            }
            if slug in proofs_by_slug:
                item["learning_proof_status"] = proofs_by_slug[slug]
            per_skill.append(item)

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
            "per_skill": per_skill,
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

        # ── New query params (opt-in, back-compat) ───────────────────────
        granularity = request.query_params.get("granularity", "category")
        if granularity not in ("category", "skill"):
            granularity = "category"
        include_cohort_mean_raw = request.query_params.get("include_cohort_mean", "")
        include_cohort_mean = str(include_cohort_mean_raw).lower() in ("1", "true", "yes")

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
        # Per-skill bucket: { week_start_str: { slug: [scores] } }
        skill_buckets: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        for o in obs_qs:
            wk = (o.created_at - timedelta(days=o.created_at.weekday())).date()
            buckets[wk.isoformat()][o.skill.category.name].append(float(o.weighted_score))
            if o.skill.slug in CREBO_SKILL_SLUGS:
                skill_buckets[wk.isoformat()][o.skill.slug].append(float(o.weighted_score))

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
        ordered_week_keys: list[str] = []
        cur = start_monday
        end_monday = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        while cur <= end_monday:
            wk_key = cur.date().isoformat()
            ordered_week_keys.append(wk_key)
            cat_avgs = {
                cat: round(sum(scores) / len(scores), 1)
                for cat, scores in buckets.get(wk_key, {}).items()
            }
            week_entry = {
                "week_start": wk_key,
                "avg_score_per_category": cat_avgs,
                "prs_count": evals_by_week.get(wk_key, 0),
                "findings_count": findings_by_week.get(wk_key, 0),
            }
            if granularity == "skill":
                week_entry["avg_score_per_skill"] = {
                    slug: round(sum(scores) / len(scores), 1)
                    for slug, scores in skill_buckets.get(wk_key, {}).items()
                }
            weeks_out.append(week_entry)
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

        response_data = {
            "student": _student_ref(student),
            "weeks": weeks_out,
            "milestones": milestones,
            "granularity": granularity,
        }

        # ── Per-skill series (granularity=skill) ─────────────────────────
        if granularity == "skill":
            criterion_meta = _build_criterion_meta_for_student(student)
            skill_series = []
            for slug in CREBO_SKILL_SLUGS:
                meta = criterion_meta.get(slug, {})
                points = []
                for wk_key in ordered_week_keys:
                    scores = skill_buckets.get(wk_key, {}).get(slug, [])
                    if scores:
                        points.append({
                            "week_start": wk_key,
                            "avg_score": round(sum(scores) / len(scores), 1),
                            "observation_count": len(scores),
                        })
                    else:
                        points.append({
                            "week_start": wk_key,
                            "avg_score": None,
                            "observation_count": 0,
                        })
                skill_series.append({
                    "skill_slug": slug,
                    "display_name": meta.get("name") or slug.replace("_", " ").title(),
                    "kerntaak": meta.get("kerntaak"),
                    "points": points,
                })
            response_data["series"] = skill_series

        # ── Cohort-mean overlay ──────────────────────────────────────────
        if include_cohort_mean:
            cohort = _student_cohort(student)
            cohort_mean: list[dict] = []
            if cohort is not None:
                peer_ids = list(
                    CohortMembership.objects
                    .filter(cohort=cohort, removed_at__isnull=True)
                    .exclude(student_id=student.id)
                    .values_list("student_id", flat=True)
                )
                if peer_ids:
                    peer_obs = (
                        SkillObservation.objects
                        .filter(user_id__in=peer_ids, created_at__gte=start_monday)
                        .select_related("skill__category")
                        .values(
                            "user_id", "created_at",
                            "skill__slug", "skill__category__name",
                            "weighted_score",
                        )
                    )
                    if granularity == "skill":
                        # { slug: { wk_key: { 'scores': [...], 'users': set() } } }
                        agg: dict[str, dict[str, dict]] = defaultdict(
                            lambda: defaultdict(lambda: {"scores": [], "users": set()})
                        )
                        for o in peer_obs:
                            slug = o["skill__slug"]
                            if slug not in CREBO_SKILL_SLUGS:
                                continue
                            created = o["created_at"]
                            wk = (created - timedelta(days=created.weekday())).date().isoformat()
                            bucket = agg[slug][wk]
                            bucket["scores"].append(float(o["weighted_score"]))
                            bucket["users"].add(o["user_id"])
                        criterion_meta = _build_criterion_meta_for_student(student)
                        for slug in CREBO_SKILL_SLUGS:
                            meta = criterion_meta.get(slug, {})
                            points = []
                            for wk_key in ordered_week_keys:
                                b = agg.get(slug, {}).get(wk_key)
                                if b and b["scores"]:
                                    points.append({
                                        "week_start": wk_key,
                                        "avg_score": round(
                                            sum(b["scores"]) / len(b["scores"]), 1
                                        ),
                                        "student_count": len(b["users"]),
                                    })
                                else:
                                    points.append({
                                        "week_start": wk_key,
                                        "avg_score": None,
                                        "student_count": 0,
                                    })
                            cohort_mean.append({
                                "key": slug,
                                "skill_slug": slug,
                                "display_name": (
                                    meta.get("name")
                                    or slug.replace("_", " ").title()
                                ),
                                "kerntaak": meta.get("kerntaak"),
                                "points": points,
                            })
                    else:
                        # { category: { wk_key: { 'scores': [...], 'users': set() } } }
                        agg: dict[str, dict[str, dict]] = defaultdict(
                            lambda: defaultdict(lambda: {"scores": [], "users": set()})
                        )
                        for o in peer_obs:
                            cat = o["skill__category__name"]
                            created = o["created_at"]
                            wk = (created - timedelta(days=created.weekday())).date().isoformat()
                            bucket = agg[cat][wk]
                            bucket["scores"].append(float(o["weighted_score"]))
                            bucket["users"].add(o["user_id"])
                        for cat in sorted(agg.keys()):
                            points = []
                            for wk_key in ordered_week_keys:
                                b = agg.get(cat, {}).get(wk_key)
                                if b and b["scores"]:
                                    points.append({
                                        "week_start": wk_key,
                                        "avg_score": round(
                                            sum(b["scores"]) / len(b["scores"]), 1
                                        ),
                                        "student_count": len(b["users"]),
                                    })
                                else:
                                    points.append({
                                        "week_start": wk_key,
                                        "avg_score": None,
                                        "student_count": 0,
                                    })
                            cohort_mean.append({
                                "key": cat,
                                "points": points,
                            })
            response_data["cohort_mean"] = cohort_mean

        return Response(response_data)


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
                "iteration_number": s.iteration_number,
                "is_superseded": s.superseded_by_id is not None,
            })

        return Response({
            "student": _student_ref(student),
            "sessions": rows,
        })


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint 4: Cohort-wide recurring errors (teacher-only intelligence)
# ─────────────────────────────────────────────────────────────────────────────
def _can_view_cohort_intelligence(user, cohort) -> bool:
    """
    Teacher-or-admin only view of aggregated cohort patterns.

    Returns a tri-state via exception-free bool semantics:
      - True  → allow (200)
      - False → caller decides 403 (role gated) vs 404 (org gated) via
                _cohort_access_denied_reason() below.

    This function only returns True/False; the view inspects the reason to
    choose the HTTP status.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    # Cross-org: deny (404 upstream).
    user_org = getattr(user, "organization_id", None)
    if user_org is None or cohort.org_id != user_org:
        return False
    role = _role(user)
    if role in ADMIN_ROLES:
        return True
    if role == "teacher":
        return (
            cohort.courses.filter(owner=user).exists()
            or cohort.courses.filter(secondary_docent=user).exists()
        )
    # Students (or other roles): explicitly denied (403, not 404).
    return False


class CohortRecurringErrorsView(APIView):
    """
    GET /api/grading/cohorts/<cohort_id>/recurring-errors/

    Returns the top unresolved `Pattern` records aggregated across all
    currently-enrolled students in a cohort — "what is my class weak at".

    Permission matrix:
      - superuser: 200
      - admin in same org: 200
      - teacher owning (or secondary on) a course in this cohort: 200
      - student (any): 403 — teacher-only intelligence
      - anyone else in a different org: 404 (follows isolation pattern)
      - unauthenticated: 401
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, cohort_id: int):
        from evaluations.models import Finding, Pattern  # local import

        # Scope cohort lookup to the requester's org (cross-org → 404).
        # Superusers/admins of the same org see it; others follow the
        # permission helper.
        try:
            cohort = Cohort.objects.select_related("org").get(pk=cohort_id)
        except Cohort.DoesNotExist:
            raise Http404("cohort not found")

        user = request.user

        # Cross-org anyone (incl. admin of a different org) → 404.
        if not getattr(user, "is_superuser", False):
            user_org = getattr(user, "organization_id", None)
            if user_org is None or cohort.org_id != user_org:
                raise Http404("cohort not found")

        # Role gating within the org:
        #   - admin (same org) or teacher-of-a-course-in-cohort → 200
        #   - student enrolled in this cohort → 403 (role-gated; they can
        #     see the cohort exists but may not view aggregated intel)
        #   - anyone else (e.g. teacher same org but not teaching here) → 404
        if not _can_view_cohort_intelligence(user, cohort):
            is_enrolled_student = CohortMembership.objects.filter(
                cohort=cohort, student=user, removed_at__isnull=True
            ).exists()
            if is_enrolled_student:
                return Response(
                    {"detail": "Teacher or admin role required for this view."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            raise Http404("cohort not found")

        # ── Active student set for this cohort ───────────────────────────
        student_ids = list(
            CohortMembership.objects
            .filter(cohort=cohort, removed_at__isnull=True)
            .values_list("student_id", flat=True)
        )
        student_count = len(student_ids)

        if not student_ids:
            return Response({
                "cohort": {
                    "id": cohort.id,
                    "name": cohort.name,
                    "student_count": 0,
                },
                "top_patterns": [],
                "summary": {
                    "students_with_unresolved_patterns": 0,
                    "total_unresolved_patterns": 0,
                    "most_affected_category": None,
                },
            })

        # ── Aggregate Pattern rows for those students (unresolved only) ──
        patterns_qs = (
            Pattern.objects
            .filter(user_id__in=student_ids, is_resolved=False)
            .prefetch_related("sample_findings")
        )

        # Group by pattern_key in Python: the fields we need (affected
        # student count via distinct users, frequency sum, example findings)
        # are awkward to express in one annotated query without double-counting
        # sample_findings. With cohort-sized N (≤ a few hundred students ×
        # a handful of patterns each) this is fine.
        by_key: dict[str, dict] = {}
        for p in patterns_qs:
            bucket = by_key.setdefault(p.pattern_key, {
                "pattern_key": p.pattern_key,
                "pattern_type": p.pattern_type,
                "users": set(),
                "total_frequency": 0,
                "last_seen": None,
                "finding_descriptions": [],
            })
            bucket["users"].add(p.user_id)
            bucket["total_frequency"] += int(p.frequency or 0)
            if p.last_seen and (bucket["last_seen"] is None or p.last_seen > bucket["last_seen"]):
                bucket["last_seen"] = p.last_seen
            # Keep up to 3 example Finding descriptions total per key.
            if len(bucket["finding_descriptions"]) < 3:
                # .all() is prefetched; no extra queries.
                for f in p.sample_findings.all():
                    if f.description and f.description not in bucket["finding_descriptions"]:
                        bucket["finding_descriptions"].append(f.description)
                        if len(bucket["finding_descriptions"]) >= 3:
                            break

        now = timezone.now()
        top_patterns = []
        for b in by_key.values():
            affected = len(b["users"])
            total_freq = b["total_frequency"]
            avg_per_student = round(total_freq / affected, 1) if affected else 0.0
            # Severity heuristic consistent with snapshot: any pattern
            # averaging ≥ 3 hits per affected student, OR affecting ≥ half
            # the cohort, is a "warning"; else "info".
            half = max(1, student_count // 2)
            severity = "warning" if (avg_per_student >= 3 or affected >= half) else "info"
            days_ago = (now - b["last_seen"]).days if b["last_seen"] else None
            top_patterns.append({
                "pattern_key": b["pattern_key"],
                "pattern_type": b["pattern_type"],
                "affected_students": affected,
                "total_frequency": total_freq,
                "avg_frequency_per_student": avg_per_student,
                "severity": severity,
                "last_seen_days_ago": days_ago,
                "example_findings": b["finding_descriptions"][:3],
            })

        # Order: more-students-affected first, then raw frequency.
        top_patterns.sort(
            key=lambda r: (-r["affected_students"], -r["total_frequency"], r["pattern_key"])
        )
        top_patterns = top_patterns[:10]

        # ── Summary ──────────────────────────────────────────────────────
        students_with_unresolved = len({p.user_id for p in patterns_qs})
        total_unresolved = patterns_qs.count()
        # "Most affected category" — we don't have a dedicated category
        # field on Pattern, so use pattern_type as the category proxy
        # (matches how snapshot exposes it). Pick the type whose affected-
        # student count is highest.
        type_student_counts: dict[str, set] = defaultdict(set)
        for p in patterns_qs:
            type_student_counts[p.pattern_type].add(p.user_id)
        most_affected_category = None
        if type_student_counts:
            most_affected_category = max(
                type_student_counts.items(),
                key=lambda kv: (len(kv[1]), kv[0]),
            )[0]

        return Response({
            "cohort": {
                "id": cohort.id,
                "name": cohort.name,
                "student_count": student_count,
            },
            "top_patterns": top_patterns,
            "summary": {
                "students_with_unresolved_patterns": students_with_unresolved,
                "total_unresolved_patterns": total_unresolved,
                "most_affected_category": most_affected_category,
            },
        })


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint 5: Teacher's students — roster view across all their cohorts
# ─────────────────────────────────────────────────────────────────────────────
class TeacherStudentListView(APIView):
    """
    GET /api/grading/students/

    Roster-oriented list of every student a teacher (or admin) can see:
      - admin / superuser in org → every student in every cohort of the org
      - teacher → students in any cohort where they own/secondary-teach a
        course OR are assigned via CohortTeacher

    Different from GradingInbox (which is PR-queue-oriented). This is the
    "all my students" view powering /grading/students in the UI.

    Response:
      { "results": [
          { id, email, name, handle, cohort_id, cohort_name,
            pr_count, prs_waiting_feedback, avg_score },
          ...
      ] }
    """

    permission_classes = [permissions.IsAuthenticated, IsTeacher]

    def get(self, request):
        from django.db.models import Q

        user = request.user

        # Scope: cohorts this user can see (mirrors CohortViewSet.get_queryset).
        cohorts = Cohort.objects.for_user(user).filter(archived_at__isnull=True)
        if not getattr(user, "is_superuser", False) and _role(user) not in ADMIN_ROLES:
            # Teacher: narrow to cohorts they actually teach in.
            cohorts = cohorts.filter(
                Q(teacher_assignments__teacher=user)
                | Q(courses__owner=user)
                | Q(courses__secondary_docent=user)
            ).distinct()

        memberships = (
            CohortMembership.objects
            .filter(cohort__in=cohorts, removed_at__isnull=True)
            .select_related("student", "cohort")
            .order_by("student__email")
        )

        # Pre-aggregate PR counts (total + waiting-for-feedback) per student.
        # `waiting` = sessions in DRAFTED or REVIEWING; this matches the
        # "wachten op feedback" semantic used elsewhere.
        WAITING_STATES = {"drafted", "reviewing"}
        sessions_qs = (
            GradingSession.objects
            .for_user(user)
            .filter(submission__student__in=[m.student_id for m in memberships])
            .values("submission__student", "state", "final_scores", "ai_draft_scores")
        )
        pr_total: dict[int, int] = defaultdict(int)
        pr_waiting: dict[int, int] = defaultdict(int)
        score_sum: dict[int, float] = defaultdict(float)
        score_n: dict[int, int] = defaultdict(int)
        for s in sessions_qs:
            sid = s["submission__student"]
            pr_total[sid] += 1
            if s["state"] in WAITING_STATES:
                pr_waiting[sid] += 1
            # avg_score: mean of numeric "score" values in final or draft scores
            src = s["final_scores"] or s["ai_draft_scores"] or {}
            nums = []
            if isinstance(src, dict):
                for v in src.values():
                    if isinstance(v, dict) and isinstance(v.get("score"), (int, float)):
                        nums.append(float(v["score"]))
                    elif isinstance(v, (int, float)):
                        nums.append(float(v))
            if nums:
                score_sum[sid] += sum(nums) / len(nums)
                score_n[sid] += 1

        results = []
        for m in memberships:
            stu = m.student
            sid = stu.id
            avg = (
                round(score_sum[sid] / score_n[sid], 2)
                if score_n[sid] else None
            )
            results.append({
                "id": sid,
                "email": stu.email,
                "name": (
                    getattr(stu, "display_name", "")
                    or stu.get_full_name()
                    or stu.username
                    or stu.email
                ),
                "handle": stu.username,
                "cohort_id": m.cohort_id,
                "cohort_name": m.cohort.name,
                "pr_count": pr_total[sid],
                "prs_waiting_feedback": pr_waiting[sid],
                "avg_score": avg,
            })

        return Response({"results": results})
