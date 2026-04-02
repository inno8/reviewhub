"""
User Serializers
"""
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User, Team, TeamMember, UserCategory, GitProviderConnection, UserDevProfile


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT serializer that uses email as username."""
    
    username_field = User.USERNAME_FIELD


class UserSerializer(serializers.ModelSerializer):
    """User serializer for API responses."""

    display_name = serializers.ReadOnlyField()
    has_llm_configured = serializers.ReadOnlyField()
    dev_profile_completed = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name',
            'display_name', 'role', 'avatar_url', 'has_llm_configured',
            'llm_provider', 'llm_model', 'dev_profile_completed',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class UserDevProfileSerializer(serializers.ModelSerializer):
    """Read/write serializer for the developer onboarding questionnaire."""

    class Meta:
        model = UserDevProfile
        fields = [
            'job_role', 'experience_years', 'primary_language', 'other_languages',
            'self_scores',
            'focus_first', 'writes_tests', 'edge_case_handling', 'debugging_approach',
            'can_design_system', 'comfortable_with', 'worked_on',
            'enjoy_most', 'want_to_improve',
            'current_goal', 'learning_style',
            'proud_code', 'struggled_code',
            'completed_at', 'updated_at',
        ]
        read_only_fields = ['completed_at', 'updated_at']


class GitProviderConnectionSerializer(serializers.ModelSerializer):
    """Linked Git host identity (multiple per user)."""

    class Meta:
        model = GitProviderConnection
        fields = ['id', 'provider', 'username', 'email', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_username(self, value):
        v = (value or '').strip()
        if not v:
            raise serializers.ValidationError('Username is required.')
        return v[:100]

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""
    
    password = serializers.CharField(
        write_only=True, 
        min_length=8,
        style={'input_type': 'password'}
    )
    
    class Meta:
        model = User
        fields = ['email', 'username', 'password', 'first_name', 'last_name']
    
    def create(self, validated_data):
        """Create user with hashed password."""
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for password change endpoint."""
    
    old_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )
    new_password = serializers.CharField(
        required=True,
        min_length=8,
        write_only=True,
        style={'input_type': 'password'}
    )
    confirm_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )
    
    def validate(self, data):
        """Validate that new passwords match."""
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({
                'confirm_password': 'New passwords must match.'
            })
        return data


class UserLLMConfigSerializer(serializers.Serializer):
    """Serializer for updating LLM configuration."""
    
    llm_provider = serializers.ChoiceField(
        choices=['openai', 'anthropic'],
        required=False,
        allow_null=True
    )
    llm_api_key = serializers.CharField(required=False, allow_blank=True)
    llm_model = serializers.CharField(required=False, allow_blank=True)


class UserCategorySerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()
    member_ids = serializers.PrimaryKeyRelatedField(
        source='members', many=True, queryset=User.objects.all(), required=False
    )
    
    class Meta:
        model = UserCategory
        fields = ['id', 'name', 'description', 'member_count', 'member_ids', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_member_count(self, obj):
        return obj.members.count()
    
    def create(self, validated_data):
        members = validated_data.pop('members', [])
        validated_data['created_by'] = self.context['request'].user
        category = UserCategory.objects.create(**validated_data)
        if members:
            category.members.set(members)
        return category
    
    def update(self, instance, validated_data):
        members = validated_data.pop('members', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if members is not None:
            instance.members.set(members)
        return instance


class UserCategoryDetailSerializer(UserCategorySerializer):
    members = UserSerializer(many=True, read_only=True)
    
    class Meta(UserCategorySerializer.Meta):
        fields = UserCategorySerializer.Meta.fields + ['members']


class TeamSerializer(serializers.ModelSerializer):
    """Team serializer."""
    
    owner = UserSerializer(read_only=True)
    member_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Team
        fields = ['id', 'name', 'description', 'owner', 'member_count', 'created_at']
        read_only_fields = ['id', 'owner', 'created_at']
    
    def get_member_count(self, obj):
        return obj.members.count()


class TeamMemberSerializer(serializers.ModelSerializer):
    """Team member serializer."""
    
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = TeamMember
        fields = ['id', 'user', 'role', 'joined_at']
        read_only_fields = ['id', 'joined_at']
