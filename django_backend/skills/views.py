"""
Skills API Views
"""
from rest_framework import generics, permissions, status
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

        # Admins may query any user; developers can only query themselves.
        if not (request.user.id == user_id or request.user.role == 'admin' or request.user.is_staff):
            return Response({'error': 'Forbidden'}, status=403)

        from users.models import User

        try:
            subject = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

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

        # Developer level
        try:
            from batch.models import DeveloperProfile
            profile = DeveloperProfile.objects.get(user_id=subject.id)
            level = profile.level
        except Exception:
            if avg_score >= 75:
                level = 'senior'
            elif avg_score >= 60:
                level = 'intermediate'
            elif avg_score >= 40:
                level = 'junior'
            else:
                level = 'beginner'

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
            'recommendations': [],
            'severityDistribution': severity_distribution,
            'categoryBreakdown': category_breakdown,
            'scoreTrend': score_trend,
            'level': level,
            'progression': progression,
            'improving': improving,
            'improvementPct': improvement_pct,
        })


class PerformanceTrendsView(APIView):
    """
    Weekly finding counts grouped by skill category.
    Used by the TrendChart on the Insights page.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, user_id):
        from evaluations.models import Evaluation, FindingSkill
        from datetime import datetime, timedelta
        from collections import defaultdict

        if not (request.user.id == user_id or request.user.role == 'admin' or request.user.is_staff):
            return Response({'error': 'Forbidden'}, status=403)

        from users.models import User

        try:
            subject = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        project_id = request.query_params.get('project')
        weeks = int(request.query_params.get('weeks', 8))

        end_date = tz.now()
        start_date = end_date - timedelta(weeks=weeks)

        evals = Evaluation.objects.for_user(subject).filter(created_at__gte=start_date)
        if project_id:
            evals = evals.filter(project_id=project_id)

        finding_qs = FindingSkill.objects.filter(
            finding__evaluation__in=evals,
        ).select_related('skill__category', 'finding__evaluation')

        weekly: dict = defaultdict(lambda: defaultdict(int))
        for fs in finding_qs:
            eval_date = fs.finding.evaluation.created_at
            week_start = (eval_date - timedelta(days=eval_date.weekday())).strftime('%Y-%m-%d')
            cat = fs.skill.category.name.upper().replace(' ', '_')
            weekly[week_start][cat] += 1

        result = []
        # Align to Monday of start week
        cur = start_date - timedelta(days=start_date.weekday())
        end_monday = end_date - timedelta(days=end_date.weekday()) + timedelta(weeks=1)
        while cur <= end_monday:
            ws = cur.strftime('%Y-%m-%d')
            result.append({'weekStart': ws, 'categories': dict(weekly.get(ws, {}))})
            cur += timedelta(weeks=1)

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

        if not (request.user.id == user_id or request.user.role == 'admin' or request.user.is_staff):
            return Response({'error': 'Forbidden'}, status=403)

        from users.models import User
        from evaluations.models import Evaluation

        try:
            subject = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

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
        level = metric.level if metric else 0

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
                'created_at': f.created_at.isoformat(),
            })
            if not f.is_fixed:
                deductions.append({
                    'reason': f.title,
                    'impact': round(fs.impact_score, 1),
                    'severity': f.severity,
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
        
        project_id = request.query_params.get('project')
        
        # Get user's evaluations (includes unmatched commits with same email)
        evaluations = Evaluation.objects.for_user(request.user)
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
            user=request.user
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
            profile = DeveloperProfile.objects.get(user=request.user)
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
        pattern_qs = Pattern.objects.filter(user=request.user, is_resolved=False)
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


class DashboardSkillsView(APIView):
    """
    Get skill scores grouped by category for radar chart.
    Returns: categories with avg scores.
    """
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        from django.db.models import Avg
        
        project_id = request.query_params.get('project')
        
        # Get user's metrics grouped by category
        metrics = SkillMetric.objects.filter(
            user=request.user
        ).select_related('skill', 'skill__category')
        
        if project_id:
            metrics = metrics.filter(project_id=project_id)
        
        # Group by category and calculate averages
        categories = {}
        for metric in metrics:
            cat_name = metric.skill.category.name
            if cat_name not in categories:
                categories[cat_name] = {
                    'name': cat_name,
                    'scores': [],
                    'color': metric.skill.category.color
                }
            categories[cat_name]['scores'].append(metric.score)
        
        # Calculate averages
        result = []
        for cat_name, data in categories.items():
            avg_score = sum(data['scores']) / len(data['scores']) if data['scores'] else 0
            result.append({
                'category': cat_name,
                'score': round(avg_score, 1),
                'color': data['color']
            })

        if not result:
            # No SkillMetric rows (e.g. author was null at ingest); approximate from FindingSkill
            from evaluations.models import Evaluation, FindingSkill

            evals = Evaluation.objects.for_user(request.user)
            if project_id:
                evals = evals.filter(project_id=project_id)
            cat_map: dict = {}
            for row in FindingSkill.objects.filter(finding__evaluation__in=evals).select_related('skill__category'):
                c = row.skill.category
                name = c.name
                if name not in cat_map:
                    cat_map[name] = {'issues': 0, 'color': c.color}
                cat_map[name]['issues'] += 1
            for cat_name, data in cat_map.items():
                pseudo = max(5.0, 100.0 - min(data['issues'] * 6.0, 85.0))
                result.append({'category': cat_name, 'score': round(pseudo, 1), 'color': data['color']})
        
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
        
        # Get evaluations for the last N weeks
        end_date = tz.now()
        start_date = end_date - timedelta(weeks=weeks)
        
        evaluations = Evaluation.objects.for_user(request.user).filter(
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
        
        from evaluations.models import Evaluation

        user_evals = Evaluation.objects.for_user(request.user)
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
        
        # Verify user exists
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
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
                score = metric.score if metric else 0
                # Derive a simple 0-5 level from score (no DB field)
                level = min(5, int(score / 20)) if score else 0
                cat_data['skills'].append({
                    'id': skill.id,
                    'displayName': skill.name,
                    'score': score,
                    'level': level,
                })
            
            result['categories'].append(cat_data)
        
        return Response(result)
