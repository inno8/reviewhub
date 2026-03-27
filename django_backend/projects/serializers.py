"""
Project Serializers
"""
from rest_framework import serializers
from .models import Project, ProjectMember
from users.serializers import UserSerializer


class ProjectSerializer(serializers.ModelSerializer):
    """Project serializer."""
    
    full_name = serializers.ReadOnlyField()
    webhook_url = serializers.ReadOnlyField()
    created_by = UserSerializer(read_only=True)
    
    class Meta:
        model = Project
        fields = [
            'id', 'name', 'description', 'provider', 'repo_url',
            'repo_owner', 'repo_name', 'default_branch',
            'webhook_active', 'webhook_url', 'full_name',
            'team', 'created_by', 'settings', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'webhook_url', 'created_by', 'created_at', 'updated_at']
        extra_kwargs = {
            'webhook_secret': {'write_only': True}
        }


class ProjectCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating projects."""
    
    class Meta:
        model = Project
        fields = [
            'name', 'description', 'provider', 'repo_url',
            'repo_owner', 'repo_name', 'default_branch', 'team'
        ]
    
    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class ProjectMemberSerializer(serializers.ModelSerializer):
    """Project member serializer."""
    
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = ProjectMember
        fields = ['id', 'user', 'role', 'git_email', 'git_username', 'joined_at']
        read_only_fields = ['id', 'joined_at']


class WebhookInfoSerializer(serializers.Serializer):
    """Webhook setup information."""
    
    webhook_url = serializers.CharField(read_only=True)
    webhook_secret = serializers.CharField(read_only=True)
    provider = serializers.CharField(read_only=True)
    instructions = serializers.CharField(read_only=True)
