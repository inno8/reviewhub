"""
Skills Serializers
"""
from rest_framework import serializers
from .models import SkillCategory, Skill, SkillMetric


class SkillSerializer(serializers.ModelSerializer):
    """Skill serializer."""
    
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = Skill
        fields = ['id', 'name', 'slug', 'description', 'weight', 'category', 'category_name', 'order']


class SkillCategorySerializer(serializers.ModelSerializer):
    """Skill category serializer."""
    
    skills = SkillSerializer(many=True, read_only=True)
    
    class Meta:
        model = SkillCategory
        fields = ['id', 'name', 'slug', 'description', 'icon', 'color', 'order', 'skills']


class SkillMetricSerializer(serializers.ModelSerializer):
    """Skill metric serializer."""

    skill = SkillSerializer(read_only=True)
    fix_rate = serializers.ReadOnlyField()
    display_score = serializers.ReadOnlyField()
    confidence_label = serializers.ReadOnlyField()
    level_label = serializers.ReadOnlyField()

    class Meta:
        model = SkillMetric
        fields = [
            'id', 'skill', 'score', 'bayesian_score', 'confidence',
            'display_score', 'confidence_label', 'level_label',
            'observation_count', 'proven_concepts', 'relapsed_concepts',
            'issue_count', 'fixed_count',
            'fix_rate', 'trend', 'previous_score',
            'first_evaluated_at', 'last_evaluated_at',
        ]


class SkillTrendDataSerializer(serializers.Serializer):
    """Skill trend data point."""
    
    date = serializers.DateField()
    score = serializers.FloatField()
    issue_count = serializers.IntegerField()


class SkillTrendSerializer(serializers.Serializer):
    """Skill trends over time."""
    
    skill_slug = serializers.CharField()
    skill_name = serializers.CharField()
    current_score = serializers.FloatField()
    trend = serializers.CharField()
    data_points = SkillTrendDataSerializer(many=True)
