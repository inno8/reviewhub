"""
Batch Processing Serializers
"""
import requests
from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import serializers

from projects.models import Project

from .models import BatchJob, BatchCommitResult, DeveloperProfile


class BatchJobCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a new batch job."""

    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.none())

    class Meta:
        model = BatchJob
        fields = [
            'repo_url', 'branch', 'target_github_username',
            'max_commits', 'since_date', 'project',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        qs = Project.objects.all()
        if request and request.user.is_authenticated:
            u = request.user
            if u.role != 'admin' and not getattr(u, 'is_staff', False):
                qs = Project.objects.filter(
                    Q(created_by=u)
                    | Q(members__user=u)
                    | Q(team__members__user=u)
                ).distinct()
        self.fields['project'].queryset = qs

    def validate_project(self, project):
        if (project.repo_url or '').strip():
            raise serializers.ValidationError(
                'This project already has a repository linked. '
                'Choose a project without a repo (or create a new one).'
            )
        return project

    def validate_repo_url(self, value):
        """Ensure it's a valid GitHub URL."""
        if not value.startswith('https://github.com/'):
            raise serializers.ValidationError(
                "Only GitHub repositories are supported. URL must start with https://github.com/"
            )
        return value

    def validate(self, attrs):
        from .github_branches import list_active_branches

        repo_url = attrs.get('repo_url')
        branch = (attrs.get('branch') or '').strip()
        author = (attrs.get('target_github_username') or '').strip()
        if not branch:
            raise serializers.ValidationError({'branch': 'Select a branch or "All branches".'})
        user = self.context['request'].user
        u = get_user_model().objects.get(pk=user.pk)
        pat = u.github_personal_access_token
        try:
            active = list_active_branches(
                repo_url,
                author=author or None,
                user_token=pat,
            )
        except ValueError as e:
            raise serializers.ValidationError({'repo_url': str(e)}) from e
        except requests.RequestException as e:
            raise serializers.ValidationError(
                {'repo_url': f'Could not reach GitHub: {e}'}
            ) from e
        if not active:
            raise serializers.ValidationError({
                'branch': 'No branches match this repository/author. Check the URL, token, or author username.'
            })

        BRANCH_ALL = '__all__'
        if branch == BRANCH_ALL:
            attrs['_resolved_branches'] = active
        else:
            if branch not in active:
                raise serializers.ValidationError({
                    'branch': f'Branch "{branch}" is not in the current active list. Refresh branches and try again.'
                })
            attrs['_resolved_branches'] = [branch]
        return attrs

    def create(self, validated_data):
        resolved = validated_data.pop('_resolved_branches')
        job = super().create(validated_data)
        job.resolved_branches = resolved
        job.save(update_fields=['resolved_branches'])
        return job


class BatchJobSerializer(serializers.ModelSerializer):
    """Full serializer for batch job details."""

    progress_percent = serializers.ReadOnlyField()
    is_running = serializers.ReadOnlyField()

    class Meta:
        model = BatchJob
        fields = [
            'id', 'repo_url', 'branch', 'resolved_branches', 'target_github_username',
            'max_commits', 'since_date', 'project',
            'status', 'total_commits', 'processed_commits',
            'skipped_commits', 'findings_count',
            'skills_detected', 'patterns_detected',
            'error_message', 'progress_percent', 'is_running',
            'created_at', 'started_at', 'completed_at',
        ]
        read_only_fields = [
            'id', 'resolved_branches', 'status', 'total_commits', 'processed_commits',
            'skipped_commits', 'findings_count', 'skills_detected',
            'patterns_detected', 'error_message', 'created_at',
            'started_at', 'completed_at',
        ]


class BatchJobListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing jobs."""

    progress_percent = serializers.ReadOnlyField()

    class Meta:
        model = BatchJob
        fields = [
            'id', 'repo_url', 'branch', 'status', 'target_github_username',
            'progress_percent', 'total_commits', 'processed_commits',
            'skipped_commits', 'findings_count', 'project', 'error_message',
            'created_at', 'completed_at',
        ]


class BatchCommitResultSerializer(serializers.ModelSerializer):
    """Serializer for commit analysis results."""

    class Meta:
        model = BatchCommitResult
        fields = [
            'id', 'commit_sha', 'commit_message', 'commit_date',
            'author_name', 'author_email',
            'files_changed', 'lines_added', 'lines_removed',
            'overall_score', 'findings_count',
            'skills_snapshot', 'patterns_snapshot',
            'analyzed_at',
        ]


class DeveloperProfileSerializer(serializers.ModelSerializer):
    """Serializer for developer profile."""

    user_email = serializers.CharField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = DeveloperProfile
        fields = [
            'id', 'user_email', 'user_name',
            'level', 'overall_score', 'trend',
            'strengths', 'weaknesses',
            'top_patterns', 'resolved_patterns',
            'commits_analyzed', 'total_findings', 'total_fixes',
            'first_commit_date', 'last_commit_date',
            'score_history', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
