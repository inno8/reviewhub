"""
Evaluation Serializers
"""
from rest_framework import serializers
from .models import Evaluation, Finding, FindingSkill, Pattern
from users.serializers import UserSerializer
from skills.serializers import SkillSerializer


class FindingSkillSerializer(serializers.ModelSerializer):
    """Finding-Skill relationship serializer."""
    
    skill = SkillSerializer(read_only=True)
    
    class Meta:
        model = FindingSkill
        fields = ['skill', 'impact_score']


class FindingSerializer(serializers.ModelSerializer):
    """Finding serializer."""

    skills = SkillSerializer(many=True, read_only=True)
    finding_skills = FindingSkillSerializer(many=True, read_only=True)
    difficulty = serializers.SerializerMethodField()

    class Meta:
        model = Finding
        fields = [
            'id', 'title', 'description', 'severity', 'difficulty',
            'file_path', 'line_start', 'line_end',
            'original_code', 'suggested_code', 'explanation',
            'is_fixed', 'fixed_at', 'fixed_in_commit',
            'developer_explanation', 'understanding_level', 'understanding_feedback',
            'skills', 'finding_skills', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def get_difficulty(self, obj):
        """Compute difficulty: quick_fix / moderate / deep_dive based on severity and code size."""
        sev = (obj.severity or '').lower()
        code_lines = len((obj.original_code or '').split('\n'))

        if sev == 'suggestion' or (sev == 'info' and code_lines <= 3):
            return 'quick_fix'
        elif sev == 'critical' or code_lines > 15:
            return 'deep_dive'
        return 'moderate'


class EvaluationSerializer(serializers.ModelSerializer):
    """Evaluation serializer."""
    
    author = UserSerializer(read_only=True)
    findings = FindingSerializer(many=True, read_only=True)
    finding_count = serializers.ReadOnlyField()
    critical_count = serializers.ReadOnlyField()
    warning_count = serializers.ReadOnlyField()
    
    class Meta:
        model = Evaluation
        fields = [
            'id', 'project', 'author', 'commit_sha', 'commit_message',
            'commit_timestamp', 'branch', 'author_name', 'author_email',
            'files_changed', 'lines_added', 'lines_removed', 'overall_score',
            'status', 'llm_model', 'llm_tokens_used', 'processing_ms',
            'findings', 'finding_count', 'critical_count', 'warning_count',
            'commit_complexity', 'complexity_score',
            'created_at', 'evaluated_at'
        ]
        read_only_fields = ['id', 'created_at', 'evaluated_at']


class EvaluationListSerializer(serializers.ModelSerializer):
    """Lightweight evaluation serializer for lists."""
    
    author = UserSerializer(read_only=True)
    finding_count = serializers.ReadOnlyField()
    
    class Meta:
        model = Evaluation
        fields = [
            'id', 'project', 'author', 'commit_sha', 'commit_message',
            'branch', 'overall_score', 'status', 'finding_count',
            'commit_complexity', 'complexity_score',
            'created_at'
        ]


class InternalEvaluationCreateSerializer(serializers.Serializer):
    """Serializer for creating evaluation from FastAPI."""
    
    project_id = serializers.IntegerField()
    commit_sha = serializers.CharField(max_length=40)
    commit_message = serializers.CharField()
    commit_timestamp = serializers.DateTimeField(required=False, allow_null=True)
    branch = serializers.CharField(max_length=100)
    author_name = serializers.CharField(max_length=100)
    # Git commit author emails can be blank or non-standard (noreply, local hostnames, etc.)
    author_email = serializers.CharField(max_length=255, allow_blank=True)
    files_changed = serializers.IntegerField()
    lines_added = serializers.IntegerField()
    lines_removed = serializers.IntegerField()
    overall_score = serializers.FloatField(allow_null=True, required=False)
    llm_model = serializers.CharField(max_length=50)
    llm_tokens_used = serializers.IntegerField()
    processing_ms = serializers.IntegerField()
    findings = serializers.ListField(child=serializers.DictField())
    commit_complexity = serializers.CharField(max_length=10, required=False, allow_blank=True, default="")
    complexity_score = serializers.FloatField(required=False, allow_null=True, default=None)
    sender_login = serializers.CharField(required=False, allow_blank=True, default="")
    batch_job_id = serializers.IntegerField(required=False, allow_null=True)


class DashboardSerializer(serializers.Serializer):
    """Dashboard overview data."""
    
    total_evaluations = serializers.IntegerField()
    total_findings = serializers.IntegerField()
    fixed_findings = serializers.IntegerField()
    average_score = serializers.FloatField()
    recent_evaluations = EvaluationListSerializer(many=True)
    skill_summary = serializers.DictField()


class PatternSerializer(serializers.ModelSerializer):
    """Public serializer for a developer's repeated issue patterns."""

    class Meta:
        model = Pattern
        fields = [
            'id', 'pattern_type', 'pattern_key',
            'frequency', 'first_seen', 'last_seen', 'is_resolved',
        ]
        read_only_fields = ['id', 'first_seen', 'last_seen']
