"""
User Models - Custom User with LLM API key support
"""
from django.contrib.auth.models import AbstractUser
from django.db import models
from cryptography.fernet import Fernet
from django.conf import settings
import os


class User(AbstractUser):
    """
    Custom User model with:
    - Email as primary identifier
    - Encrypted LLM API key storage
    - Role-based access
    """
    
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        DEVELOPER = 'developer', 'Developer'
        VIEWER = 'viewer', 'Viewer'
    
    email = models.EmailField(unique=True)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.DEVELOPER
    )
    avatar_url = models.URLField(blank=True, null=True)
    
    # LLM Configuration (encrypted)
    llm_provider = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="openai, anthropic, or empty for OpenClaw fallback"
    )
    _llm_api_key = models.BinaryField(
        blank=True,
        null=True,
        db_column='llm_api_key'
    )
    llm_model = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="e.g., gpt-4-turbo, claude-3-opus"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return self.email
    
    @property
    def _cipher(self):
        """Get Fernet cipher for encryption/decryption."""
        key = os.getenv('ENCRYPTION_KEY')
        if not key:
            # Generate a key if not set (dev only)
            key = Fernet.generate_key()
        return Fernet(key if isinstance(key, bytes) else key.encode())
    
    @property
    def llm_api_key(self):
        """Decrypt and return the LLM API key."""
        if not self._llm_api_key:
            return None
        try:
            return self._cipher.decrypt(bytes(self._llm_api_key)).decode()
        except Exception:
            return None
    
    @llm_api_key.setter
    def llm_api_key(self, value):
        """Encrypt and store the LLM API key."""
        if value:
            self._llm_api_key = self._cipher.encrypt(value.encode())
        else:
            self._llm_api_key = None
    
    @property
    def has_llm_configured(self):
        """Check if user has their own LLM configured."""
        return bool(self.llm_provider and self._llm_api_key)
    
    @property
    def display_name(self):
        """Return display name (full name or username)."""
        if self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        return self.username


class Team(models.Model):
    """Team for grouping users and projects."""
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='owned_teams'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'teams'
    
    def __str__(self):
        return self.name


class TeamMember(models.Model):
    """Team membership with roles."""
    
    class TeamRole(models.TextChoices):
        OWNER = 'owner', 'Owner'
        ADMIN = 'admin', 'Admin'
        MEMBER = 'member', 'Member'
    
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='members'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='team_memberships'
    )
    role = models.CharField(
        max_length=20,
        choices=TeamRole.choices,
        default=TeamRole.MEMBER
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'team_members'
        unique_together = ['team', 'user']
    
    def __str__(self):
        return f"{self.user.email} in {self.team.name}"
