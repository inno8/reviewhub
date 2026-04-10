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


class ProjectCreateSerializer(serializers.Serializer):
    """Serializer for creating projects (simplified flow)."""
    
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    provider = serializers.ChoiceField(choices=Project.Provider.choices, default='github', required=False)
    repo_url = serializers.URLField(required=False, allow_blank=True, default='')
    repo_owner = serializers.CharField(required=False, allow_blank=True, default='')
    repo_name = serializers.CharField(required=False, allow_blank=True, default='')
    default_branch = serializers.CharField(required=False, default='main')
    team = serializers.PrimaryKeyRelatedField(queryset=Project.objects.none(), required=False, allow_null=True)
    member_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    category_id = serializers.IntegerField(required=False, allow_null=True)
    url = serializers.URLField(required=False, allow_blank=True)
    
    def create(self, validated_data):
        from users.models import User, UserCategory
        
        member_ids = validated_data.pop('member_ids', [])
        category_id = validated_data.pop('category_id', None)
        legacy_url = validated_data.pop('url', '')
        validated_data.pop('team', None)
        
        if legacy_url and not validated_data.get('repo_url'):
            validated_data['repo_url'] = legacy_url
        
        repo_owner = validated_data.get('repo_owner', '') or ''
        repo_name = validated_data.get('repo_name', '') or validated_data['name'].lower().replace(' ', '-')
        
        validated_data['created_by'] = self.context['request'].user
        validated_data['repo_owner'] = repo_owner or self.context['request'].user.username
        validated_data['repo_name'] = repo_name
        
        if not (validated_data.get('repo_url') or '').strip():
            validated_data['repo_url'] = None

        project = Project.objects.create(**validated_data)
        
        # Add creator as owner member
        ProjectMember.objects.create(
            project=project,
            user=self.context['request'].user,
            role='owner'
        )
        
        # Add members from category
        if category_id:
            try:
                category = UserCategory.objects.get(id=category_id)
                for user in category.members.all():
                    if user.id != self.context['request'].user.id:
                        ProjectMember.objects.get_or_create(
                            project=project, user=user,
                            defaults={'role': 'developer'}
                        )
            except UserCategory.DoesNotExist:
                pass
        
        # Add individual members
        for uid in member_ids:
            try:
                user = User.objects.get(id=uid)
                if user.id != self.context['request'].user.id:
                    ProjectMember.objects.get_or_create(
                        project=project, user=user,
                        defaults={'role': 'developer'}
                    )
            except User.DoesNotExist:
                pass
        
        return project


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
