"""
Skills API Views
"""
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q

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
    
    permission_classes = [permissions.AllowAny]  # TODO: Add API key auth
    
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
    """
    Get skill score trends over time.
    """
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        project_id = request.query_params.get('project')
        skill_slug = request.query_params.get('skill')
        
        # Get user's metrics
        metrics = SkillMetric.objects.filter(
            user=request.user
        ).select_related('skill')
        
        if project_id:
            metrics = metrics.filter(project_id=project_id)
        
        if skill_slug:
            metrics = metrics.filter(skill__slug=skill_slug)
        
        # Build trend data
        trends = []
        for metric in metrics:
            trends.append({
                'skill_slug': metric.skill.slug,
                'skill_name': metric.skill.name,
                'current_score': metric.score,
                'trend': metric.trend,
                'issue_count': metric.issue_count,
                'fix_rate': metric.fix_rate,
                # TODO: Add historical data points from evaluation history
                'data_points': []
            })
        
        return Response(trends)


class DashboardOverviewView(APIView):
    """
    Get overall dashboard stats for current user.
    Returns: total evaluations, findings, avg score, etc.
    """
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        from evaluations.models import Evaluation, Finding
        from django.db.models import Avg, Count
        
        project_id = request.query_params.get('project')
        
        # Get user's evaluations
        evaluations = Evaluation.objects.filter(author=request.user)
        if project_id:
            evaluations = evaluations.filter(project_id=project_id)
        
        # Get user's findings
        findings = Finding.objects.filter(evaluation__author=request.user)
        if project_id:
            findings = findings.filter(evaluation__project_id=project_id)
        
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
        
        return Response({
            'total_evaluations': total_evaluations,
            'total_findings': total_findings,
            'avg_score': round(avg_score, 1),
            'critical_count': critical_count,
            'warning_count': warning_count,
            'info_count': info_count,
            'fixed_count': fixed_count,
            'fix_rate': round(fix_rate, 1)
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
        end_date = datetime.now()
        start_date = end_date - timedelta(weeks=weeks)
        
        evaluations = Evaluation.objects.filter(
            author=request.user,
            created_at__gte=start_date
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
        
        # Build query - filter BEFORE slicing
        queryset = Finding.objects.filter(
            evaluation__author=request.user
        ).select_related(
            'evaluation'
        ).prefetch_related(
            'skills'
        )
        
        if project_id:
            queryset = queryset.filter(evaluation__project_id=project_id)
        
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
