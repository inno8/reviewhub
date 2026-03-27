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
    
    class Meta:
        model = Finding
        fields = [
            'id', 'title', 'description', 'severity',
            'file_path', 'line_start', 'line_end',
            'original_code', 'suggested_code', 'explanation',
            'is_fixed', 'fixed_at', 'fixed_in_commit',
            'skills', 'finding_skills', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


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
    author_email = serializers.EmailField()
    files_changed = serializers.IntegerField()
    lines_added = serializers.IntegerField()
    lines_removed = serializers.IntegerField()
    overall_score = serializers.FloatField()
    llm_model = serializers.CharField(max_length=50)
    llm_tokens_used = serializers.IntegerField()
    processing_ms = serializers.IntegerField()
    findings = serializers.ListField(child=serializers.DictField())


class DashboardSerializer(serializers.Serializer):
    """Dashboard overview data."""
    
    total_evaluations = serializers.IntegerField()
    total_findings = serializers.IntegerField()
    fixed_findings = serializers.IntegerField()
    average_score = serializers.FloatField()
    recent_evaluations = EvaluationListSerializer(many=True)
    skill_summary = serializers.DictField()
