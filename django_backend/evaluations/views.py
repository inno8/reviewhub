"""
Evaluation API Views
"""
from collections import Counter
from urllib.parse import quote

import requests
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Avg, Count, Q
from django.utils import timezone

from .models import Evaluation, Finding, FindingSkill, Pattern
from .serializers import (
    EvaluationSerializer,
    EvaluationListSerializer,
    FindingSerializer,
    InternalEvaluationCreateSerializer,
    DashboardSerializer,
    PatternSerializer,
)
from projects.models import Project, ProjectMember
from skills.models import Skill, SkillMetric
from users.models import User, GitProviderConnection


def _user_can_access_project_q(user, project_field_prefix: str) -> Q:
    """Same rules as projects list: creator, project member, or team member."""
    prefix = project_field_prefix.rstrip("_")
    return (
        Q(**{f"{prefix}__created_by": user})
        | Q(**{f"{prefix}__members__user": user})
        | Q(**{f"{prefix}__team__members__user": user})
    )


class EvaluationListView(generics.ListAPIView):
    """List evaluations with filtering."""
    
    serializer_class = EvaluationListSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['project', 'status', 'branch']
    search_fields = ['commit_message', 'author_name']
    ordering_fields = ['created_at', 'overall_score']
    ordering = ['-created_at']
    
    def get_queryset(self):
        user = self.request.user

        # Admins see every evaluation (for the commit timeline and file review)
        if getattr(user, 'role', None) == 'admin' or getattr(user, 'is_staff', False):
            return Evaluation.objects.select_related('author', 'project')

        # Developers see evaluations they authored (by FK or email identity) +
        # evaluations belonging to projects they have access to
        by_identity = Evaluation.objects.for_user(user).values_list('pk', flat=True)
        by_project = Evaluation.objects.filter(
            _user_can_access_project_q(user, "project")
        ).values_list('pk', flat=True)

        all_ids = set(by_identity) | set(by_project)
        return Evaluation.objects.select_related('author', 'project').filter(
            pk__in=all_ids
        )


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
    
    permission_classes = []

    def get_permissions(self):
        from reviewhub.permissions import IsInternalAPIKey
        return [IsInternalAPIKey()]

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
        
        # ── User mapping (3-step fallback per ARCHITECTURE_V2) ──────────
        author = self._resolve_author(
            project=project,
            email=data['author_email'],
            sender_login=data.get('sender_login', ''),
        )
        
        if not author:
            # Unknown user -- log and still create the evaluation
            import logging
            logging.getLogger(__name__).warning(
                'Unmatched commit author %s (%s) for project %s',
                data['author_name'], data['author_email'], project.id,
            )
        
        from batch.models import BatchJob

        batch_job = None
        raw_bjid = data.get('batch_job_id')
        if raw_bjid is not None:
            batch_job = BatchJob.objects.filter(pk=raw_bjid, project=project).first()

        # ── Create evaluation ─────────────────────────────────────────
        evaluation = Evaluation.objects.create(
            project=project,
            batch_job=batch_job,
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
            overall_score=data.get('overall_score'),
            status=Evaluation.Status.COMPLETED,
            llm_model=data['llm_model'],
            llm_tokens_used=data['llm_tokens_used'],
            processing_ms=data['processing_ms'],
            commit_complexity=data.get('commit_complexity', ''),
            complexity_score=data.get('complexity_score'),
            evaluated_at=timezone.now()
        )
        
        # ── Create findings + skills + patterns ───────────────────────
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
            
            for skill_slug in finding_data.get('skills_affected', []):
                try:
                    skill = Skill.objects.get(slug=skill_slug)
                    severity = finding_data.get('severity', 'warning')
                    impact = {'critical': 10.0, 'warning': 5.0, 'info': 2.0, 'suggestion': 1.0}.get(severity, 5.0)
                    
                    FindingSkill.objects.create(
                        finding=finding, skill=skill, impact_score=impact
                    )
                    
                    if author:
                        metric, _ = SkillMetric.objects.get_or_create(
                            user=author, project=project, skill=skill
                        )
                        metric.update_score(new_issues=1, impact=impact)
                        
                        # ── Pattern detection ────────────────────────
                        pattern_key = f"{skill_slug}:{severity}"
                        pattern, created = Pattern.objects.get_or_create(
                            user=author,
                            project=project,
                            pattern_key=pattern_key,
                            defaults={
                                'pattern_type': skill_slug,
                            }
                        )
                        if not created:
                            pattern.increment(finding)
                        else:
                            pattern.sample_findings.add(finding)
                        
                except Skill.DoesNotExist:
                    pass
        
        return Response(
            EvaluationSerializer(evaluation).data,
            status=status.HTTP_201_CREATED
        )
    
    # ── Private helpers ───────────────────────────────────────────────
    
    @staticmethod
    def _resolve_author(project, email, sender_login=''):
        """
        Resolve commit author to a User:
          1. User.email
          2. ProjectMember.git_email (this project)
          3. GitProviderConnection.email (project member, provider matches project)
          4. ProjectMember.git_username vs sender_login
          5. GitProviderConnection.username (same)
        """
        member_ids = ProjectMember.objects.filter(project=project).values_list('user_id', flat=True)
        prov = (project.provider or '').lower()

        # Step 1: direct email match
        try:
            return User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            pass

        # Step 2: ProjectMember.git_email
        member = ProjectMember.objects.filter(
            project=project, git_email__iexact=email
        ).select_related('user').first()
        if member:
            return member.user

        # Step 3: Settings → linked Git emails (multiple connections per user)
        if email:
            conn = GitProviderConnection.objects.filter(
                user_id__in=member_ids,
                provider=prov,
                email__iexact=email,
            ).exclude(email__isnull=True).exclude(email='').select_related('user').first()
            if conn:
                return conn.user

        # Step 4: ProjectMember.git_username
        if sender_login:
            member = ProjectMember.objects.filter(
                project=project, git_username__iexact=sender_login
            ).select_related('user').first()
            if member:
                return member.user

            conn = GitProviderConnection.objects.filter(
                user_id__in=member_ids,
                provider=prov,
                username__iexact=sender_login,
            ).select_related('user').first()
            if conn:
                return conn.user

        return None


class FindingListView(generics.ListAPIView):
    """List findings with filtering."""
    
    serializer_class = FindingSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['severity', 'is_fixed']
    search_fields = ['title', 'description', 'file_path']
    ordering = ['-evaluation__created_at', '-severity']
    
    def get_queryset(self):
        user = self.request.user
        queryset = Finding.objects.select_related('evaluation__project')

        queryset = queryset.filter(
            _user_can_access_project_q(user, "evaluation__project")
            | Q(evaluation__author=user)
        ).distinct()

        project_id = self.request.query_params.get('project')
        if project_id:
            queryset = queryset.filter(evaluation__project_id=project_id)

        date_str = self.request.query_params.get('date')
        if date_str:
            try:
                from datetime import datetime

                day = datetime.strptime(date_str, '%Y-%m-%d').date()
                queryset = queryset.filter(evaluation__created_at__date=day)
            except ValueError:
                pass

        return queryset


class FindingDetailView(generics.RetrieveAPIView):
    """Get finding details."""

    serializer_class = FindingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return (
            Finding.objects.select_related('evaluation__project')
            .prefetch_related('skills', 'finding_skills')
            .filter(
                _user_can_access_project_q(user, 'evaluation__project')
                | Q(evaluation__author=user)
            )
            .distinct()
        )


class FindingFileContentView(APIView):
    """
    Fetch full file text from GitHub for the finding's path at the evaluation's branch.
    Used by the file review UI. Returns { content: string, detail?: string }.
    """

    permission_classes = [permissions.IsAuthenticated]

    @staticmethod
    def _encode_github_path(path: str) -> str:
        path = (path or '').strip().lstrip('/').replace('\\', '/')
        segments = [s for s in path.split('/') if s]
        return '/'.join(quote(seg, safe='') for seg in segments)

    def get(self, request, pk):
        base_qs = (
            Finding.objects.select_related('evaluation__project')
            .filter(
                _user_can_access_project_q(request.user, 'evaluation__project')
                | Q(evaluation__author=request.user)
            )
            .distinct()
        )
        finding = get_object_or_404(base_qs, pk=pk)
        evaluation = finding.evaluation
        project = evaluation.project
        rel_path = (finding.file_path or '').strip().lstrip('/')
        if not rel_path:
            return Response({'content': '', 'detail': 'Finding has no file path.'})

        if project.provider != Project.Provider.GITHUB:
            return Response({
                'content': '',
                'detail': 'File fetch is only implemented for GitHub projects.',
            })

        owner = (project.repo_owner or '').strip()
        repo = (project.repo_name or '').strip()
        if not owner or not repo:
            return Response({
                'content': '',
                'detail': 'Project has no GitHub repository configured.',
            })

        branch = (evaluation.branch or project.default_branch or 'main').strip()
        path_encoded = self._encode_github_path(rel_path)
        url = f'https://api.github.com/repos/{owner}/{repo}/contents/{path_encoded}'
        headers = {
            'Accept': 'application/vnd.github.raw',
            'X-GitHub-Api-Version': '2022-11-28',
        }
        token = (getattr(request.user, 'github_personal_access_token', None) or '').strip()
        if not token:
            token = (getattr(settings, 'GITHUB_TOKEN', None) or '').strip()
        if token:
            headers['Authorization'] = f'Bearer {token}'

        try:
            r = requests.get(url, params={'ref': branch}, headers=headers, timeout=30)
        except requests.RequestException as e:
            return Response({'content': '', 'detail': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        if r.status_code == 404:
            return Response({
                'content': '',
                'detail': 'File or branch not found on GitHub (check path and token for private repos).',
            })

        if r.status_code != 200:
            return Response(
                {
                    'content': '',
                    'detail': f'GitHub returned {r.status_code}: {(r.text or "")[:300]}',
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({'content': r.text})


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


class CalendarView(APIView):
    """Return dates with evaluation activity and per-date counts."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        project_id = request.query_params.get('project')
        month = request.query_params.get('month', '')  # "YYYY-MM"

        qs = Evaluation.objects.filter(
            _user_can_access_project_q(request.user, "project")
            | Q(author=request.user)
        ).distinct()

        if project_id:
            qs = qs.filter(project_id=project_id)

        if month:
            try:
                year, m = month.split('-')
                qs = qs.filter(created_at__year=int(year), created_at__month=int(m))
            except (ValueError, IndexError):
                pass

        dates = qs.values_list('created_at__date', flat=True)
        counts: Counter = Counter()
        for d in dates:
            if d:
                counts[d.isoformat()] += 1

        return Response({
            'dates': list(counts.keys()),
            'counts': counts,
        })


class DashboardView(APIView):
    """Dashboard overview data."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        project_id = request.query_params.get('project')
        
        # Base querysets
        evaluations = Evaluation.objects.filter(
            _user_can_access_project_q(user, "project") | Q(author=user)
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


class PatternListView(generics.ListAPIView):
    """
    GET /api/evaluations/patterns/
    List all recurring issue patterns for the current user.
    Optional ?project=<id> filter.
    Supports ?resolved=true|false to filter by resolution status.
    """

    serializer_class = PatternSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Pattern.objects.filter(user=user)

        project_id = self.request.query_params.get('project')
        if project_id:
            qs = qs.filter(project_id=project_id)

        resolved_param = self.request.query_params.get('resolved')
        if resolved_param == 'true':
            qs = qs.filter(is_resolved=True)
        elif resolved_param == 'false':
            qs = qs.filter(is_resolved=False)

        return qs.order_by('-frequency', '-last_seen')


class PatternResolveView(APIView):
    """
    POST /api/evaluations/patterns/<id>/resolve/
    Mark a pattern as resolved.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk: int):
        pattern = get_object_or_404(Pattern, pk=pk, user=request.user)
        from django.utils import timezone as tz
        pattern.is_resolved = True
        pattern.resolved_at = tz.now()
        pattern.save(update_fields=['is_resolved', 'resolved_at'])
        return Response(PatternSerializer(pattern).data)
