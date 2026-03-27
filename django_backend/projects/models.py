"""
Project Models - Repository tracking and webhook management
"""
from django.db import models
from django.conf import settings
import secrets


def generate_webhook_secret():
    """Generate a secure webhook secret."""
    return secrets.token_urlsafe(32)


class Project(models.Model):
    """
    Project represents a Git repository being monitored.
    """
    
    class Provider(models.TextChoices):
        GITHUB = 'github', 'GitHub'
        GITLAB = 'gitlab', 'GitLab'
        BITBUCKET = 'bitbucket', 'Bitbucket'
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Repository info
    provider = models.CharField(
        max_length=20,
        choices=Provider.choices,
        default=Provider.GITHUB
    )
    repo_url = models.URLField(help_text="Full repository URL")
    repo_owner = models.CharField(max_length=100, help_text="Owner/organization name")
    repo_name = models.CharField(max_length=100, help_text="Repository name")
    default_branch = models.CharField(max_length=100, default='main')
    
    # Webhook
    webhook_secret = models.CharField(
        max_length=64,
        default=generate_webhook_secret
    )
    webhook_active = models.BooleanField(default=False)
    
    # Ownership
    team = models.ForeignKey(
        'users.Team',
        on_delete=models.CASCADE,
        related_name='projects',
        null=True,
        blank=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_projects'
    )
    
    # Settings (JSON)
    settings = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'projects'
        unique_together = ['provider', 'repo_owner', 'repo_name']
    
    def __str__(self):
        return f"{self.repo_owner}/{self.repo_name}"
    
    @property
    def full_name(self):
        return f"{self.repo_owner}/{self.repo_name}"
    
    @property
    def webhook_url(self):
        """Generate the webhook URL for this project."""
        # Will be set based on deployment URL
        base_url = settings.FASTAPI_URL.rstrip('/')
        return f"{base_url}/api/v1/webhook/{self.provider}/{self.id}"
    
    def regenerate_webhook_secret(self):
        """Generate a new webhook secret."""
        self.webhook_secret = generate_webhook_secret()
        self.save(update_fields=['webhook_secret'])
        return self.webhook_secret


class ProjectMember(models.Model):
    """
    Project membership - maps users to projects with roles.
    Allows tracking individual developer progress per project.
    """
    
    class ProjectRole(models.TextChoices):
        OWNER = 'owner', 'Owner'
        MAINTAINER = 'maintainer', 'Maintainer'
        DEVELOPER = 'developer', 'Developer'
        VIEWER = 'viewer', 'Viewer'
    
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='members'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='project_memberships'
    )
    role = models.CharField(
        max_length=20,
        choices=ProjectRole.choices,
        default=ProjectRole.DEVELOPER
    )
    
    # Git identity (for matching commits)
    git_email = models.EmailField(
        blank=True,
        null=True,
        help_text="Git commit email (if different from user email)"
    )
    git_username = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Git username (if different from user)"
    )
    
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'project_members'
        unique_together = ['project', 'user']
    
    def __str__(self):
        return f"{self.user.email} in {self.project.name}"
