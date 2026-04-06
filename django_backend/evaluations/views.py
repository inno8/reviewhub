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
    filterset_fields = ['project', 'status', 'branch', 'author']
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
        
        # Fallback: use batch job owner as author if this is a batch evaluation
        if not author and data.get('batch_job_id'):
            from batch.models import BatchJob
            bj = BatchJob.objects.filter(pk=data['batch_job_id']).select_related('user').first()
            if bj:
                author = bj.user

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

        # Skip individual notifications for batch evaluations
        if batch_job:
            evaluation._batch_skip_notifications = True

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

        # Auto-resolve patterns that haven't appeared in last 10 commits
        if author:
            self._auto_resolve_patterns(author, project)

        # Update DeveloperProfile level with composite calculation
        if author:
            try:
                from skills.level_calculator import compute_level_for_user
                from batch.models import DeveloperProfile
                level_data = compute_level_for_user(author)
                DeveloperProfile.objects.filter(user=author).update(
                    level=level_data['level'],
                    overall_score=level_data['composite_score'],
                )
            except Exception:
                pass

        return Response(
            EvaluationSerializer(evaluation).data,
            status=status.HTTP_201_CREATED
        )
    
    @staticmethod
    def _auto_resolve_patterns(user, project):
        """
        After each evaluation, check if any active patterns for this user
        did NOT appear in the last 10 commits. If so, auto-resolve them.
        """
        try:
            active_patterns = Pattern.objects.filter(
                user=user, project=project, is_resolved=False
            )
            if not active_patterns.exists():
                return

            # Get last 10 evaluations for this user+project
            recent_evals = Evaluation.objects.filter(
                author=user, project=project
            ).order_by('-created_at')[:10]

            if recent_evals.count() < 5:
                return  # Not enough data to auto-resolve

            # Get all finding IDs from recent evaluations
            recent_finding_ids = set(
                Finding.objects.filter(
                    evaluation__in=recent_evals
                ).values_list('id', flat=True)
            )

            # Get skill slugs from recent findings
            recent_skill_slugs = set(
                FindingSkill.objects.filter(
                    finding_id__in=recent_finding_ids
                ).values_list('skill__slug', flat=True)
            )

            from notifications.models import Notification
            from skills.models import SkillMetric, Skill

            for pattern in active_patterns:
                # Extract skill slug from pattern_key (format: "skill_slug:severity")
                pattern_skill = pattern.pattern_key.split(':')[0] if ':' in pattern.pattern_key else pattern.pattern_type

                # Check if this pattern's skill appeared in recent findings
                if pattern_skill not in recent_skill_slugs:
                    # Pattern hasn't appeared in last 10 commits — auto-resolve!
                    pattern.is_resolved = True
                    pattern.resolved_at = timezone.now()
                    pattern.save(update_fields=['is_resolved', 'resolved_at'])

                    # Improve skill score
                    recovery = min(10.0, pattern.frequency / 5.0)
                    try:
                        skill = Skill.objects.get(slug=pattern_skill)
                        for metric in SkillMetric.objects.filter(user=user, project=project, skill=skill):
                            metric.improve_score(fixed_issues=0, recovery=recovery)
                    except Skill.DoesNotExist:
                        pass

                    # Notify developer
                    Notification.objects.create(
                        user=user,
                        type='skill_improvement',
                        title=f'Pattern Resolved: {pattern.pattern_type.replace("_", " ").title()}',
                        message=(
                            f"You haven't had any {pattern.pattern_type.replace('_', ' ')} issues "
                            f"in your last 10 commits. This pattern has been auto-resolved!"
                        ),
                        data={
                            'pattern_id': pattern.id,
                            'pattern_type': pattern.pattern_type,
                            'frequency': pattern.frequency,
                            'skill_boost': round(recovery, 1),
                        },
                    )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning('Auto-resolve patterns failed: %s', e)

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

        # Fallback for non-GitHub or missing repo config: return stored code
        if project.provider != Project.Provider.GITHUB:
            return Response({
                'content': finding.original_code or '',
                'detail': 'Showing stored code snippet (GitHub fetch not available).',
            })

        owner = (project.repo_owner or '').strip()
        repo = (project.repo_name or '').strip()
        if not owner or not repo:
            return Response({
                'content': finding.original_code or '',
                'detail': 'Showing stored code snippet (no repo configured).',
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

        if r.status_code == 200:
            return Response({'content': r.text})

        # Fallback: return the finding's stored original_code when GitHub fetch fails
        if finding.original_code:
            return Response({
                'content': finding.original_code,
                'detail': f'GitHub returned {r.status_code}. Showing stored code snippet.',
            })

        return Response({
            'content': '',
            'detail': f'GitHub returned {r.status_code} and no stored code available.',
        })


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


class CheckUnderstandingView(APIView):
    """
    Fix & Learn: evaluate developer's understanding of findings.
    Groups findings by skill category, sends explanation to LLM,
    returns understanding level (got_it/partial/not_yet) with feedback.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        entries = request.data.get('findings', [])
        if not entries:
            return Response({'error': 'No findings provided'}, status=400)

        results = []
        for entry in entries:
            finding_id = entry.get('id')
            explanation = (entry.get('explanation') or '').strip()
            if not finding_id or not explanation:
                continue

            try:
                finding = Finding.objects.select_related('evaluation__project').get(pk=finding_id)
            except Finding.DoesNotExist:
                continue

            # Anti-cheat: detect if developer copy-pasted the LLM explanation
            from difflib import SequenceMatcher
            explanation_lower = explanation.lower()
            cheat_sources = [
                (finding.explanation or '').lower(),
                (finding.description or '').lower(),
                (finding.suggested_code or '').lower(),
            ]
            is_copy_paste = any(
                SequenceMatcher(None, explanation_lower, src).ratio() > 0.7
                for src in cheat_sources if len(src) > 20
            )
            if is_copy_paste:
                finding.developer_explanation = explanation
                finding.understanding_level = 'not_yet'
                finding.understanding_feedback = (
                    "It looks like you copied the explanation from the review. "
                    "Please explain in your own words why this code is problematic. "
                    "The goal is to make sure you truly understand the issue, not just repeat it."
                )
                finding.save(update_fields=['developer_explanation', 'understanding_level', 'understanding_feedback'])
                results.append({
                    'finding_id': finding_id,
                    'level': 'not_yet',
                    'feedback': finding.understanding_feedback,
                    'deeper_explanation': finding.explanation or finding.description or '',
                })
                continue

            # Call FastAPI to evaluate understanding
            import httpx
            from django.conf import settings as django_settings

            fastapi_url = getattr(django_settings, 'FASTAPI_URL', 'http://localhost:8001')
            try:
                resp = httpx.post(
                    f"{fastapi_url}/api/v1/analyze/understand",
                    json={
                        'category': finding.title,
                        'finding_titles': [finding.title],
                        'finding_descriptions': [finding.description],
                        'suggested_fixes': [finding.suggested_code or ''],
                        'developer_explanation': explanation,
                        'developer_level': 'junior',  # TODO: get from profile
                    },
                    timeout=30,
                )
                if resp.status_code == 200:
                    llm_result = resp.json()
                else:
                    llm_result = {'level': 'partial', 'feedback': 'Could not evaluate — try again.', 'deeper_explanation': ''}
            except Exception:
                llm_result = {'level': 'partial', 'feedback': 'Evaluation service unavailable.', 'deeper_explanation': ''}

            # Store on finding
            finding.developer_explanation = explanation
            finding.understanding_level = llm_result.get('level', 'partial')
            finding.understanding_feedback = llm_result.get('feedback', '')
            finding.save(update_fields=['developer_explanation', 'understanding_level', 'understanding_feedback'])

            results.append({
                'finding_id': finding_id,
                'level': finding.understanding_level,
                'feedback': finding.understanding_feedback,
                'deeper_explanation': llm_result.get('deeper_explanation', ''),
            })

        return Response({'results': results})


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
    Verify the pattern is actually gone from recent commits before resolving.
    If still present, return the affected findings so dev can fix them first.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk: int):
        pattern = get_object_or_404(Pattern, pk=pk, user=request.user)
        force = request.data.get('force', False)

        # Check last 3 commits for this pattern
        recent_evals = Evaluation.objects.for_user(request.user)
        if pattern.project:
            recent_evals = recent_evals.filter(project=pattern.project)
        recent_evals = recent_evals.order_by('-created_at')[:3]

        # Find findings in recent commits that match this pattern's skill
        pattern_skill = pattern.pattern_key.split(':')[0] if ':' in pattern.pattern_key else pattern.pattern_type
        recent_findings = Finding.objects.filter(
            evaluation__in=recent_evals,
            finding_skills__skill__slug=pattern_skill,
        ).select_related('evaluation').distinct()

        recent_count = recent_findings.count()

        # If pattern still appears and not forced, BLOCK the resolve
        if recent_count > 0 and not force:
            affected_files = []
            for f in recent_findings[:5]:
                affected_files.append({
                    'finding_id': f.id,
                    'title': f.title,
                    'file_path': f.file_path,
                    'severity': f.severity,
                    'commit_sha': f.evaluation.commit_sha[:7] if f.evaluation.commit_sha else '',
                    'evaluation_id': f.evaluation.id,
                })

            return Response({
                'resolved': False,
                'reason': (
                    f"This pattern still appeared {recent_count} time(s) in your "
                    f"last 3 commits. Fix the issues below first, then try resolving again."
                ),
                'recent_occurrences': recent_count,
                'affected_files': affected_files,
            })

        # Pattern not found in last 3 commits (or forced) — resolve it
        pattern.is_resolved = True
        pattern.resolved_at = timezone.now()
        pattern.save(update_fields=['is_resolved', 'resolved_at'])

        # Improve related skill metrics
        from skills.models import SkillMetric, Skill
        recovery = 0
        try:
            skill = Skill.objects.get(slug=pattern_skill)
            metrics = SkillMetric.objects.filter(user=request.user, skill=skill)
            if pattern.project:
                metrics = metrics.filter(project=pattern.project)
            recovery = min(10.0, pattern.frequency / 5.0)
            for metric in metrics:
                metric.improve_score(fixed_issues=0, recovery=recovery)
        except Skill.DoesNotExist:
            pass

        from .serializers import PatternSerializer
        data = PatternSerializer(pattern).data
        data['resolved'] = True
        data['message'] = (
            f"Confirmed! No {pattern.pattern_type.replace('_', ' ')} issues "
            f"in your last 3 commits. Pattern resolved! (+{round(recovery, 1)} skill points)"
        )
        data['skill_boost'] = round(recovery, 1)
        return Response(data)
