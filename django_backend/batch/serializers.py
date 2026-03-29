"""
Batch Processing Serializers
"""
from rest_framework import serializers
from .models import BatchJob, BatchCommitResult, DeveloperProfile


class BatchJobCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a new batch job."""
    
    class Meta:
        model = BatchJob
        fields = [
            'repo_url', 'branch', 'target_email',
            'max_commits', 'since_date', 'project'
        ]
    
    def validate_repo_url(self, value):
        """Ensure it's a valid GitHub URL."""
        if not value.startswith('https://github.com/'):
            raise serializers.ValidationError(
                "Only GitHub repositories are supported. URL must start with https://github.com/"
            )
        return value


class BatchJobSerializer(serializers.ModelSerializer):
    """Full serializer for batch job details."""
    
    progress_percent = serializers.ReadOnlyField()
    is_running = serializers.ReadOnlyField()
    
    class Meta:
        model = BatchJob
        fields = [
            'id', 'repo_url', 'branch', 'target_email',
            'max_commits', 'since_date', 'project',
            'status', 'total_commits', 'processed_commits',
            'skipped_commits', 'findings_count',
            'skills_detected', 'patterns_detected',
            'error_message', 'progress_percent', 'is_running',
            'created_at', 'started_at', 'completed_at'
        ]
        read_only_fields = [
            'id', 'status', 'total_commits', 'processed_commits',
            'skipped_commits', 'findings_count', 'skills_detected',
            'patterns_detected', 'error_message', 'created_at',
            'started_at', 'completed_at'
        ]


class BatchJobListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing jobs."""
    
    progress_percent = serializers.ReadOnlyField()
    
    class Meta:
        model = BatchJob
        fields = [
            'id', 'repo_url', 'branch', 'status',
            'progress_percent', 'total_commits', 'processed_commits',
            'created_at', 'completed_at'
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
            'analyzed_at'
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
            'score_history', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
