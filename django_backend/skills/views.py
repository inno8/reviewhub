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
