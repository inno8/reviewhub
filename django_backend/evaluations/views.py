"""
Evaluation API Views
"""
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Avg, Count, Q
from django.utils import timezone

from .models import Evaluation, Finding, FindingSkill
from .serializers import (
    EvaluationSerializer,
    EvaluationListSerializer,
    FindingSerializer,
    InternalEvaluationCreateSerializer,
    DashboardSerializer
)
from projects.models import Project, ProjectMember
from skills.models import Skill, SkillMetric
from users.models import User


class EvaluationListView(generics.ListAPIView):
    """List evaluations with filtering."""
    
    serializer_class = EvaluationListSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['project', 'status', 'branch']
    search_fields = ['commit_message', 'author_name']
    ordering_fields = ['created_at', 'overall_score']
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = Evaluation.objects.select_related('author', 'project')
        
        # Filter by user's projects
        user = self.request.user
        queryset = queryset.filter(
            Q(project__created_by=user) |
            Q(project__members__user=user)
        ).distinct()
        
        return queryset


class EvaluationDetailView(generics.RetrieveAPIView):
    """Get evaluation details with findings."""
    
    queryset = Evaluation.objects.prefetch_related('findings__skills')
    serializer_class = EvaluationSerializer
    permission_classes = [permissions.IsAuthenticated]


class InternalEvaluationCreateView(APIView):
    """
    Create evaluation from FastAPI AI Engine.
    
    This is an internal endpoint, protected by API key.
    """
    
    permission_classes = [permissions.AllowAny]  # TODO: Add API key auth

    def _resolve_author(self, author_email, project, batch_job_id=None):
        """Match git author email to a system User via multiple strategies."""
        # Strategy 1: Direct email match
        try:
            return User.objects.get(email=author_email)
        except User.DoesNotExist:
            pass

        # Strategy 2: ProjectMember.git_email match for this project
        member = ProjectMember.objects.filter(
            project=project,
            git_email=author_email
        ).select_related('user').first()
        if member:
            return member.user

        # Strategy 3: ProjectMember.git_email match across all projects
        member = ProjectMember.objects.filter(
            git_email=author_email
        ).select_related('user').first()
        if member:
            return member.user

        # Strategy 4: Fall back to batch job owner
        if batch_job_id:
            from batch.models import BatchJob
            try:
                batch_job = BatchJob.objects.get(id=batch_job_id)
                return batch_job.user
            except BatchJob.DoesNotExist:
                pass

        return None

    def _detect_patterns(self, user, project, findings):
        """Detect and track recurring patterns from findings."""
        from .models import Pattern

        for finding in findings:
            for skill in finding.skills.select_related('category').all():
                pattern_key = f"{skill.category.slug}_{finding.severity}"
                pattern, created = Pattern.objects.get_or_create(
                    user=user,
                    project=project,
                    pattern_key=pattern_key,
                    defaults={
                        "pattern_type": skill.category.name,
                        "frequency": 0,
                    }
                )
                pattern.increment(finding)

    def post(self, request):
        serializer = InternalEvaluationCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        # Get project
        try:
            project = Project.objects.get(id=data['project_id'])
        except Project.DoesNotExist:
            return Response(
                {'error': 'Project not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Match author to user (multi-strategy)
        author = self._resolve_author(data['author_email'], project, data.get('batch_job_id'))

        # Determine if this is a batch evaluation
        is_batch = data.get('batch_job_id') is not None

        # Create evaluation
        evaluation = Evaluation.objects.create(
            project=project,
            author=author,
            commit_sha=data['commit_sha'],
            commit_message=data['commit_message'],
            commit_timestamp=data.get('commit_timestamp'),
            branch=data['branch'],
            author_name=data['author_name'],
            author_email=data['author_email'],
            files_changed=data['files_changed'],
            lines_added=data['lines_added'],
            lines_removed=data['lines_removed'],
            overall_score=data['overall_score'],
            status=Evaluation.Status.COMPLETED,
            llm_model=data['llm_model'],
            llm_tokens_used=data['llm_tokens_used'],
            processing_ms=data['processing_ms'],
            evaluated_at=timezone.now()
        )
        
        # Skip individual notifications for batch evaluations
        if is_batch:
            evaluation._batch_skip_notifications = True

        # Create findings
        created_findings = []
        for finding_data in data['findings']:
            finding = Finding.objects.create(
                evaluation=evaluation,
                title=finding_data.get('title', 'Unknown Issue'),
                description=finding_data.get('description', ''),
                severity=finding_data.get('severity', 'warning'),
                file_path=finding_data.get('file_path', ''),
                line_start=finding_data.get('line_start', 1),
                line_end=finding_data.get('line_end', 1),
                original_code=finding_data.get('original_code', ''),
                suggested_code=finding_data.get('suggested_code', ''),
                explanation=finding_data.get('explanation', '')
            )
            created_findings.append(finding)

            # Link skills
            for skill_slug in finding_data.get('skills_affected', []):
                try:
                    skill = Skill.objects.get(slug=skill_slug)
                    FindingSkill.objects.create(
                        finding=finding,
                        skill=skill,
                        impact_score=5.0  # Default impact
                    )

                    # Update skill metrics if author is known
                    if author:
                        metric, _ = SkillMetric.objects.get_or_create(
                            user=author,
                            project=project,
                            skill=skill
                        )
                        metric.update_score(new_issues=1)

                except Skill.DoesNotExist:
                    pass

        # Detect patterns (recurring issues by category + severity)
        if author and created_findings:
            self._detect_patterns(author, project, created_findings)

        return Response(
            EvaluationSerializer(evaluation).data,
            status=status.HTTP_201_CREATED
        )


class FindingListView(generics.ListAPIView):
    """List findings with filtering."""
    
    serializer_class = FindingSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['severity', 'is_fixed']
    search_fields = ['title', 'description', 'file_path']
    ordering = ['-evaluation__created_at', '-severity']
    
    def get_queryset(self):
        queryset = Finding.objects.select_related('evaluation__project')
        
        # Filter by project if specified
        project_id = self.request.query_params.get('project')
        if project_id:
            queryset = queryset.filter(evaluation__project_id=project_id)
        
        return queryset


class FindingDetailView(generics.RetrieveAPIView):
    """Get finding details."""
    
    queryset = Finding.objects.prefetch_related('skills', 'finding_skills')
    serializer_class = FindingSerializer
    permission_classes = [permissions.IsAuthenticated]


class MarkFindingFixedView(APIView):
    """Mark a finding as fixed."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, pk):
        try:
            finding = Finding.objects.get(pk=pk)
        except Finding.DoesNotExist:
            return Response(
                {'error': 'Finding not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        commit_sha = request.data.get('commit_sha')
        finding.mark_fixed(commit_sha)
        
        return Response(FindingSerializer(finding).data)


class DashboardView(APIView):
    """Dashboard overview data."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        project_id = request.query_params.get('project')
        
        # Base querysets
        evaluations = Evaluation.objects.filter(
            Q(project__created_by=user) |
            Q(project__members__user=user)
        ).distinct()
        
        if project_id:
            evaluations = evaluations.filter(project_id=project_id)
        
        findings = Finding.objects.filter(evaluation__in=evaluations)
        
        # Aggregate stats
        stats = evaluations.aggregate(
            total=Count('id'),
            avg_score=Avg('overall_score')
        )
        
        finding_stats = findings.aggregate(
            total=Count('id'),
            fixed=Count('id', filter=Q(is_fixed=True))
        )
        
        # Skill summary
        skill_summary = {}
        skill_counts = FindingSkill.objects.filter(
            finding__evaluation__in=evaluations
        ).values('skill__slug', 'skill__name').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        for sc in skill_counts:
            skill_summary[sc['skill__slug']] = {
                'name': sc['skill__name'],
                'issue_count': sc['count']
            }
        
        # Recent evaluations
        recent = evaluations.order_by('-created_at')[:5]
        
        return Response({
            'total_evaluations': stats['total'] or 0,
            'total_findings': finding_stats['total'] or 0,
            'fixed_findings': finding_stats['fixed'] or 0,
            'average_score': round(stats['avg_score'] or 0, 1),
            'recent_evaluations': EvaluationListSerializer(recent, many=True).data,
            'skill_summary': skill_summary
        })
