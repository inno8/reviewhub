"""
User Models - Custom User with LLM API key support
"""
import base64
import hashlib
import os

from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


def _get_fernet() -> Fernet:
    """
    Fernet instance for encrypting LLM secrets at rest.

    If ENCRYPTION_KEY is set, it must be a Fernet key string (from Fernet.generate_key()).
    If unset, a deterministic key is derived from SECRET_KEY so encrypt/decrypt match across
    requests and workers (dev-friendly). Without this, each call used generate_key() and
    stored ciphertext could never be decrypted — saved API keys looked \"missing\" on test.
    """
    env_key = (os.getenv("ENCRYPTION_KEY") or "").strip()
    if env_key:
        return Fernet(env_key.encode())
    digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    derived = base64.urlsafe_b64encode(digest)
    return Fernet(derived)


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
    onboard_completed = models.BooleanField(default=False)
    dev_profile_completed = models.BooleanField(default=False)
    dev_profile_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Developer profile questionnaire answers"
    )

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
    _github_personal_access_token = models.BinaryField(
        blank=True,
        null=True,
        db_column='github_personal_access_token',
        help_text="Encrypted GitHub PAT for private repo API access (batch branch list)",
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
        return _get_fernet()
    
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
    def github_personal_access_token(self):
        """Decrypt GitHub PAT (fine-grained or classic) for listing private repo branches."""
        if not self._github_personal_access_token:
            return None
        try:
            return self._cipher.decrypt(bytes(self._github_personal_access_token)).decode()
        except Exception:
            return None

    @github_personal_access_token.setter
    def github_personal_access_token(self, value):
        if value:
            self._github_personal_access_token = self._cipher.encrypt(str(value).encode())
        else:
            self._github_personal_access_token = None

    @property
    def has_github_personal_access_token(self):
        return bool(self._github_personal_access_token)

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

    @property
    def dev_profile_completed(self):
        """True when the developer has submitted the onboarding questionnaire."""
        return hasattr(self, 'dev_profile') and self.dev_profile is not None


class UserDevProfile(models.Model):
    """
    Self-reported developer profile collected during onboarding.
    Feeds SkillMetric initial scores and enriches LLM adaptive prompts.
    """

    class JobRole(models.TextChoices):
        FRONTEND = 'frontend', 'Frontend Developer'
        BACKEND = 'backend', 'Backend Developer'
        FULLSTACK = 'fullstack', 'Full Stack Developer'
        MOBILE = 'mobile', 'Mobile Developer'
        OTHER = 'other', 'Other'

    class FocusFirst(models.TextChoices):
        MAKING_IT_WORK = 'making_it_work', 'Making it work'
        CODE_QUALITY = 'code_quality', 'Code quality'
        PERFORMANCE = 'performance', 'Performance'
        READABILITY = 'readability', 'Readability'

    class TestHabit(models.TextChoices):
        ALWAYS = 'always', 'Always'
        SOMETIMES = 'sometimes', 'Sometimes'
        RARELY = 'rarely', 'Rarely'
        NEVER = 'never', 'Never'

    class EdgeCaseHabit(models.TextChoices):
        ALWAYS = 'always', 'Always'
        SOMETIMES = 'sometimes', 'Sometimes'
        RARELY = 'rarely', 'Rarely'

    class DebuggingApproach(models.TextChoices):
        TRIAL_AND_ERROR = 'trial_and_error', 'Trial and error'
        LOGS_TRACING = 'logs_tracing', 'Logs and tracing'
        STRUCTURED = 'structured', 'Structured debugging'
        STRUGGLE = 'struggle', 'I struggle with debugging'

    class SystemDesign(models.TextChoices):
        YES = 'yes', 'Yes confidently'
        WITH_HELP = 'with_help', 'With help'
        NO = 'no', 'No'

    class EnjoyMost(models.TextChoices):
        FRONTEND_UI = 'frontend_ui', 'Frontend UI'
        BACKEND_LOGIC = 'backend_logic', 'Backend logic'
        SYSTEM_DESIGN = 'system_design', 'System design'
        DEVOPS = 'devops', 'DevOps'
        DATA_AI = 'data_ai', 'Data / AI'

    class WantToImprove(models.TextChoices):
        CLEAN_CODE = 'clean_code', 'Clean code'
        ARCHITECTURE = 'architecture', 'Architecture'
        TESTING = 'testing', 'Testing'
        DEBUGGING = 'debugging', 'Debugging'
        PERFORMANCE = 'performance', 'Performance'

    class CurrentGoal(models.TextChoices):
        GET_JOB = 'get_job', 'Get a job'
        IMPROVE_JOB = 'improve_job', 'Improve at current job'
        BECOME_SENIOR = 'become_senior', 'Become senior'
        LEARN_NEW_TECH = 'learn_new_tech', 'Learn new tech'
        BUILD_STARTUP = 'build_startup', 'Build a startup'

    class LearningStyle(models.TextChoices):
        SHORT_TIPS = 'short_tips', 'Short tips'
        DETAILED = 'detailed', 'Detailed explanations'
        EXAMPLES = 'examples', 'Examples / projects'
        CHALLENGES = 'challenges', 'Challenges'

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='dev_profile',
    )

    # Category 1: Basic Profile
    job_role = models.CharField(max_length=30, choices=JobRole.choices)
    experience_years = models.FloatField()
    primary_language = models.CharField(max_length=50)
    other_languages = models.JSONField(default=list, blank=True)

    # Category 2: Skill Self-Assessment (1-5 scale per skill slug)
    self_scores = models.JSONField(
        default=dict,
        help_text='{"clean_code": 4, "testing": 2, …} — 1 (weak) to 5 (strong)',
    )

    # Category 3: Coding Behavior
    focus_first = models.CharField(max_length=30, choices=FocusFirst.choices, blank=True)
    writes_tests = models.CharField(max_length=20, choices=TestHabit.choices, blank=True)
    edge_case_handling = models.CharField(max_length=20, choices=EdgeCaseHabit.choices, blank=True)
    debugging_approach = models.CharField(max_length=30, choices=DebuggingApproach.choices, blank=True)

    # Category 4: Technical Depth
    can_design_system = models.CharField(max_length=20, choices=SystemDesign.choices, blank=True)
    comfortable_with = models.JSONField(default=list, blank=True)  # [databases, apis, auth, deployment]
    worked_on = models.JSONField(default=list, blank=True)  # [production, personal, opensource]

    # Category 5: Preferences
    enjoy_most = models.CharField(max_length=30, choices=EnjoyMost.choices, blank=True)
    want_to_improve = models.CharField(max_length=30, choices=WantToImprove.choices, blank=True)

    # Category 6: Goals
    current_goal = models.CharField(max_length=30, choices=CurrentGoal.choices, blank=True)
    learning_style = models.CharField(max_length=20, choices=LearningStyle.choices, blank=True)

    # Category 7: Optional code snippets
    proud_code = models.TextField(blank=True)
    struggled_code = models.TextField(blank=True)

    completed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_dev_profiles'

    def __str__(self):
        return f"{self.user.email} — {self.job_role} ({self.experience_years}y)"

    def skill_score_for_metric(self, self_score: int) -> float:
        """Convert 1-5 self-assessment to 0-100 SkillMetric initial score."""
        mapping = {1: 40.0, 2: 55.0, 3: 70.0, 4: 85.0, 5: 100.0}
        return mapping.get(self_score, 55.0)


class GitProviderConnection(models.Model):
    """
    One or more linked Git host identities per user (GitHub / GitLab / Bitbucket).
    Used to match webhook commit author email and push sender username to ReviewHub users.
    """

    class Provider(models.TextChoices):
        GITHUB = 'github', 'GitHub'
        GITLAB = 'gitlab', 'GitLab'
        BITBUCKET = 'bitbucket', 'Bitbucket'

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='git_connections',
    )
    provider = models.CharField(max_length=20, choices=Provider.choices)
    username = models.CharField(
        max_length=100,
        help_text='Login on the host (matches push sender on webhooks)',
    )
    email = models.EmailField(
        blank=True,
        null=True,
        help_text='Optional: git commit author email if different from ReviewHub email',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'git_provider_connections'
        unique_together = [('user', 'provider', 'username')]
        ordering = ['provider', 'username']

    def __str__(self):
        return f'{self.user.email} @ {self.provider}:{self.username}'


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


class UserCategory(models.Model):
    """Group of users (e.g. 'Frontend Interns', 'Backend Team')."""
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_categories'
    )
    members = models.ManyToManyField(
        User,
        related_name='categories',
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_categories'
        unique_together = ['name', 'created_by']
        ordering = ['name']
    
    def __str__(self):
        return self.name


class LLMConfiguration(models.Model):
    """Per-admin multi-provider LLM configuration."""

    class AuthMethod(models.TextChoices):
        API_KEY = 'api_key', 'API key'
        ACCESS_TOKEN = 'access_token', 'Access token'
        OAUTH_GOOGLE = 'oauth_google', 'Google OAuth'

    PROVIDERS = [
        ('openai', 'OpenAI'),
        ('anthropic', 'Anthropic'),
        ('google', 'Google'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='llm_configs')
    provider = models.CharField(max_length=20, choices=PROVIDERS)
    auth_method = models.CharField(
        max_length=20,
        choices=AuthMethod.choices,
        default=AuthMethod.API_KEY,
    )
    # API key, Anthropic long-lived token, or OpenAI Codex-style bearer (when auth_method=api_key or access_token)
    _api_key = models.BinaryField(db_column='api_key', null=True, blank=True)
    model = models.CharField(max_length=80, blank=True)
    is_default = models.BooleanField(default=False)
    _oauth_refresh_token = models.BinaryField(
        db_column='oauth_refresh_token', null=True, blank=True
    )
    _oauth_access_token = models.BinaryField(
        db_column='oauth_access_token', null=True, blank=True
    )
    oauth_expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'llm_configurations'
        unique_together = ['user', 'provider']

    @property
    def _cipher(self):
        return _get_fernet()

    @property
    def api_key(self):
        if not self._api_key:
            return None
        try:
            return self._cipher.decrypt(bytes(self._api_key)).decode()
        except Exception:
            return None

    @api_key.setter
    def api_key(self, value):
        if value:
            self._api_key = self._cipher.encrypt(value.encode())
        else:
            self._api_key = None

    @property
    def oauth_refresh_token(self):
        if not self._oauth_refresh_token:
            return None
        try:
            return self._cipher.decrypt(bytes(self._oauth_refresh_token)).decode()
        except Exception:
            return None

    @oauth_refresh_token.setter
    def oauth_refresh_token(self, value):
        if value:
            self._oauth_refresh_token = self._cipher.encrypt(value.encode())
        else:
            self._oauth_refresh_token = None

    @property
    def oauth_access_token(self):
        if not self._oauth_access_token:
            return None
        try:
            return self._cipher.decrypt(bytes(self._oauth_access_token)).decode()
        except Exception:
            return None

    @oauth_access_token.setter
    def oauth_access_token(self, value):
        if value:
            self._oauth_access_token = self._cipher.encrypt(value.encode())
        else:
            self._oauth_access_token = None

    def clear_oauth_tokens(self):
        self._oauth_refresh_token = None
        self._oauth_access_token = None
        self.oauth_expires_at = None

    def __str__(self):
        return f"{self.user.email} - {self.provider}"


class OnboardCode(models.Model):
    """Temporary OTP codes for first-time user onboarding."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='onboard_codes')
    code = models.CharField(max_length=5)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'onboard_codes'
        indexes = [
            models.Index(fields=['user', 'code']),
        ]

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"OnboardCode for {self.user.email}"
