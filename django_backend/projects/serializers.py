"""
Project Serializers
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Project, ProjectMember

User = get_user_model()


class ProjectSerializer(serializers.ModelSerializer):
    """Project serializer."""
    
    full_name = serializers.ReadOnlyField()
    webhook_url = serializers.ReadOnlyField()
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)
    member_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Project
        fields = [
            'id', 'name', 'description', 'provider', 'repo_url',
            'repo_owner', 'repo_name', 'default_branch',
            'webhook_active', 'webhook_url', 'full_name',
            'team', 'created_by', 'created_by_email', 'member_count',
            'settings', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'webhook_url', 'created_by', 'created_at', 'updated_at']
        extra_kwargs = {
            'webhook_secret': {'write_only': True}
        }
    
    def get_member_count(self, obj):
        return obj.members.count()


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
    
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.display_name', read_only=True)
    
    class Meta:
        model = ProjectMember
        fields = ['id', 'user', 'user_email', 'user_name', 'role', 'git_email', 'git_username', 'joined_at']
        read_only_fields = ['id', 'user', 'joined_at']


class InviteMemberSerializer(serializers.Serializer):
    """Serializer for inviting a member by email."""
    
    email = serializers.EmailField(required=True)
    role = serializers.ChoiceField(
        choices=ProjectMember.ProjectRole.choices,
        default=ProjectMember.ProjectRole.DEVELOPER
    )
    git_email = serializers.EmailField(required=False, allow_blank=True)
    git_username = serializers.CharField(required=False, allow_blank=True)
    
    def validate_email(self, value):
        """Check if user exists."""
        try:
            User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist.")
        return value


class UpdateMemberRoleSerializer(serializers.Serializer):
    """Serializer for updating member role."""
    
    role = serializers.ChoiceField(
        choices=ProjectMember.ProjectRole.choices,
        required=True
    )


class WebhookInfoSerializer(serializers.Serializer):
    """Webhook setup information."""
    
    webhook_url = serializers.CharField(read_only=True)
    webhook_secret = serializers.CharField(read_only=True)
    provider = serializers.CharField(read_only=True)
    instructions = serializers.CharField(read_only=True)
