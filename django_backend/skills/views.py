"""
Skills API Views
"""
from collections import defaultdict

from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q, Count
from django.utils import timezone as tz

from .models import SkillCategory, Skill, SkillMetric
from .serializers import (
    SkillCategorySerializer,
    SkillSerializer,
    SkillMetricSerializer,
    SkillTrendSerializer
)


class SkillCategoryListView(generics.ListAPIView):
    """List all skill categories with their skills."""
    
    queryset = SkillCategory.objects.prefetch_related('skills')
    serializer_class = SkillCategorySerializer
    permission_classes = [permissions.IsAuthenticated]


class SkillListView(generics.ListAPIView):
    """List all skills."""
    
    queryset = Skill.objects.select_related('category')
    serializer_class = SkillSerializer
    permission_classes = [permissions.IsAuthenticated]


class SkillMetricListView(generics.ListAPIView):
    """List skill metrics for current user."""
    
    serializer_class = SkillMetricSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = SkillMetric.objects.filter(
            user=self.request.user
        ).select_related('skill', 'skill__category')
        
        # Filter by project if specified
        project_id = self.request.query_params.get('project')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        
        return queryset.order_by('skill__category__order', 'skill__order')


class UpdateSkillMetricsView(APIView):
    """
    Update skill metrics (internal API from FastAPI).
    """
    
    permission_classes = []

    def get_permissions(self):
        from reviewhub.permissions import IsInternalAPIKey
        return [IsInternalAPIKey()]

    def post(self, request):
        user_id = request.data.get('user_id')
        project_id = request.data.get('project_id')
        updates = request.data.get('updates', {})
        
        if not user_id or not project_id:
            return Response(
                {'error': 'user_id and project_id required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        for skill_slug, data in updates.items():
            try:
                skill = Skill.objects.get(slug=skill_slug)
                metric, _ = SkillMetric.objects.get_or_create(
                    user_id=user_id,
                    project_id=project_id,
                    skill=skill
                )
                
                if 'issues' in data:
                    metric.update_score(new_issues=data['issues'])
                elif 'score' in data:
                    metric.score = data['score']
                    metric.save()
                    
            except Skill.DoesNotExist:
                continue
        
        return Response({'success': True})


class SkillTrendsView(APIView):
    """Get skill score trends over time, with weekly historical data points."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from evaluations.models import Evaluation, FindingSkill
        from django.db.models import Count
        from datetime import datetime, timedelta

        project_id = request.query_params.get('project')
        skill_slug = request.query_params.get('skill')
        weeks = int(request.query_params.get('weeks', 8))

        metrics = SkillMetric.objects.filter(
            user=request.user
        ).select_related('skill')

        if project_id:
            metrics = metrics.filter(project_id=project_id)
        if skill_slug:
            metrics = metrics.filter(skill__slug=skill_slug)

        end_date = tz.now()
        start_date = end_date - timedelta(weeks=weeks)

        # Fetch finding history grouped by week + skill
        from evaluations.models import Evaluation

        user_evals = Evaluation.objects.for_user(request.user).filter(created_at__gte=start_date)
        if project_id:
            user_evals = user_evals.filter(project_id=project_id)
        finding_qs = FindingSkill.objects.filter(
            finding__evaluation__in=user_evals,
        ).select_related('skill', 'finding__evaluation')

        # Build weekly buckets per skill
        from collections import defaultdict
        weekly: dict = defaultdict(lambda: defaultdict(int))
        for fs in finding_qs:
            week_start = (fs.finding.evaluation.created_at - timedelta(
                days=fs.finding.evaluation.created_at.weekday()
            )).strftime('%Y-%m-%d')
            weekly[fs.skill.slug][week_start] += 1

        trends = []
        for metric in metrics:
            slug = metric.skill.slug
            week_buckets = weekly.get(slug, {})
            # Build ordered data_points for the last N weeks
            data_points = []
            cur = start_date
            while cur < end_date:
                ws = cur.strftime('%Y-%m-%d')
                data_points.append({'week': ws, 'issues': week_buckets.get(ws, 0)})
                cur += timedelta(weeks=1)

            trends.append({
                'skill_slug': slug,
                'skill_name': metric.skill.name,
                'current_score': metric.score,
                'trend': metric.trend,
                'issue_count': metric.issue_count,
                'fix_rate': metric.fix_rate,
                'data_points': data_points,
            })

        return Response(trends)


# ─── Performance Insights ──────────────────────────────────────────────────

class PerformanceStatsView(APIView):
    """
    Real performance summary for a given user + project.
    Used by the Insights page (replaces mocked api.performance.get).
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, user_id):
        from evaluations.models import Evaluation, Finding
        from django.db.models import Avg

        is_admin = getattr(request.user, 'role', None) in ('admin', 'teacher') or getattr(request.user, 'is_staff', False)

        # Admins may query users within their org; developers can only query themselves.
        if not (request.user.id == user_id or is_admin):
            return Response({'error': 'Forbidden'}, status=403)

        from users.models import User

        try:
            subject = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        # Org isolation: admins can only view users in their own org
        if is_admin and request.user.organization_id:
            if subject.organization_id != request.user.organization_id:
                return Response({'error': 'Forbidden'}, status=403)

        project_id = request.query_params.get('project')

        evals = Evaluation.objects.for_user(subject)
        if project_id:
            evals = evals.filter(project_id=project_id)

        commit_count = evals.count()
        findings = Finding.objects.filter(evaluation__in=evals)
        finding_count = findings.count()
        fixed_count = findings.filter(is_fixed=True).count()
        fix_rate = round((fixed_count / finding_count * 100) if finding_count else 0, 1)
        avg_score = round(evals.aggregate(avg=Avg('overall_score'))['avg'] or 0, 1)
        critical_issues = findings.filter(severity='critical').count()

        # Review velocity: average days between evaluations
        review_velocity = None
        dates = list(evals.order_by('created_at').values_list('created_at', flat=True))
        if len(dates) >= 2:
            gaps = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
            review_velocity = round(sum(gaps) / len(gaps), 1)

        # Strengths / Growth from skill metrics
        metrics_qs = SkillMetric.objects.filter(user_id=subject.id).select_related('skill__category')
        if project_id:
            metrics_qs = metrics_qs.filter(project_id=project_id)

        from collections import defaultdict
        cat_scores: dict = defaultdict(list)
        for m in metrics_qs:
            cat_scores[m.skill.category.name].append(m.score)

        strengths = [c for c, scores in cat_scores.items() if scores and sum(scores) / len(scores) >= 75]
        growth_areas = [c for c, scores in cat_scores.items() if scores and sum(scores) / len(scores) < 50]

        # Severity distribution
        severity_distribution = {
            'critical': findings.filter(severity='critical').count(),
            'warning': findings.filter(severity='warning').count(),
            'info': findings.filter(severity='info').count(),
            'suggestion': findings.filter(severity='suggestion').count(),
        }

        # Category breakdown (top skill issues)
        from evaluations.models import FindingSkill
        skill_counts = (
            FindingSkill.objects.filter(finding__evaluation__in=evals)
            .values('skill__id', 'skill__name', 'skill__slug')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        category_breakdown = [
            {'id': s['skill__id'], 'name': s['skill__name'], 'slug': s['skill__slug'], 'count': s['count']}
            for s in skill_counts
        ]

        # Score trend (last evaluations with dates)
        recent_evals = evals.order_by('-created_at')[:20]
        score_trend = [
            {'date': e.created_at.strftime('%Y-%m-%d'), 'score': float(e.overall_score or 0)}
            for e in reversed(recent_evals)
            if e.overall_score is not None
        ]

        # Developer level (composite calculation)
        from .level_calculator import compute_level_for_user
        level_data = compute_level_for_user(subject, project_id=project_id)

        # Progression data — per-commit scores chronologically
        all_evals_ordered = evals.order_by('created_at').values_list(
            'commit_sha', 'commit_message', 'overall_score', 'created_at'
        )
        progression = []
        running_avg = 0
        for i, (sha, msg, score, created) in enumerate(all_evals_ordered):
            if score is None:
                continue
            running_avg = ((running_avg * i) + score) / (i + 1)
            # Count findings for this eval
            eval_findings = findings.filter(evaluation__commit_sha=sha).count()
            progression.append({
                'commit': sha[:7],
                'message': (msg or '')[:50],
                'score': float(score),
                'runningAvg': round(running_avg, 1),
                'findings': eval_findings,
                'date': created.strftime('%Y-%m-%d'),
            })

        # Improvement metrics
        improving = False
        improvement_pct = 0
        if len(progression) >= 3:
            first_3_avg = sum(p['score'] for p in progression[:3]) / 3
            last_3_avg = sum(p['score'] for p in progression[-3:]) / 3
            improvement_pct = round(last_3_avg - first_3_avg, 1)
            improving = improvement_pct > 0

        return Response({
            'commitCount': commit_count,
            'findingCount': finding_count,
            'fixRate': fix_rate,
            'reviewVelocity': review_velocity,
            'averageScore': avg_score,
            'totalReviews': commit_count,
            'criticalIssues': critical_issues,
            'strengths': strengths,
            'growthAreas': growth_areas,
            'understandingRate': {
                'total_checked': findings.exclude(understanding_level='').count(),
                'got_it': findings.filter(understanding_level='got_it').count(),
                'partial': findings.filter(understanding_level='partial').count(),
                'not_yet': findings.filter(understanding_level='not_yet').count(),
            },
            'recommendations': [],
            'severityDistribution': severity_distribution,
            'categoryBreakdown': category_breakdown,
            'scoreTrend': score_trend,
            'level': level_data['level'],
            'compositeScore': level_data['composite_score'],
            'levelBreakdown': level_data['breakdown'],
            'progression': progression,
            'improving': improving,
            'improvementPct': improvement_pct,
        })


class PerformanceTrendsView(APIView):
    """
    Finding counts grouped by skill category, bucketed by day or week.
    Supports ?granularity=daily|weekly (default: daily) and ?days=N (default: 30).
    Used by the Category Trends chart on the Insights page.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, user_id):
        from evaluations.models import Evaluation, FindingSkill
        from datetime import datetime, timedelta
        from collections import defaultdict

        is_admin = getattr(request.user, 'role', None) in ('admin', 'teacher') or getattr(request.user, 'is_staff', False)

        if not (request.user.id == user_id or is_admin):
            return Response({'error': 'Forbidden'}, status=403)

        from users.models import User

        try:
            subject = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        # Org isolation: admins can only view users in their own org
        if is_admin and request.user.organization_id:
            if subject.organization_id != request.user.organization_id:
                return Response({'error': 'Forbidden'}, status=403)

        project_id = request.query_params.get('project')
        granularity = request.query_params.get('granularity', 'daily')
        days = int(request.query_params.get('days', 30))
        # Legacy support: weeks param converts to days
        weeks = request.query_params.get('weeks')
        if weeks:
            days = int(weeks) * 7

        end_date = tz.now()
        start_date = end_date - timedelta(days=days)

        evals = Evaluation.objects.for_user(subject).filter(created_at__gte=start_date)
        if project_id:
            evals = evals.filter(project_id=project_id)

        finding_qs = FindingSkill.objects.filter(
            finding__evaluation__in=evals,
        ).select_related('skill__category', 'finding__evaluation')

        buckets: dict = defaultdict(lambda: defaultdict(int))
        for fs in finding_qs:
            eval_date = fs.finding.evaluation.created_at
            if granularity == 'weekly':
                bucket_key = (eval_date - timedelta(days=eval_date.weekday())).strftime('%Y-%m-%d')
            else:
                bucket_key = eval_date.strftime('%Y-%m-%d')
            cat = fs.skill.category.name.upper().replace(' ', '_')
            buckets[bucket_key][cat] += 1

        result = []
        if granularity == 'weekly':
            cur = start_date - timedelta(days=start_date.weekday())
            end_monday = end_date - timedelta(days=end_date.weekday()) + timedelta(weeks=1)
            while cur <= end_monday:
                key = cur.strftime('%Y-%m-%d')
                result.append({'date': key, 'categories': dict(buckets.get(key, {}))})
                cur += timedelta(weeks=1)
        else:
            cur = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_day = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
            while cur <= end_day:
                key = cur.strftime('%Y-%m-%d')
                result.append({'date': key, 'categories': dict(buckets.get(key, {}))})
                cur += timedelta(days=1)

        return Response(result)


class SkillBreakdownView(APIView):
    """
    Detailed breakdown for a single skill: score, finding history, deductions, trend.
    Replaces the client-side mock in api.skills.breakdown.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, user_id, skill_id):
        from evaluations.models import FindingSkill
        from django.db.models import Avg
        from datetime import datetime, timedelta

        is_admin = getattr(request.user, 'role', None) in ('admin', 'teacher') or getattr(request.user, 'is_staff', False)

        if not (request.user.id == user_id or is_admin):
            return Response({'error': 'Forbidden'}, status=403)

        from users.models import User
        from evaluations.models import Evaluation

        try:
            subject = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        # Org isolation: admins can only view users in their own org
        if is_admin and request.user.organization_id:
            if subject.organization_id != request.user.organization_id:
                return Response({'error': 'Forbidden'}, status=403)

        project_id = request.query_params.get('project')

        try:
            skill = Skill.objects.select_related('category').get(id=skill_id)
        except Skill.DoesNotExist:
            return Response({'error': 'Skill not found'}, status=404)

        user_evals = Evaluation.objects.for_user(subject)
        if project_id:
            user_evals = user_evals.filter(project_id=project_id)

        # Current metric
        metric_qs = SkillMetric.objects.filter(user_id=subject.id, skill=skill)
        if project_id:
            metric_qs = metric_qs.filter(project_id=project_id)
        metric = metric_qs.first()

        score = metric.score if metric else 100.0
        # Compute level from score
        if score >= 90: level = 4
        elif score >= 75: level = 3
        elif score >= 50: level = 2
        elif score >= 25: level = 1
        else: level = 0

        # Findings for this skill
        fs_qs = FindingSkill.objects.filter(
            skill=skill,
            finding__evaluation__in=user_evals,
        ).select_related('finding', 'finding__evaluation')
        if project_id:
            fs_qs = fs_qs.filter(finding__evaluation__project_id=project_id)

        findings_data = []
        deductions = []
        for fs in fs_qs.order_by('-finding__created_at')[:20]:
            f = fs.finding
            findings_data.append({
                'id': f.id,
                'title': f.title,
                'severity': f.severity,
                'file_path': f.file_path,
                'line_start': f.line_start,
                'is_fixed': f.is_fixed,
                'created_at': f.created_at.isoformat() if f.created_at else None,
            })
            deductions.append({
                'findingId': f.id,
                'explanation': f.title + (f' — {f.description[:80]}' if f.description else ''),
                'impact': round(-fs.impact_score, 1) if not f.is_fixed else round(fs.impact_score * 0.6, 1),
                'keyword': f.severity,
                'type': 'positive' if f.is_fixed else 'negative',
                'filePath': f.file_path or '',
                'date': f.created_at.isoformat() if f.created_at else '',
            })

        # Weekly trend (last 8 weeks)
        weeks = 8
        end_date = tz.now()
        start_date = end_date - timedelta(weeks=weeks)
        from collections import defaultdict
        weekly_issues: dict = defaultdict(int)
        for fs in fs_qs.filter(finding__evaluation__created_at__gte=start_date):
            d = fs.finding.evaluation.created_at
            ws = (d - timedelta(days=d.weekday())).strftime('%Y-%m-%d')
            weekly_issues[ws] += 1

        trend_points = []
        cur = start_date
        from datetime import timedelta as td
        while cur < end_date:
            ws = cur.strftime('%Y-%m-%d')
            trend_points.append({'week': ws, 'issues': weekly_issues.get(ws, 0)})
            cur += td(weeks=1)

        # Tips: use low fix-rate patterns
        tips = []
        if score < 50:
            tips.append(f"Your {skill.name} score is below 50. Focus on reviewing recent findings.")
        if metric and metric.fix_rate < 30:
            tips.append("Low fix rate — try resolving existing issues before the next push.")
        if not tips:
            tips.append("Keep pushing code and reviewing findings to improve this skill.")

        return Response({
            'skill': {
                'id': skill.id,
                'name': skill.name,
                'displayName': skill.name,
                'description': skill.description,
                'category': {
                    'id': skill.category.id,
                    'name': skill.category.name,
                    'displayName': skill.category.name,
                    'icon': skill.category.icon or 'school',
                },
            },
            'score': round(score, 1),
            'level': level,
            'baseScore': 100,
            'deductions': deductions[:10],
            'tips': tips,
            'findings': findings_data,
            'trend': trend_points,
        })


class DashboardOverviewView(APIView):
    """
    Get overall dashboard stats for current user.
    Returns: total evaluations, findings, avg score, etc.
    """
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        from evaluations.models import Evaluation, Finding
        from django.db.models import Avg
        from users.models import User

        project_id = request.query_params.get('project')

        # Admin can view any user's data via ?user=<id>, scoped to their org
        target_user = request.user
        user_id_param = request.query_params.get('user')
        if user_id_param and (request.user.role in ('admin', 'teacher') or request.user.is_staff):
            try:
                candidate = User.objects.get(pk=user_id_param)
                # Org isolation: only allow if target is in the same org
                if not request.user.organization_id or candidate.organization_id == request.user.organization_id:
                    target_user = candidate
            except User.DoesNotExist:
                pass

        # Get user's evaluations
        evaluations = Evaluation.objects.for_user(target_user)
        if project_id:
            evaluations = evaluations.filter(project_id=project_id)
        
        # Get user's findings
        findings = Finding.objects.filter(evaluation__in=evaluations)
        
        # Calculate stats
        total_evaluations = evaluations.count()
        total_findings = findings.count()
        avg_score = evaluations.aggregate(avg=Avg('overall_score'))['avg'] or 0
        
        # Findings by severity
        critical_count = findings.filter(severity=Finding.Severity.CRITICAL).count()
        warning_count = findings.filter(severity=Finding.Severity.WARNING).count()
        info_count = findings.filter(severity=Finding.Severity.INFO).count()
        
        # Fixed count
        fixed_count = findings.filter(is_fixed=True).count()
        fix_rate = (fixed_count / total_findings * 100) if total_findings > 0 else 0

        # Score trend (last 10 evaluations)
        recent_evals = evaluations.order_by('-created_at')[:10]
        score_trend = [
            {
                "date": e.created_at.strftime("%Y-%m-%d"),
                "score": float(e.overall_score),
            }
            for e in reversed(recent_evals)
            if e.overall_score is not None
        ]

        # Top 3 priority skills to improve (lowest scores)
        priority_metrics = SkillMetric.objects.filter(
            user=target_user
        ).select_related('skill')
        if project_id:
            priority_metrics = priority_metrics.filter(project_id=project_id)
        priority_metrics = priority_metrics.order_by('score')[:3]
        priorities = [
            {
                "skill": m.skill.name,
                "skill_slug": m.skill.slug,
                "score": float(m.score),
                "issues": m.issue_count,
                "trend": m.trend,
            }
            for m in priority_metrics
        ]

        # Developer profile (if exists)
        profile_data = None
        try:
            from batch.models import DeveloperProfile
            profile = DeveloperProfile.objects.get(user=target_user)
            profile_data = {
                "level": profile.level,
                "trend": profile.trend,
                "overall_score": float(profile.overall_score),
                "strengths_count": len(profile.strengths) if profile.strengths else 0,
                "weaknesses_count": len(profile.weaknesses) if profile.weaknesses else 0,
            }
        except Exception:
            pass

        # Pattern insights (top recurring patterns)
        from evaluations.models import Pattern
        pattern_qs = Pattern.objects.filter(user=target_user, is_resolved=False)
        if project_id:
            pattern_qs = pattern_qs.filter(project_id=project_id)
        top_patterns = pattern_qs.order_by('-frequency')[:5]
        pattern_insights = [
            {
                "type": p.pattern_type,
                "key": p.pattern_key,
                "frequency": p.frequency,
                "message": f"You have {p.frequency} recurring {p.pattern_type} issues",
            }
            for p in top_patterns
        ]

        return Response({
            'total_evaluations': total_evaluations,
            'total_findings': total_findings,
            'avg_score': round(avg_score, 1),
            'critical_count': critical_count,
            'warning_count': warning_count,
            'info_count': info_count,
            'fixed_count': fixed_count,
            'fix_rate': round(fix_rate, 1),
            'score_trend': score_trend,
            'priorities': priorities,
            'profile': profile_data,
            'pattern_insights': pattern_insights,
        })


def _resolve_target_user(request):
    """Admin can view any user's data via ?user=<id>, scoped to their org.

    Raises PermissionDenied when a cross-org target is requested instead of
    silently falling back to request.user (which masked ACL bugs).
    """
    from users.models import User
    user_id = request.query_params.get('user')
    if user_id and (request.user.role in ('admin', 'teacher') or request.user.is_staff):
        try:
            target = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise PermissionDenied('Target user not found or not accessible.')
        # Org isolation: only allow if target is in the same org
        if request.user.organization_id and target.organization_id != request.user.organization_id:
            raise PermissionDenied('Cross-organization access is not allowed.')
        return target
    return request.user


class DashboardSkillsView(APIView):
    """
    Get skill scores grouped by category for the dashboard radar chart.

    Honest scoring (Apr 28 2026):
      - Use `bayesian_score` (evidence-weighted, starts at 50, converges
        with observations) instead of the legacy `.score` field. The
        legacy score defaulted to 100 — anything we hadn't seen showed
        as "perfect" which is a misread of the actual signal.
      - Aggregate per-category confidence (mean across the category's
        metrics) and emit `is_preliminary = mean_confidence < 0.15`.
        The frontend SkillRadarChart fades the whole spoke / dataset
        when this flag is true so a teacher can tell the difference
        between "real 50%" and "we have no idea, defaulted to 50%".
      - Mirrors the pattern already in UserSkillsView and the grading
        student-intelligence radar (single source of truth on scoring).
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from skills.models import CONFIDENCE_PRELIMINARY

        project_id = request.query_params.get('project')
        target_user = _resolve_target_user(request)

        metrics = SkillMetric.objects.filter(
            user=target_user
        ).select_related('skill', 'skill__category')

        if project_id:
            metrics = metrics.filter(project_id=project_id)

        # Group by category — collect Bayesian scores + confidences.
        categories: dict = {}
        for metric in metrics:
            cat_name = metric.skill.category.name
            if cat_name not in categories:
                categories[cat_name] = {
                    'scores': [],
                    'confidences': [],
                    'color': metric.skill.category.color,
                }
            # Use Bayesian score once we have any observation; fall back
            # to the legacy seed score for the zero-observation case so
            # we still render a spoke for the category (the is_preliminary
            # flag will mark it as untrusted).
            if metric.observation_count > 0:
                categories[cat_name]['scores'].append(metric.bayesian_score)
            else:
                categories[cat_name]['scores'].append(metric.score)
            categories[cat_name]['confidences'].append(metric.confidence)

        result = []
        for cat_name, data in categories.items():
            scores = data['scores']
            confs = data['confidences']
            avg_score = sum(scores) / len(scores) if scores else 0.0
            avg_conf = sum(confs) / len(confs) if confs else 0.0
            result.append({
                'category': cat_name,
                'score': round(avg_score, 1),
                'confidence': round(avg_conf, 3),
                'is_preliminary': avg_conf < CONFIDENCE_PRELIMINARY,
                'color': data['color'],
            })

        if not result:
            # No SkillMetric rows (e.g. author was null at ingest);
            # approximate from FindingSkill. These pseudo-scores are
            # always preliminary — a teacher should see them as a
            # rough hint, not a verdict.
            from evaluations.models import Evaluation, FindingSkill

            evals = Evaluation.objects.for_user(request.user)
            if project_id:
                evals = evals.filter(project_id=project_id)
            cat_map: dict = {}
            for row in FindingSkill.objects.filter(
                finding__evaluation__in=evals
            ).select_related('skill__category'):
                c = row.skill.category
                name = c.name
                if name not in cat_map:
                    cat_map[name] = {'issues': 0, 'color': c.color}
                cat_map[name]['issues'] += 1
            for cat_name, data in cat_map.items():
                pseudo = max(5.0, 100.0 - min(data['issues'] * 6.0, 85.0))
                result.append({
                    'category': cat_name,
                    'score': round(pseudo, 1),
                    'confidence': 0.0,
                    'is_preliminary': True,
                    'color': data['color'],
                })

        return Response(result)


class DashboardProgressView(APIView):
    """
    Get skill progress over time for line chart.
    Returns: time series data for skills.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from evaluations.models import Evaluation
        from django.db.models import Avg
        from datetime import datetime, timedelta

        project_id = request.query_params.get('project')
        weeks = int(request.query_params.get('weeks', 8))
        target_user = _resolve_target_user(request)

        # Get evaluations for the last N weeks
        end_date = tz.now()
        start_date = end_date - timedelta(weeks=weeks)

        evaluations = Evaluation.objects.for_user(target_user).filter(
            created_at__gte=start_date,
        ).order_by('created_at')
        
        if project_id:
            evaluations = evaluations.filter(project_id=project_id)
        
        # Group by week and calculate avg score
        weekly_data = []
        current_week_start = start_date
        
        while current_week_start < end_date:
            week_end = current_week_start + timedelta(days=7)
            
            week_evals = evaluations.filter(
                created_at__gte=current_week_start,
                created_at__lt=week_end
            )
            
            avg_score = week_evals.aggregate(avg=Avg('overall_score'))['avg'] or 0
            finding_count = sum(e.finding_count for e in week_evals)
            
            weekly_data.append({
                'week_start': current_week_start.strftime('%Y-%m-%d'),
                'week_end': week_end.strftime('%Y-%m-%d'),
                'avg_score': round(avg_score, 1),
                'evaluation_count': week_evals.count(),
                'finding_count': finding_count
            })
            
            current_week_start = week_end
        
        return Response(weekly_data)


class DashboardRecentView(APIView):
    """
    Get recent findings with skill tags.
    Returns: recent findings with associated skills.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from evaluations.models import Finding

        project_id = request.query_params.get('project')
        limit = int(request.query_params.get('limit', 10))
        target_user = _resolve_target_user(request)

        from evaluations.models import Evaluation

        user_evals = Evaluation.objects.for_user(target_user)
        if project_id:
            user_evals = user_evals.filter(project_id=project_id)

        queryset = Finding.objects.filter(evaluation__in=user_evals).select_related(
            'evaluation'
        ).prefetch_related(
            'skills'
        )
        
        # Apply ordering and limit AFTER all filters
        findings = queryset.order_by('-created_at')[:limit]
        
        # Format response
        result = []
        for finding in findings:
            result.append({
                'id': finding.id,
                'title': finding.title,
                'description': finding.description,
                'severity': finding.severity,
                'file_path': finding.file_path,
                'line_start': finding.line_start,
                'is_fixed': finding.is_fixed,
                'created_at': finding.created_at.isoformat(),
                'skills': [
                    {
                        'id': skill.id,
                        'name': skill.name,
                        'category': skill.category.name
                    } for skill in finding.skills.all()
                ]
            })
        
        return Response(result)


class UserSkillsView(APIView):
    """
    Get skill metrics for a specific user, grouped by category.
    """
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, user_id):
        from users.models import User

        is_admin = getattr(request.user, 'role', None) in ('admin', 'teacher') or getattr(request.user, 'is_staff', False)

        # Permission check: devs see only themselves, admins see their org
        if not (request.user.id == user_id or is_admin):
            return Response({'error': 'Forbidden'}, status=403)

        # Verify user exists
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Org isolation: admins can only view users in their own org
        if is_admin and request.user.organization_id:
            if user.organization_id != request.user.organization_id:
                return Response({'error': 'Forbidden'}, status=403)

        # Get project filter
        project_id = request.query_params.get('project')
        
        # Get all categories with skills
        categories = SkillCategory.objects.prefetch_related('skills').order_by('order')
        
        # Get user's skill metrics
        metrics_query = SkillMetric.objects.filter(user=user)
        if project_id:
            metrics_query = metrics_query.filter(project_id=project_id)
        
        # Build metrics lookup
        metrics_map = {}
        for metric in metrics_query.select_related('skill'):
            metrics_map[metric.skill_id] = metric
        
        # Build response
        result = {
            'user_id': user_id,
            'categories': []
        }
        
        for category in categories:
            cat_data = {
                'id': category.id,
                'name': category.name,
                'displayName': category.name.replace('_', ' ').title(),
                'description': category.description or '',
                'icon': category.icon or 'school',
                'skills': []
            }
            
            for skill in category.skills.all().order_by('order'):
                metric = metrics_map.get(skill.id)
                if metric and metric.observation_count > 0:
                    score = metric.bayesian_score
                elif metric:
                    score = metric.score  # legacy fallback
                else:
                    score = 0
                confidence = metric.confidence if metric else 0.0
                confidence_label = metric.confidence_label if metric else 'insufficient'
                level_label = metric.level_label if metric else None
                # Derive a simple 0-5 level from score for backward compat
                level = min(5, int(score / 20)) if score else 0
                cat_data['skills'].append({
                    'id': skill.id,
                    'displayName': skill.name,
                    'score': round(score, 1),
                    'level': level,
                    'confidence': round(confidence, 2),
                    'confidenceLabel': confidence_label,
                    'levelLabel': level_label,
                    'observationCount': metric.observation_count if metric else 0,
                    'provenConcepts': metric.proven_concepts if metric else 0,
                    'relapsedConcepts': metric.relapsed_concepts if metric else 0,
                })

            result['categories'].append(cat_data)

        return Response(result)


class DeveloperHomeView(APIView):
    """
    Unified dashboard endpoint for the developer home page.
    Returns everything needed in one call: metrics, skills, progression,
    priorities, patterns, recent commits — across ALL projects.
    """

    permission_classes = [permissions.IsAuthenticated]

    @staticmethod
    def _build_pattern_chart(user):
        """
        Aggregate Pattern rows by skill_slug (pattern_type) so the
        Recurring Patterns chart shows one row per underlying mistake,
        not one row per (mistake, severity) pair.

        Returns a list of dicts ordered by frequency desc, capped at 10:
            {
                "slug": "input_validation",
                "name": "Input Validation",
                "frequency": 11,        # summed across severity variants
                "resolved": False,      # True only if ALL variants resolved
                "category": "Security", # SkillCategory.name
                "category_color": "#...", # SkillCategory.color (or "" if missing)
            }
        """
        from collections import defaultdict
        from evaluations.models import Pattern
        from .models import Skill

        # Group by pattern_type (= skill_slug). frequency sums across
        # severity variants; resolved is the AND across variants
        # (any unresolved variant keeps the aggregate "active").
        agg: dict[str, dict] = defaultdict(lambda: {
            "frequency": 0,
            "resolved": True,
            "name": None,
        })
        for p in Pattern.objects.filter(user=user):
            slot = agg[p.pattern_type]
            slot["frequency"] += p.frequency
            if not p.is_resolved:
                slot["resolved"] = False
            if slot["name"] is None:
                slot["name"] = p.pattern_type.replace("_", " ").title()

        if not agg:
            return []

        # Look up category metadata for each unique slug — single bulk
        # query, joined by Skill.slug.
        slugs = list(agg.keys())
        skill_meta = {
            s.slug: {
                "category_name": s.category.name if s.category_id else "Algemeen",
                "category_color": getattr(s.category, "color", "") or "",
            }
            for s in Skill.objects.filter(slug__in=slugs).select_related("category")
        }

        out = []
        for slug, data in agg.items():
            meta = skill_meta.get(slug, {"category_name": "Algemeen", "category_color": ""})
            out.append({
                "slug": slug,
                "name": data["name"],
                "frequency": data["frequency"],
                "resolved": data["resolved"],
                "category": meta["category_name"],
                "category_color": meta["category_color"],
            })

        out.sort(key=lambda x: x["frequency"], reverse=True)
        return out[:10]

    @staticmethod
    def _calculate_streak(evals):
        """Count consecutive recent commits with score >= 70 and no critical findings."""
        streak = 0
        for e in evals.order_by('-created_at')[:20]:
            if e.overall_score and e.overall_score >= 70:
                has_critical = e.findings.filter(severity='critical').exists()
                if not has_critical:
                    streak += 1
                else:
                    break
            else:
                break
        return {
            'count': streak,
            'label': f'{streak} commit{"s" if streak != 1 else ""} without critical issues',
            'active': streak >= 3,
        }

    def get(self, request):
        from evaluations.models import Evaluation, Finding, FindingSkill, Pattern
        from django.db.models import Avg
        from collections import defaultdict

        user = request.user
        project_id = request.query_params.get('project')

        # All evaluations for this user
        evals = Evaluation.objects.for_user(user)
        if project_id:
            evals = evals.filter(project_id=project_id)

        findings = Finding.objects.filter(evaluation__in=evals)

        # ── Key Metrics ──
        commit_count = evals.count()
        finding_count = findings.count()
        fixed_count = findings.filter(is_fixed=True).count()
        avg_score = round(evals.aggregate(avg=Avg('overall_score'))['avg'] or 0, 1)

        # Level (composite calculation)
        from .level_calculator import compute_level_for_user
        level_data = compute_level_for_user(user, project_id=project_id)
        level = level_data['level']
        trend_label = 'new'
        try:
            from batch.models import DeveloperProfile
            profile = DeveloperProfile.objects.get(user=user)
            trend_label = profile.trend
        except Exception:
            pass

        # ── Improvement ──
        ordered_evals = evals.order_by('created_at').values_list('overall_score', flat=True)
        scores_list = [s for s in ordered_evals if s is not None]
        improving = False
        improvement_pct = 0
        if len(scores_list) >= 3:
            first_3 = sum(scores_list[:3]) / 3
            last_3 = sum(scores_list[-3:]) / 3
            improvement_pct = round(last_3 - first_3, 1)
            improving = improvement_pct > 0

        # ── Severity ──
        severity = {
            'critical': findings.filter(severity='critical').count(),
            'warning': findings.filter(severity='warning').count(),
            'info': findings.filter(severity='info').count(),
            'suggestion': findings.filter(severity='suggestion').count(),
        }

        # ── Top 3 Priority Skills (weakest) ──
        metrics = SkillMetric.objects.filter(user=user).select_related('skill')
        if project_id:
            metrics = metrics.filter(project_id=project_id)
        priority_metrics = metrics.order_by('score')[:3]
        priorities = [
            {
                'id': m.skill.id,
                'skill': m.skill.name,
                'slug': m.skill.slug,
                'score': float(m.score),
                'issues': m.issue_count,
                'trend': m.trend,
            }
            for m in priority_metrics
        ]

        # ── Pattern Insights ──
        pattern_qs = Pattern.objects.filter(user=user, is_resolved=False)
        if project_id:
            pattern_qs = pattern_qs.filter(project_id=project_id)
        top_patterns = pattern_qs.order_by('-frequency')[:3]
        patterns = [
            {
                'type': p.pattern_type,
                'key': p.pattern_key,
                'frequency': p.frequency,
                'message': f"You have {p.frequency} recurring {p.pattern_type.replace('_', ' ')} issues",
            }
            for p in top_patterns
        ]

        # ── Recent Commits (last 5) ──
        recent_evals = evals.order_by('-created_at')[:5]
        recent_commits = [
            {
                'id': e.id,
                'sha': e.commit_sha[:7],
                'message': (e.commit_message or '')[:60],
                'score': float(e.overall_score) if e.overall_score else None,
                'findings': e.findings.count(),
                'date': e.created_at.strftime('%Y-%m-%d %H:%M'),
                'project': e.project.name if e.project else '',
            }
            for e in recent_evals
        ]

        # ── Skill Radar (category averages) ──
        # P1-7: Only include categories with actual data (don't show 0)
        cat_scores = defaultdict(list)
        for m in metrics:
            cat_scores[m.skill.category.name].append(m.score)
        radar = [
            {'category': cat, 'score': round(sum(scores) / len(scores), 1)}
            for cat, scores in cat_scores.items()
            if scores
        ]

        # P1-7: Fallback when no SkillMetric records — derive from FindingSkill
        if not radar and finding_count > 0:
            cat_map = defaultdict(lambda: {'issues': 0})
            for row in FindingSkill.objects.filter(
                finding__evaluation__in=evals
            ).select_related('skill__category'):
                cat_map[row.skill.category.name]['issues'] += 1
            for cat_name, data in cat_map.items():
                pseudo = max(5.0, 100.0 - min(data['issues'] * 6.0, 85.0))
                radar.append({'category': cat_name, 'score': round(pseudo, 1)})

        # ── Progression Sparkline (last 10 scores) ──
        last_10 = evals.order_by('-created_at').values_list('overall_score', flat=True)[:10]
        sparkline = [float(s) for s in reversed(last_10) if s is not None]

        # ── Category Breakdown (top issues) ──
        skill_counts = (
            FindingSkill.objects.filter(finding__evaluation__in=evals)
            .values('skill__id', 'skill__name')
            .annotate(count=Count('id'))
            .order_by('-count')[:6]
        )
        top_issues = [
            {'id': s['skill__id'], 'name': s['skill__name'], 'count': s['count']}
            for s in skill_counts
        ]

        return Response({
            # Key metrics
            'avgScore': avg_score,
            'level': level,
            'compositeScore': level_data['composite_score'],
            'levelBreakdown': level_data['breakdown'],
            'trend': trend_label,
            'improving': improving,
            'improvementPct': improvement_pct,
            'commitCount': commit_count,
            'findingCount': finding_count,
            'fixedCount': fixed_count,
            'severity': severity,
            # Action items
            'priorities': priorities,
            'patterns': patterns,
            'patternsResolved': Pattern.objects.filter(user=user, is_resolved=True).count(),
            'patternsActive': pattern_qs.count(),
            # Pattern breakdown for chart, deduplicated by skill_slug.
            #
            # Pattern rows are keyed `{skill_slug}:{severity}` so the same
            # underlying mistake (e.g. raw SQL with user input) splits across
            # multiple rows when the LLM tags it differently per occurrence
            # (input_validation:warning vs input_validation:critical). The
            # old chart rendered "Input Validation 7x" + "Input Validation 4x"
            # as TWO bars — student saw a duplicated list, not a clear "this
            # one mistake recurs 11 times" signal.
            #
            # Aggregate by pattern_type (= skill_slug without severity), sum
            # frequencies, mark resolved only when EVERY underlying pattern
            # for that skill is resolved (any open variant means the student
            # hasn't fully cleared the pattern). Enrich with category name +
            # color so the frontend can group by category and use the
            # canonical SkillCategory accent without a second roundtrip.
            'patternChart': self._build_pattern_chart(user),
            'recentCommits': recent_commits,
            # Visuals
            'radar': radar,
            'sparkline': sparkline,
            'topIssues': top_issues,
            # Streak: consecutive commits with score >= 70 and 0 critical findings
            'streak': self._calculate_streak(evals),
        })


class AdminTeamOverviewView(APIView):
    """
    Admin-only: team-wide aggregate stats for the admin dashboard.
    Returns team health, level distribution, attention flags, and leaderboard.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.role not in ('admin', 'teacher') and not request.user.is_staff:
            return Response({'error': 'Admin or teacher only'}, status=403)

        from evaluations.models import Evaluation, Finding, Pattern
        from users.models import User
        from django.db.models import Avg, Count
        from .level_calculator import compute_level_for_user
        from collections import Counter

        developers = User.objects.filter(role='developer')
        if request.user.organization_id:
            developers = developers.filter(organization=request.user.organization)

        # Per-developer data
        dev_data = []
        level_counts = Counter()
        all_scores = []

        for dev in developers:
            evals = Evaluation.objects.for_user(dev)
            eval_count = evals.count()
            if eval_count == 0:
                continue

            avg_score = evals.aggregate(avg=Avg('overall_score'))['avg'] or 0
            findings = Finding.objects.filter(evaluation__in=evals)
            finding_count = findings.count()
            fixed_count = findings.filter(is_fixed=True).count()
            fix_rate = round((fixed_count / finding_count * 100) if finding_count else 0, 1)

            # Level
            level_data = compute_level_for_user(dev)
            level_counts[level_data['level']] += 1
            all_scores.append(level_data['composite_score'])

            # Improvement
            scores_list = [s for s in evals.order_by('created_at').values_list('overall_score', flat=True) if s is not None]
            improvement = 0
            if len(scores_list) >= 3:
                improvement = round(sum(scores_list[-3:]) / 3 - sum(scores_list[:3]) / 3, 1)

            # Recent sparkline (last 5)
            recent_scores = [float(s) for s in evals.order_by('-created_at').values_list('overall_score', flat=True)[:5] if s is not None]

            # Active patterns
            active_patterns = Pattern.objects.filter(user=dev, is_resolved=False).count()
            resolved_patterns = Pattern.objects.filter(user=dev, is_resolved=True).count()

            dev_data.append({
                'id': dev.id,
                'username': dev.username,
                'email': dev.email,
                'displayName': dev.display_name,
                'level': level_data['level'],
                'compositeScore': level_data['composite_score'],
                'avgScore': round(avg_score, 1),
                'improvement': improvement,
                'commitCount': eval_count,
                'findingCount': finding_count,
                'fixRate': fix_rate,
                'activePatterns': active_patterns,
                'resolvedPatterns': resolved_patterns,
                'sparkline': list(reversed(recent_scores)),
            })

        # Team aggregates
        team_avg_score = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0
        total_findings = sum(d['findingCount'] for d in dev_data)
        total_fixed = sum(int(d['findingCount'] * d['fixRate'] / 100) for d in dev_data)
        team_fix_rate = round((total_fixed / total_findings * 100) if total_findings else 0, 1)

        # Level distribution
        level_distribution = {
            'beginner': level_counts.get('beginner', 0),
            'junior': level_counts.get('junior', 0),
            'intermediate': level_counts.get('intermediate', 0),
            'senior': level_counts.get('senior', 0),
            'expert': level_counts.get('expert', 0),
        }

        # Developers who need attention
        needs_attention = []
        for d in dev_data:
            reasons = []
            if d['fixRate'] == 0 and d['findingCount'] > 5:
                reasons.append(f"0% fix rate with {d['findingCount']} findings")
            if d['improvement'] < -10:
                reasons.append(f"Score declining ({d['improvement']}%)")
            if d['activePatterns'] >= 5:
                reasons.append(f"{d['activePatterns']} unresolved patterns")
            if reasons:
                needs_attention.append({
                    'id': d['id'],
                    'username': d['username'],
                    'displayName': d['displayName'],
                    'level': d['level'],
                    'reasons': reasons,
                })

        # Top team patterns
        team_patterns = (
            Pattern.objects.filter(user__role='developer', is_resolved=False)
            .values('pattern_type')
            .annotate(total=Count('id'), total_freq=Count('frequency'))
            .order_by('-total')[:5]
        )

        # Leaderboard
        top_improvers = sorted(dev_data, key=lambda d: d['improvement'], reverse=True)[:3]
        top_quality = sorted(dev_data, key=lambda d: d['avgScore'], reverse=True)[:3]
        top_fixers = sorted(dev_data, key=lambda d: d['fixRate'], reverse=True)[:3]

        return Response({
            # Team health
            'teamAvgScore': team_avg_score,
            'teamFixRate': team_fix_rate,
            'totalDevelopers': len(dev_data),
            'totalFindings': total_findings,
            'levelDistribution': level_distribution,

            # Attention flags
            'needsAttention': needs_attention,

            # Team patterns
            'teamPatterns': [
                {'type': p['pattern_type'].replace('_', ' ').title(), 'count': p['total']}
                for p in team_patterns
            ],

            # Leaderboard
            'topImprovers': [
                {'id': d['id'], 'name': d['displayName'], 'improvement': d['improvement'], 'level': d['level']}
                for d in top_improvers if d['improvement'] > 0
            ],
            'topQuality': [
                {'id': d['id'], 'name': d['displayName'], 'avgScore': d['avgScore'], 'level': d['level']}
                for d in top_quality
            ],
            'topFixers': [
                {'id': d['id'], 'name': d['displayName'], 'fixRate': d['fixRate'], 'level': d['level']}
                for d in top_fixers if d['fixRate'] > 0
            ],

            # All developers with detailed data
            'developers': sorted(dev_data, key=lambda d: d['compositeScore'], reverse=True),
        })


class AdminSkillMatrixView(APIView):
    """
    Admin-only: team skill matrix heatmap data.
    Returns developers as rows, skill categories as columns, scores as values.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.role not in ('admin', 'teacher') and not request.user.is_staff:
            return Response({'error': 'Admin or teacher only'}, status=403)

        from users.models import User
        from collections import defaultdict

        developers = User.objects.filter(role='developer')
        if request.user.organization_id:
            developers = developers.filter(organization=request.user.organization)
        categories = SkillCategory.objects.prefetch_related('skills').order_by('order')

        # Build category list
        cat_names = [cat.name for cat in categories]

        # Build matrix: developer → category → avg score
        rows = []
        for dev in developers:
            metrics = SkillMetric.objects.filter(user=dev).select_related('skill__category')
            if not metrics.exists():
                continue

            cat_scores = defaultdict(list)
            for m in metrics:
                cat_scores[m.skill.category.name].append(m.score)

            scores = {}
            for cat_name in cat_names:
                s_list = cat_scores.get(cat_name, [])
                scores[cat_name] = round(sum(s_list) / len(s_list), 1) if s_list else None

            rows.append({
                'id': dev.id,
                'name': dev.display_name,
                'email': dev.email,
                'scores': scores,
            })

        # Team averages per category
        team_avgs = {}
        for cat_name in cat_names:
            vals = [r['scores'][cat_name] for r in rows if r['scores'].get(cat_name) is not None]
            team_avgs[cat_name] = round(sum(vals) / len(vals), 1) if vals else None

        # Weakest categories (sorted by team avg ascending)
        weakest = sorted(
            [(cat, avg) for cat, avg in team_avgs.items() if avg is not None],
            key=lambda x: x[1]
        )[:3]

        return Response({
            'categories': cat_names,
            'developers': rows,
            'teamAverages': team_avgs,
            'weakestCategories': [{'name': w[0], 'avg': w[1]} for w in weakest],
        })


# ═══════════════════════════════════════════════════════════════════════════
# Phase 2: Organization Dashboard Views
# ═══════════════════════════════════════════════════════════════════════════


class OrgDashboardView(APIView):
    """
    P2-5: Organization dashboard — shows all students with skill overview.
    Org admin sees: student name, level, trend, weakest skill, last active.
    Also returns a skill heatmap (avg score per category across all students).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.contrib.auth import get_user_model
        from evaluations.models import Evaluation
        from batch.models import DeveloperProfile

        User = get_user_model()
        user = request.user

        if not user.organization:
            return Response({'error': 'You must belong to an organization.'}, status=400)
        if user.role not in ('admin', 'teacher'):
            return Response({'error': 'Only admins and teachers can access the dashboard.'}, status=403)

        org = user.organization
        students = User.objects.filter(
            organization=org, role='developer'
        ).order_by('first_name', 'username')

        student_rows = []
        cat_totals = defaultdict(list)

        for student in students:
            # Get profile data
            profile = DeveloperProfile.objects.filter(user=student).first()
            level = profile.level if profile else 'new'
            trend = profile.trend if profile else 'new'
            overall = profile.overall_score if profile else 0

            # Weakest skill
            weakest_metric = SkillMetric.objects.filter(
                user=student
            ).select_related('skill__category').order_by('score').first()
            weakest_skill = weakest_metric.skill.category.name if weakest_metric else None

            # Last active
            last_eval = Evaluation.objects.for_user(student).order_by('-created_at').first()
            last_active = last_eval.created_at.strftime('%Y-%m-%d') if last_eval else None

            # Collect category scores for heatmap
            for m in SkillMetric.objects.filter(user=student).select_related('skill__category'):
                cat_totals[m.skill.category.name].append(m.score)

            student_rows.append({
                'id': student.id,
                'name': student.display_name,
                'email': student.email,
                'level': level,
                'overall_score': round(overall, 1),
                'trend': trend,
                'weakest_skill': weakest_skill,
                'last_active': last_active,
            })

        # Skill heatmap — average score per category across all students
        heatmap = [
            {
                'category': cat,
                'avg_score': round(sum(scores) / len(scores), 1),
                'student_count': len(scores),
            }
            for cat, scores in sorted(cat_totals.items(), key=lambda x: sum(x[1]) / len(x[1]))
        ]

        return Response({
            'org_name': org.name,
            'student_count': len(student_rows),
            'students': student_rows,
            'heatmap': heatmap,
        })


class OrgStudentDetailView(APIView):
    """
    P2-6: Org admin drills into a specific student.
    Returns: radar chart, evaluation history, strengths, weaknesses.
    Does NOT expose code or secrets — only scores and finding titles.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, student_id):
        from django.contrib.auth import get_user_model
        from evaluations.models import Evaluation, Finding, FindingSkill
        from batch.models import DeveloperProfile
        from .level_calculator import compute_level_for_user

        User = get_user_model()
        user = request.user

        if not user.organization:
            return Response({'error': 'You must belong to an organization.'}, status=400)
        if user.role not in ('admin', 'teacher'):
            return Response({'error': 'Only admins and teachers can access student details.'}, status=403)

        try:
            student = User.objects.get(id=student_id, organization=user.organization)
        except User.DoesNotExist:
            return Response({'error': 'Student not found in your organization.'}, status=404)

        # Radar chart
        metrics = SkillMetric.objects.filter(user=student).select_related('skill__category')
        cat_scores = defaultdict(list)
        for m in metrics:
            cat_scores[m.skill.category.name].append(m.score)
        radar = [
            {'category': cat, 'score': round(sum(s) / len(s), 1)}
            for cat, s in cat_scores.items() if s
        ]

        # Level
        level_data = compute_level_for_user(student)

        # Profile
        profile = DeveloperProfile.objects.filter(user=student).first()

        # Evaluation history (scores only, no code)
        evals = Evaluation.objects.for_user(student).order_by('-created_at')[:20]
        eval_history = [
            {
                'id': e.id,
                'sha': e.commit_sha[:7],
                'score': float(e.overall_score) if e.overall_score else None,
                'finding_count': e.finding_count,
                'date': e.created_at.strftime('%Y-%m-%d'),
                'project': e.project.name if e.project else '',
            }
            for e in evals
        ]

        # Strengths / weaknesses (by category name, not code)
        strengths = [
            m.skill.category.name
            for m in metrics.order_by('-score')[:3]
            if m.score > 75
        ]
        weaknesses = [
            m.skill.category.name
            for m in metrics.order_by('score')[:3]
            if m.score < 50
        ]

        return Response({
            'student': {
                'id': student.id,
                'name': student.display_name,
                'email': student.email,
            },
            'level': level_data['level'],
            'composite_score': level_data['composite_score'],
            'trend': profile.trend if profile else 'new',
            'radar': radar,
            'strengths': list(set(strengths)),
            'weaknesses': list(set(weaknesses)),
            'evaluation_history': eval_history,
            'score_history': profile.score_history if profile else [],
        })


# ─── Developer Journey ───────────────────────────────────────────────────

class DeveloperJourneyView(APIView):
    """
    Aggregated developer journey data: timeline of growth, skill evolution,
    learning milestones, and current state.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, user_id):
        from users.models import User
        from evaluations.models import Evaluation
        from .models import SkillObservation, LearningProof, GrowthSnapshot
        from .level_calculator import compute_level_for_user
        from datetime import timedelta

        is_admin = getattr(request.user, 'role', None) in ('admin', 'teacher') or getattr(request.user, 'is_staff', False)
        if not (request.user.id == user_id or is_admin):
            return Response({'error': 'Forbidden'}, status=403)

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        project_id = request.query_params.get('project')

        # ── 1. Evaluation timeline ─────────────────────────────────────
        eval_qs = Evaluation.objects.for_user(user).annotate(
            finding_count=Count('findings'),
        ).order_by('created_at')
        if project_id:
            eval_qs = eval_qs.filter(project_id=project_id)

        timeline = []
        for i, ev in enumerate(eval_qs):
            timeline.append({
                'date': ev.created_at.isoformat(),
                'commitSha': ev.commit_sha[:7] if ev.commit_sha else '',
                'message': (ev.commit_message or '')[:80],
                'score': round(ev.overall_score, 1) if ev.overall_score else None,
                'findingCount': ev.finding_count,
                'filesChanged': ev.files_changed or 0,
                'index': i + 1,
            })

        # ── 2. Skill evolution (score over time per category) ──────────
        obs_qs = SkillObservation.objects.filter(user=user).select_related(
            'skill__category'
        ).order_by('created_at')
        if project_id:
            obs_qs = obs_qs.filter(project_id=project_id)

        # Aggregate by category + date
        category_evolution = defaultdict(list)
        for obs in obs_qs:
            cat_name = obs.skill.category.name
            category_evolution[cat_name].append({
                'date': obs.created_at.strftime('%Y-%m-%d'),
                'score': round(obs.weighted_score, 1),
                'skill': obs.skill.name,
                'complexity': obs.complexity_weight,
            })

        # Build per-category score averages per date
        skill_evolution = []
        for cat_name, entries in category_evolution.items():
            by_date = defaultdict(list)
            for e in entries:
                by_date[e['date']].append(e['score'])
            data_points = [
                {'date': d, 'avgScore': round(sum(scores) / len(scores), 1)}
                for d, scores in sorted(by_date.items())
            ]
            skill_evolution.append({
                'category': cat_name,
                'dataPoints': data_points,
            })

        # ── 3. Learning milestones (proofs) ────────────────────────────
        proof_qs = LearningProof.objects.filter(user=user).select_related(
            'skill'
        ).order_by('created_at')

        milestones = []
        for proof in proof_qs:
            milestone = {
                'type': proof.status,
                'skill': proof.skill.name,
                'issueType': proof.issue_type,
                'conceptSummary': proof.concept_summary[:120] if proof.concept_summary else '',
                'understandingLevel': proof.understanding_level,
                'taughtAt': proof.taught_at.isoformat() if proof.taught_at else None,
            }
            if proof.status == 'proven':
                milestone['provenAt'] = proof.proven_at.isoformat() if proof.proven_at else None
                milestone['proofCommit'] = proof.proof_commit[:7] if proof.proof_commit else ''
            elif proof.status == 'relapsed':
                milestone['relapsedAt'] = proof.relapsed_at.isoformat() if proof.relapsed_at else None
                milestone['relapseCommit'] = proof.relapse_commit[:7] if proof.relapse_commit else ''
            milestones.append(milestone)

        # ── 4. Current skill snapshot ──────────────────────────────────
        metrics_qs = SkillMetric.objects.filter(user=user).select_related('skill__category')
        if project_id:
            metrics_qs = metrics_qs.filter(project_id=project_id)

        categories_summary = defaultdict(lambda: {'skills': [], 'totalScore': 0, 'count': 0})
        for m in metrics_qs:
            score = m.bayesian_score if m.observation_count > 0 else m.score
            if score <= 0:
                continue
            cat = m.skill.category.name
            categories_summary[cat]['skills'].append({
                'name': m.skill.name,
                'score': round(score, 1),
                'confidence': round(m.confidence, 2),
                'confidenceLabel': m.confidence_label,
                'levelLabel': m.level_label,
                'observationCount': m.observation_count,
                'provenConcepts': m.proven_concepts,
                'relapsedConcepts': m.relapsed_concepts,
                'trend': m.trend,
            })
            categories_summary[cat]['totalScore'] += score
            categories_summary[cat]['count'] += 1

        current_skills = []
        for cat_name, data in sorted(categories_summary.items()):
            avg = round(data['totalScore'] / data['count'], 1) if data['count'] else 0
            current_skills.append({
                'category': cat_name,
                'avgScore': avg,
                'skills': sorted(data['skills'], key=lambda s: -s['score']),
            })

        # ── 5. Overall stats ───────────────────────────────────────────
        total_evaluations = eval_qs.count()
        total_findings = sum(t['findingCount'] for t in timeline)

        # Score trajectory (first vs last 5 evals)
        scores = [t['score'] for t in timeline if t['score'] is not None]
        first_avg = round(sum(scores[:5]) / len(scores[:5]), 1) if len(scores) >= 5 else (round(sum(scores) / len(scores), 1) if scores else 0)
        last_avg = round(sum(scores[-5:]) / len(scores[-5:]), 1) if len(scores) >= 5 else first_avg

        # Level
        level_data = compute_level_for_user(user, project_id)

        # Proof stats
        proof_total = proof_qs.count()
        proof_proven = proof_qs.filter(status='proven').count()
        proof_reinforced = proof_qs.filter(status='reinforced').count()
        proof_relapsed = proof_qs.filter(status='relapsed').count()
        proof_pending = proof_qs.filter(status='pending').count()

        # First and last evaluation dates
        first_eval = timeline[0]['date'] if timeline else None
        last_eval = timeline[-1]['date'] if timeline else None

        return Response({
            'userId': user_id,
            'userName': user.display_name,
            'stats': {
                'totalEvaluations': total_evaluations,
                'totalFindings': total_findings,
                'firstEvaluation': first_eval,
                'lastEvaluation': last_eval,
                'firstAvgScore': first_avg,
                'lastAvgScore': last_avg,
                'scoreGrowth': round(last_avg - first_avg, 1),
                'level': level_data.get('level', 'Beginner'),
                'compositeScore': level_data.get('composite_score', 0),
            },
            'proofStats': {
                'total': proof_total,
                'proven': proof_proven,
                'reinforced': proof_reinforced,
                'relapsed': proof_relapsed,
                'pending': proof_pending,
            },
            'timeline': timeline,
            'skillEvolution': skill_evolution,
            'milestones': milestones,
            'currentSkills': current_skills,
        })
