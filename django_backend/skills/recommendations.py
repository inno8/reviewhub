"""
Learning Recommendations View
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from datetime import timedelta

from django.utils import timezone

from .models import SkillMetric


class LearningRecommendationsView(APIView):
    """
    Get personalized learning recommendations based on:
    - Skills with low scores
    - Recent findings by category
    - Skills that haven't improved recently
    """
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        from evaluations.models import Finding
        
        project_id = request.query_params.get('project')
        limit = int(request.query_params.get('limit', 5))
        
        # Get user's skill metrics
        metrics = SkillMetric.objects.filter(
            user=request.user
        ).select_related('skill', 'skill__category')
        
        if project_id:
            metrics = metrics.filter(project_id=project_id)
        
        recommendations = []
        
        # 1. Find skills with low scores (below 70)
        low_score_metrics = metrics.filter(score__lt=70).order_by('score')[:limit]
        
        for metric in low_score_metrics:
            priority = 'high' if metric.score < 50 else 'medium'
            
            recommendations.append({
                'skill': {
                    'id': metric.skill.id,
                    'name': metric.skill.name,
                    'slug': metric.skill.slug,
                    'category': metric.skill.category.name
                },
                'current_score': metric.score,
                'reason': f'Low score in {metric.skill.name}',
                'priority': priority,
                'issue_count': metric.issue_count,
                'suggested_resources': self._get_resources_for_skill(metric.skill.slug),
                'improvement_tip': self._get_improvement_tip(metric.skill.slug, metric.issue_count)
            })
        
        # 2. Find skills with many recent issues (last 30 days)
        from evaluations.models import Evaluation

        thirty_days_ago = timezone.now() - timedelta(days=30)
        user_evals = Evaluation.objects.for_user(request.user)
        if project_id:
            user_evals = user_evals.filter(project_id=project_id)
        recent_findings = Finding.objects.filter(
            evaluation__in=user_evals,
            created_at__gte=thirty_days_ago,
            is_fixed=False,
        ).prefetch_related('skills')
        
        # Count issues by skill
        skill_issue_counts = {}
        for finding in recent_findings:
            for skill in finding.skills.all():
                if skill.id not in skill_issue_counts:
                    skill_issue_counts[skill.id] = {
                        'skill': skill,
                        'count': 0,
                        'severity_counts': {'critical': 0, 'warning': 0, 'info': 0, 'suggestion': 0}
                    }
                skill_issue_counts[skill.id]['count'] += 1
                sev = finding.severity.lower()
                if sev in skill_issue_counts[skill.id]['severity_counts']:
                    skill_issue_counts[skill.id]['severity_counts'][sev] += 1
        
        # Add recommendations for skills with many recent issues
        for skill_id, data in sorted(
            skill_issue_counts.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )[:3]:
            skill = data['skill']
            
            # Check if not already in recommendations
            if not any(r['skill']['id'] == skill.id for r in recommendations):
                priority = 'high' if data['severity_counts']['critical'] > 0 else 'medium'
                
                recommendations.append({
                    'skill': {
                        'id': skill.id,
                        'name': skill.name,
                        'slug': skill.slug,
                        'category': skill.category.name
                    },
                    'current_score': next(
                        (m.score for m in metrics if m.skill.id == skill.id),
                        0
                    ),
                    'reason': f'{data["count"]} recent issues in {skill.name}',
                    'priority': priority,
                    'issue_count': data['count'],
                    'severity_breakdown': data['severity_counts'],
                    'suggested_resources': self._get_resources_for_skill(skill.slug),
                    'improvement_tip': self._get_improvement_tip(skill.slug, data['count'])
                })
        
        # 3. Skills with negative trends
        declining_metrics = metrics.filter(trend='declining').order_by('score')[:2]
        
        for metric in declining_metrics:
            # Check if not already in recommendations
            if not any(r['skill']['id'] == metric.skill.id for r in recommendations):
                recommendations.append({
                    'skill': {
                        'id': metric.skill.id,
                        'name': metric.skill.name,
                        'slug': metric.skill.slug,
                        'category': metric.skill.category.name
                    },
                    'current_score': metric.score,
                    'reason': f'Declining trend in {metric.skill.name}',
                    'priority': 'medium',
                    'issue_count': metric.issue_count,
                    'trend': metric.trend,
                    'suggested_resources': self._get_resources_for_skill(metric.skill.slug),
                    'improvement_tip': self._get_improvement_tip(metric.skill.slug, metric.issue_count)
                })
        
        # Sort by priority and limit
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        recommendations.sort(key=lambda x: priority_order.get(x['priority'], 3))
        
        return Response(recommendations[:limit])
    
    def _get_resources_for_skill(self, skill_slug):
        """Get learning resources for a skill."""
        resources_map = {
            'code-quality': [
                {'title': 'Clean Code by Robert Martin', 'type': 'book', 'url': 'https://www.oreilly.com/library/view/clean-code-a/9780136083238/'},
                {'title': 'Code Quality Best Practices', 'type': 'article', 'url': 'https://www.sonarsource.com/learn/code-quality/'},
            ],
            'security': [
                {'title': 'OWASP Top 10', 'type': 'documentation', 'url': 'https://owasp.org/www-project-top-ten/'},
                {'title': 'Secure Coding Practices', 'type': 'course', 'url': 'https://www.coursera.org/learn/secure-coding-practices'},
            ],
            'performance': [
                {'title': 'Web Performance Fundamentals', 'type': 'course', 'url': 'https://frontendmasters.com/courses/web-performance/'},
                {'title': 'High Performance Browser Networking', 'type': 'book', 'url': 'https://hpbn.co/'},
            ],
            'testing': [
                {'title': 'Testing JavaScript', 'type': 'course', 'url': 'https://testingjavascript.com/'},
                {'title': 'Unit Testing Best Practices', 'type': 'article', 'url': 'https://github.com/goldbergyoni/javascript-testing-best-practices'},
            ],
            'documentation': [
                {'title': 'Write the Docs Guide', 'type': 'documentation', 'url': 'https://www.writethedocs.org/guide/'},
                {'title': 'Documentation Best Practices', 'type': 'article', 'url': 'https://documentation.divio.com/'},
            ],
        }
        
        return resources_map.get(skill_slug, [
            {'title': f'Learn more about {skill_slug}', 'type': 'search', 'url': f'https://google.com/search?q={skill_slug}+best+practices'}
        ])
    
    def _get_improvement_tip(self, skill_slug, issue_count):
        """Get an improvement tip for a skill."""
        tips_map = {
            'code-quality': 'Focus on writing cleaner, more maintainable code. Review SOLID principles.',
            'security': 'Review OWASP guidelines and implement security checks in your workflow.',
            'performance': 'Profile your code to identify bottlenecks. Consider caching strategies.',
            'testing': 'Aim for at least 80% code coverage. Write tests before fixing bugs.',
            'documentation': 'Document as you code. Keep README and inline comments up to date.',
        }
        
        base_tip = tips_map.get(skill_slug, f'Review recent issues and identify common patterns.')
        
        if issue_count > 10:
            return f'{base_tip} Start with the most critical issues first.'
        elif issue_count > 5:
            return f'{base_tip} Focus on preventing similar issues in new code.'
        else:
            return base_tip
