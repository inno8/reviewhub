"""
Evaluation API Views
"""
from collections import Counter
from urllib.parse import quote

import requests
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import IntegrityError
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

        # Admins see evaluations belonging to their org's projects
        if getattr(user, 'role', None) in ('admin', 'teacher') or getattr(user, 'is_staff', False):
            qs = Evaluation.objects.select_related('author', 'project')
            if user.organization_id:
                qs = qs.filter(project__created_by__organization=user.organization)
        else:
            # Developers see evaluations they authored (by FK or email identity) +
            # evaluations belonging to projects they have access to
            by_identity = Evaluation.objects.for_user(user).values_list('pk', flat=True)
            by_project = Evaluation.objects.filter(
                _user_can_access_project_q(user, "project")
            ).values_list('pk', flat=True)

            all_ids = set(by_identity) | set(by_project)
            qs = Evaluation.objects.select_related('author', 'project').filter(
                pk__in=all_ids
            )

        # Date filter: ?date=YYYY-MM-DD
        date_str = self.request.query_params.get('date')
        if date_str:
            from datetime import datetime
            try:
                dt = datetime.strptime(date_str, '%Y-%m-%d').date()
                qs = qs.filter(created_at__date=dt)
            except ValueError:
                pass

        return qs


class EvaluationChartView(APIView):
    """Return evaluation data optimised for the score-over-time chart.

    Each item includes a compact skill_summary (top affected skills)
    and a delta vs the previous commit so the frontend can render
    improvement / decline indicators without extra computation.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        is_admin = getattr(user, 'role', None) in ('admin', 'teacher') or getattr(user, 'is_staff', False)

        if is_admin:
            qs = Evaluation.objects.select_related('author', 'project')
            if user.organization_id:
                qs = qs.filter(project__created_by__organization=user.organization)
        else:
            by_identity = Evaluation.objects.for_user(user).values_list('pk', flat=True)
            by_project = Evaluation.objects.filter(
                _user_can_access_project_q(user, "project")
            ).values_list('pk', flat=True)
            qs = Evaluation.objects.select_related('author', 'project').filter(
                pk__in=set(by_identity) | set(by_project)
            )

        # Filters
        project_id = request.query_params.get('project')
        if project_id:
            qs = qs.filter(project_id=project_id)

        author_id = request.query_params.get('author')
        if author_id:
            qs = qs.filter(author_id=author_id)

        date_str = request.query_params.get('date')
        if date_str:
            qs = qs.filter(created_at__date=date_str)

        # Only completed evaluations with a score
        qs = qs.filter(status='completed', overall_score__isnull=False)

        # Limit to last 50 evaluations, oldest first (for chart X axis)
        evals = list(qs.order_by('-created_at')[:50])
        evals.reverse()

        # Prefetch findings + skills in bulk
        eval_ids = [e.id for e in evals]
        findings_qs = (
            Finding.objects.filter(evaluation_id__in=eval_ids)
            .select_related('evaluation')
            .prefetch_related('skills')
        )

        # Build per-evaluation skill summary
        eval_findings: dict = {}
        for f in findings_qs:
            eid = f.evaluation_id
            if eid not in eval_findings:
                eval_findings[eid] = []
            eval_findings[eid].append(f)

        result = []
        prev_score = None
        for ev in evals:
            findings = eval_findings.get(ev.id, [])

            # Skill counter
            skill_counts: dict = {}
            severities: dict = {}
            for f in findings:
                sev = (f.severity or 'info').lower()
                severities[sev] = severities.get(sev, 0) + 1
                for sk in f.skills.all():
                    skill_counts[sk.name] = skill_counts.get(sk.name, 0) + 1

            # Top 5 skills
            top_skills = sorted(skill_counts.items(), key=lambda x: -x[1])[:5]

            delta = round(ev.overall_score - prev_score, 1) if prev_score is not None else None

            result.append({
                'id': ev.id,
                'commit_sha': ev.commit_sha,
                'commit_message': ev.commit_message,
                'branch': ev.branch,
                'overall_score': round(ev.overall_score, 1),
                'delta': delta,
                'finding_count': len(findings),
                'fixed_count': sum(1 for f in findings if f.is_fixed),
                'severities': severities,
                'top_skills': [{'name': s[0], 'count': s[1]} for s in top_skills],
                'commit_complexity': ev.commit_complexity,
                'files_changed': ev.files_changed,
                'lines_added': ev.lines_added,
                'lines_removed': ev.lines_removed,
                'created_at': ev.created_at.isoformat(),
                'author_name': ev.author.username if ev.author else ev.author_name,
            })
            prev_score = ev.overall_score

        return Response(result)


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

        # P1-5 / P1-9: Also update SkillMetrics with evaluation overall_score
        # so skills reflect quality, not just issue deductions.
        if author and evaluation.overall_score is not None:
            for skill_slug in set(
                slug
                for fd in data['findings']
                for slug in fd.get('skills_affected', [])
            ):
                try:
                    skill = Skill.objects.get(slug=skill_slug)
                    metric = SkillMetric.objects.filter(
                        user=author, project=project, skill=skill
                    ).first()
                    if metric:
                        metric.update_score(observed_score=evaluation.overall_score)
                except Skill.DoesNotExist:
                    pass

        # ── Learning Algorithm v2: SkillObservations + Bayesian scoring ──
        if author:
            self._create_skill_observations(
                author, project, evaluation, data,
            )
            self._check_learning_proofs(author, evaluation, data)

        # P1-4 / P1-9: Update DeveloperProfile — auto-create if missing
        if author:
            try:
                from skills.level_calculator import compute_level_for_user
                from batch.models import DeveloperProfile
                from django.utils import timezone as tz

                profile, _created = DeveloperProfile.objects.get_or_create(
                    user=author,
                    defaults={
                        'level': 'beginner',
                        'overall_score': 50.0,
                    }
                )

                level_data = compute_level_for_user(author)
                new_score = level_data['composite_score']

                # Append to score_history
                history = list(profile.score_history or [])
                today = tz.now().strftime('%Y-%m-%d')
                if history and history[-1].get('date') == today:
                    history[-1]['score'] = new_score
                else:
                    history.append({'date': today, 'score': new_score})
                history = history[-90:]

                # Update strengths/weaknesses
                metrics = SkillMetric.objects.filter(user=author).select_related('skill').order_by('score')
                weaknesses = [m.skill.id for m in metrics if m.score < 50][:5]
                strengths = [m.skill.id for m in metrics.order_by('-score') if m.score > 75][:5]

                # Update counts
                total_findings = Finding.objects.filter(
                    evaluation__in=Evaluation.objects.for_user(author)
                ).count()

                profile.level = level_data['level']
                profile.overall_score = new_score
                profile.score_history = history
                profile.strengths = strengths
                profile.weaknesses = weaknesses
                profile.total_findings = total_findings
                profile.commits_analyzed = Evaluation.objects.for_user(author).count()
                profile.last_commit_date = tz.now().date()
                profile.trend = profile.calculate_trend()
                profile.save()
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    'Failed to update DeveloperProfile for %s: %s', author.email, e
                )

        # Admin alerts: notify admins if developer score drops significantly
        if author and evaluation.overall_score is not None:
            self._check_admin_alerts(author, evaluation)

        return Response(
            EvaluationSerializer(evaluation).data,
            status=status.HTTP_201_CREATED
        )
    
    @staticmethod
    def _create_skill_observations(author, project, evaluation, data):
        """
        Create SkillObservation records and update Bayesian scores.

        One SkillObservation per skill touched in this evaluation.
        Each observation captures the complexity-weighted quality score.
        """
        try:
            from skills.models import (
                SkillMetric, SkillObservation, Skill,
                COMPLEXITY_WEIGHTS, SEVERITY_WEIGHTS,
            )

            complexity_tier = (evaluation.commit_complexity or '').lower()
            complexity_weight = COMPLEXITY_WEIGHTS.get(complexity_tier, 0.7)

            # Aggregate findings per skill for this evaluation
            skill_findings = {}
            for fd in data['findings']:
                severity = fd.get('severity', 'warning')
                dq = fd.get('decision_quality', 'appropriate')
                for slug in fd.get('skills_affected', []):
                    if slug not in skill_findings:
                        skill_findings[slug] = {
                            'critical': 0, 'warning': 0,
                            'info': 0, 'suggestion': 0,
                            'total': 0,
                            'dq_appropriate': 0,
                            'dq_suboptimal': 0,
                            'dq_poor': 0,
                        }
                    skill_findings[slug][severity] = (
                        skill_findings[slug].get(severity, 0) + 1
                    )
                    skill_findings[slug]['total'] += 1
                    if dq == 'appropriate':
                        skill_findings[slug]['dq_appropriate'] += 1
                    elif dq == 'poor':
                        skill_findings[slug]['dq_poor'] += 1
                    else:
                        skill_findings[slug]['dq_suboptimal'] += 1

            # Also aggregate decision_observations
            for obs in data.get('decision_observations', []):
                dq = obs.get('quality', 'appropriate')
                for slug in obs.get('skills_affected', []):
                    if slug not in skill_findings:
                        skill_findings[slug] = {
                            'critical': 0, 'warning': 0,
                            'info': 0, 'suggestion': 0,
                            'total': 0,
                            'dq_appropriate': 0,
                            'dq_suboptimal': 0,
                            'dq_poor': 0,
                        }
                    if dq == 'appropriate':
                        skill_findings[slug]['dq_appropriate'] += 1
                    elif dq == 'poor':
                        skill_findings[slug]['dq_poor'] += 1
                    else:
                        skill_findings[slug]['dq_suboptimal'] += 1

            lines_changed = (
                (evaluation.lines_added or 0)
                + (evaluation.lines_removed or 0)
            )
            quality_score = evaluation.overall_score or 50.0

            # Prefetch all skills in one query to avoid N+1
            skill_lookup = {
                s.slug: s
                for s in Skill.objects.filter(slug__in=list(skill_findings.keys()))
            }

            for slug, counts in skill_findings.items():
                skill = skill_lookup.get(slug)
                if skill is None:
                    import logging
                    logging.getLogger(__name__).error(
                        'Skill not found for slug %s (user=%s)', slug, author.email,
                    )
                    continue

                obs = SkillObservation.objects.create(
                    user=author,
                    project=project,
                    evaluation=evaluation,
                    skill=skill,
                    commit_sha=evaluation.commit_sha,
                    quality_score=quality_score,
                    complexity_weight=complexity_weight,
                    weighted_score=round(
                        quality_score * complexity_weight, 2
                    ),
                    lines_changed=lines_changed,
                    issue_count=counts['total'],
                    critical_count=counts.get('critical', 0),
                    warning_count=counts.get('warning', 0),
                    info_count=counts.get('info', 0),
                    suggestion_count=counts.get('suggestion', 0),
                    decision_appropriate=counts.get('dq_appropriate', 0),
                    decision_suboptimal=counts.get('dq_suboptimal', 0),
                    decision_poor=counts.get('dq_poor', 0),
                )

                # Update Bayesian score on the SkillMetric
                metric, _ = SkillMetric.objects.get_or_create(
                    user=author, project=project, skill=skill,
                )
                metric.update_bayesian(
                    weighted_score=obs.weighted_score,
                    complexity_weight=complexity_weight,
                )

        except (Skill.DoesNotExist, IntegrityError, ValueError) as e:
            import logging
            logging.getLogger(__name__).error(
                'SkillObservation creation failed for %s: %s',
                author.email, e, exc_info=True,
            )

    @staticmethod
    def _check_learning_proofs(author, evaluation, data):
        """
        Check pending LearningProofs against this evaluation.

        For each PENDING proof:
        - If the same issue_type appears in this commit → RELAPSED
        - If the skill was touched but the issue didn't appear → evidence++
        - If evidence >= threshold → PROVEN
        """
        try:
            from skills.models import LearningProof

            pending_proofs = LearningProof.objects.filter(
                user=author,
                status__in=['pending', 'taught'],
            ).select_related('skill')

            if not pending_proofs.exists():
                return

            # Build set of issue types in this evaluation
            current_issue_types = set()
            current_skills = set()
            for fd in data['findings']:
                severity = fd.get('severity', 'warning')
                for slug in fd.get('skills_affected', []):
                    current_issue_types.add(f"{slug}:{severity}")
                    current_skills.add(slug)

            for proof in pending_proofs:
                skill_slug = proof.skill.slug

                # Check if this commit touches the same skill
                if skill_slug not in current_skills:
                    continue  # Skill not relevant to this commit

                # Check if the same issue type recurred
                if proof.issue_type in current_issue_types:
                    proof.mark_relapsed(evaluation.commit_sha)
                else:
                    # Skill touched, issue didn't appear = potential proof
                    proof.proof_evidence_count += 1
                    if proof.proof_evidence_count >= 2:
                        if proof.status in ('proven', 'reinforced'):
                            # Already proven — reinforce
                            proof.mark_reinforced(evaluation.commit_sha)
                        else:
                            proof.mark_proven(evaluation.commit_sha)
                    else:
                        proof.status = 'pending'
                        proof.save(update_fields=[
                            'proof_evidence_count', 'status', 'updated_at',
                        ])

        except (Skill.DoesNotExist, IntegrityError, ValueError) as e:
            import logging
            logging.getLogger(__name__).error(
                'LearningProof check failed for %s: %s',
                author.email, e, exc_info=True,
            )

    @staticmethod
    def _check_admin_alerts(user, evaluation):
        """Notify admins if developer's score drops significantly."""
        try:
            from notifications.models import Notification

            # Get last 5 evaluations to check for decline
            recent = Evaluation.objects.filter(
                author=user, project=evaluation.project
            ).order_by('-created_at')[:5]

            scores = [e.overall_score for e in recent if e.overall_score is not None]
            if len(scores) < 3:
                return

            # Check if last score is significantly below average of prior scores
            current = scores[0]
            prior_avg = sum(scores[1:]) / len(scores[1:])
            drop = prior_avg - current

            if drop >= 20:
                # Significant drop — alert admins
                admins = User.objects.filter(role='admin')
                for admin in admins:
                    # Don't spam — check if alert was sent recently
                    recent_alert = Notification.objects.filter(
                        user=admin,
                        type='team_update',
                        data__developer_id=user.id,
                        data__alert_type='score_drop',
                    ).order_by('-created_at').first()

                    if recent_alert and (timezone.now() - recent_alert.created_at).days < 1:
                        continue

                    Notification.objects.create(
                        user=admin,
                        type='team_update',
                        title=f'Score Drop: {user.display_name}',
                        message=(
                            f'{user.display_name}\'s score dropped to {current:.0f} '
                            f'(was averaging {prior_avg:.0f}). '
                            f'Check their recent commits.'
                        ),
                        data={
                            'developer_id': user.id,
                            'alert_type': 'score_drop',
                            'current_score': float(current),
                            'prior_avg': float(prior_avg),
                            'drop': float(drop),
                        },
                    )
        except Exception:
            pass

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
        is_admin = getattr(user, 'role', None) in ('admin', 'teacher') or getattr(user, 'is_staff', False)
        queryset = Finding.objects.select_related('evaluation__project')

        if is_admin and user.organization_id:
            queryset = queryset.filter(
                evaluation__project__created_by__organization=user.organization
            )
        else:
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


class ResolvedFindingsView(generics.ListAPIView):
    """List resolved findings with evaluation context."""

    permission_classes = [permissions.IsAuthenticated]

    class ResolvedFindingSerializer(serializers.Serializer):
        id = serializers.IntegerField()
        title = serializers.CharField()
        description = serializers.CharField()
        severity = serializers.CharField()
        file_path = serializers.CharField()
        line_start = serializers.IntegerField()
        original_code = serializers.CharField()
        suggested_code = serializers.CharField()
        explanation = serializers.CharField()
        is_fixed = serializers.BooleanField()
        fixed_at = serializers.DateTimeField()
        fixed_in_commit = serializers.CharField()
        understanding_level = serializers.CharField()
        developer_explanation = serializers.CharField()
        understanding_feedback = serializers.CharField()
        # Evaluation context
        evaluation_id = serializers.IntegerField(source='evaluation.id')
        commit_sha = serializers.CharField(source='evaluation.commit_sha')
        commit_message = serializers.CharField(source='evaluation.commit_message')
        evaluation_date = serializers.DateTimeField(source='evaluation.created_at')
        project_id = serializers.IntegerField(source='evaluation.project_id')
        project_name = serializers.CharField(source='evaluation.project.name')
        author_name = serializers.CharField(source='evaluation.author_name')
        author_email = serializers.CharField(source='evaluation.author_email')

    serializer_class = ResolvedFindingSerializer

    def get_queryset(self):
        user = self.request.user
        is_admin = getattr(user, 'role', None) in ('admin', 'teacher') or getattr(user, 'is_staff', False)
        queryset = Finding.objects.filter(
            is_fixed=True
        ).select_related(
            'evaluation__project'
        )

        if is_admin and user.organization_id:
            queryset = queryset.filter(
                evaluation__project__created_by__organization=user.organization
            )
        else:
            queryset = queryset.filter(
                _user_can_access_project_q(user, "evaluation__project")
                | Q(evaluation__author=user)
            ).distinct()

        queryset = queryset.order_by('-fixed_at')

        project_id = self.request.query_params.get('project')
        if project_id:
            queryset = queryset.filter(evaluation__project_id=project_id)

        user_id = self.request.query_params.get('user')
        if user_id and is_admin:
            queryset = queryset.filter(evaluation__author_id=user_id)

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

        # Require understanding check before marking fixed
        if not finding.understanding_level or finding.understanding_level == 'not_yet':
            return Response(
                {'error': 'Please complete the Fix & Learn check first.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        commit_sha = request.data.get('commit_sha', '')
        finding.mark_fixed(commit_sha)

        # Recalculate DeveloperProfile after fix
        author = finding.evaluation.author if finding.evaluation else None
        if author:
            self._update_developer_profile(author)

        return Response(FindingSerializer(finding).data)

    @staticmethod
    def _update_developer_profile(user):
        """Recalculate DeveloperProfile level, score, and trend after a fix."""
        try:
            from skills.level_calculator import compute_level_for_user
            from batch.models import DeveloperProfile
            from django.utils import timezone

            profile = DeveloperProfile.objects.filter(user=user).first()
            if not profile:
                return

            level_data = compute_level_for_user(user)
            new_score = level_data['composite_score']

            # Append to score_history
            history = list(profile.score_history or [])
            today = timezone.now().strftime('%Y-%m-%d')
            # Update today's entry if it exists, otherwise append
            if history and history[-1].get('date') == today:
                history[-1]['score'] = new_score
            else:
                history.append({'date': today, 'score': new_score})
            # Keep last 90 entries
            history = history[-90:]

            # Update strengths/weaknesses from current skill metrics
            from skills.models import SkillMetric
            metrics = SkillMetric.objects.filter(user=user).select_related('skill').order_by('score')
            weaknesses = [m.skill.id for m in metrics if m.score < 50][:5]
            strengths = [m.skill.id for m in metrics.order_by('-score') if m.score > 75][:5]

            # Update fix count
            from evaluations.models import Finding, Evaluation
            total_fixes = Finding.objects.filter(
                evaluation__in=Evaluation.objects.for_user(user),
                is_fixed=True,
            ).count()

            profile.level = level_data['level']
            profile.overall_score = new_score
            profile.score_history = history
            profile.strengths = strengths
            profile.weaknesses = weaknesses
            profile.total_fixes = total_fixes
            profile.trend = profile.calculate_trend()
            profile.save()
        except Exception:
            pass


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
            import json as _json
            import urllib.request
            from django.conf import settings as django_settings

            fastapi_url = getattr(django_settings, 'FASTAPI_URL', 'http://localhost:8001')
            try:
                payload = _json.dumps({
                    'category': finding.title,
                    'finding_titles': [finding.title],
                    'finding_descriptions': [finding.description],
                    'suggested_fixes': [finding.suggested_code or ''],
                    'developer_explanation': explanation,
                    'developer_level': 'junior',  # TODO: get from profile
                }).encode()
                req = urllib.request.Request(
                    f"{fastapi_url}/api/v1/analyze/understand",
                    data=payload,
                    headers={'Content-Type': 'application/json'},
                    method='POST',
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    llm_result = _json.loads(resp.read())
            except Exception:
                llm_result = {'level': 'partial', 'feedback': 'Evaluation service unavailable.', 'deeper_explanation': ''}

            # Store on finding
            finding.developer_explanation = explanation
            finding.understanding_level = llm_result.get('level', 'partial')
            finding.understanding_feedback = llm_result.get('feedback', '')
            finding.save(update_fields=['developer_explanation', 'understanding_level', 'understanding_feedback'])

            # Auto-mark as fixed when developer demonstrates understanding
            # (got_it or partial = they understood the problem, fix is implied)
            if finding.understanding_level in ('got_it', 'partial') and not finding.is_fixed:
                finding.mark_fixed()

            # ── Learning Algorithm v2: create LearningProof ──
            if finding.understanding_level in ('got_it', 'partial'):
                self._create_learning_proof(finding)

            results.append({
                'finding_id': finding_id,
                'level': finding.understanding_level,
                'feedback': finding.understanding_feedback,
                'deeper_explanation': llm_result.get('deeper_explanation', ''),
            })

        # Recalculate DeveloperProfile after understanding checks
        if results:
            try:
                first_finding = Finding.objects.select_related('evaluation__author').get(
                    pk=results[0]['finding_id']
                )
                author = first_finding.evaluation.author if first_finding.evaluation else None
                if author:
                    MarkFindingFixedView._update_developer_profile(author)
            except Exception:
                pass

        return Response({'results': results})

    @staticmethod
    def _create_learning_proof(finding):
        """
        Create a LearningProof after successful Fix & Learn.

        The proof starts as PENDING — future commits will mark it
        PROVEN or RELAPSED based on whether the issue recurs.
        """
        try:
            from skills.models import LearningProof

            author = finding.evaluation.author
            if not author:
                return

            for fs in finding.finding_skills.select_related('skill').all():
                skill = fs.skill
                severity = finding.severity or 'warning'
                issue_type = f"{skill.slug}:{severity}"

                # Don't create duplicate proofs for the same issue_type
                existing = LearningProof.objects.filter(
                    user=author,
                    skill=skill,
                    issue_type=issue_type,
                    status__in=['pending', 'taught'],
                ).first()
                if existing:
                    continue

                LearningProof.objects.create(
                    user=author,
                    skill=skill,
                    finding=finding,
                    issue_type=issue_type,
                    taught_at=timezone.now(),
                    understanding_level=finding.understanding_level,
                    concept_summary=(
                        finding.explanation or finding.description or ''
                    )[:500],
                    status=LearningProof.Status.PENDING,
                )

                # Small immediate bonus for demonstrating understanding
                from skills.models import SkillMetric, FIX_LEARN_GOT_IT_BONUS, FIX_LEARN_PARTIAL_BONUS
                project = finding.evaluation.project if finding.evaluation else None
                metric = SkillMetric.objects.filter(
                    user=author, skill=skill, project=project,
                ).first()
                if metric:
                    bonus = (
                        FIX_LEARN_GOT_IT_BONUS
                        if finding.understanding_level == 'got_it'
                        else FIX_LEARN_PARTIAL_BONUS
                    )
                    metric.apply_bonus(bonus)

        except (Skill.DoesNotExist, IntegrityError, ValueError) as e:
            import logging
            logging.getLogger(__name__).error(
                'LearningProof creation failed: %s', e, exc_info=True,
            )


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
        is_admin = getattr(user, 'role', None) in ('admin', 'teacher') or getattr(user, 'is_staff', False)

        # Base querysets — org-scoped for admins
        if is_admin and user.organization_id:
            evaluations = Evaluation.objects.filter(
                project__created_by__organization=user.organization
            )
        else:
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
        is_admin = getattr(user, 'role', None) in ('admin', 'teacher') or getattr(user, 'is_staff', False)
        target_user_id = self.request.query_params.get('user')
        if is_admin and target_user_id:
            qs = Pattern.objects.filter(user_id=target_user_id)
            # Org isolation: only show patterns for users in the same org
            if user.organization_id:
                qs = qs.filter(user__organization=user.organization)
        elif is_admin and user.organization_id:
            # Admin with no target user: show all patterns in their org
            qs = Pattern.objects.filter(user__organization=user.organization)
        else:
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
