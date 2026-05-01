"""
Evaluation Models - Code reviews, findings, and patterns
"""
from django.db import models
from django.db.models import Q
from django.conf import settings


class EvaluationQuerySet(models.QuerySet):
    """Query helpers for evaluations visible in dashboards and insights."""

    def for_user(self, user):
        """
        Evaluations tied to this account. Matches:
          1. author FK set to this user.
          2. author is null AND author_email matches any of:
             - user.email
             - GitProviderConnection.email (git commit email)
             - GitProviderConnection.username (push sender stored as email)
             - ProjectMember.git_email
             - ProjectMember.git_username
        This covers the common case where webhook/batch stores a git username
        (e.g. "assignon") in author_email instead of a real email address.
        """
        if user is None:
            return self.none()

        # Collect all identifiers this user is known by
        identifiers: set[str] = set()
        login_email = (getattr(user, 'email', None) or '').strip().lower()
        if login_email:
            identifiers.add(login_email)

        # Git provider connections (email + username)
        from users.models import GitProviderConnection
        for conn in GitProviderConnection.objects.filter(user=user):
            if conn.email:
                identifiers.add(conn.email.strip().lower())
            if conn.username:
                identifiers.add(conn.username.strip().lower().lstrip('@'))

        # Project member git identifiers
        from projects.models import ProjectMember
        for pm in ProjectMember.objects.filter(user=user):
            if getattr(pm, 'git_email', None):
                identifiers.add(pm.git_email.strip().lower())
            if getattr(pm, 'git_username', None):
                identifiers.add(pm.git_username.strip().lower().lstrip('@'))

        q = Q(author=user)
        if identifiers:
            q |= Q(author__isnull=True, author_email__in=identifiers)
            # Also case-insensitive match in case DB is case-sensitive
            for ident in list(identifiers):
                q |= Q(author__isnull=True, author_email__iexact=ident)

        return self.filter(q).distinct()


class Evaluation(models.Model):
    """
    Evaluation represents a code review session for a commit.
    Created by FastAPI AI Engine after analyzing a push.
    """
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
    
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='evaluations'
    )
    batch_job = models.ForeignKey(
        'batch.BatchJob',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='evaluations',
        help_text="Set when this evaluation was produced by a batch run",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='evaluations',
        help_text="Matched user (if found)"
    )
    
    # Git info
    commit_sha = models.CharField(max_length=40)
    commit_message = models.TextField(blank=True)
    commit_timestamp = models.DateTimeField(null=True, blank=True)
    branch = models.CharField(max_length=100)
    
    # Author info (from git, used for matching)
    author_name = models.CharField(max_length=100)
    author_email = models.CharField(max_length=255, blank=True)
    
    # Stats
    files_changed = models.PositiveIntegerField(default=0)
    lines_added = models.PositiveIntegerField(default=0)
    lines_removed = models.PositiveIntegerField(default=0)
    overall_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Overall code quality score (0-100)"
    )
    
    # Processing info
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    llm_model = models.CharField(
        max_length=50,
        blank=True,
        help_text="Model used for evaluation"
    )
    llm_tokens_used = models.PositiveIntegerField(default=0)
    processing_ms = models.PositiveIntegerField(
        default=0,
        help_text="Processing time in milliseconds"
    )
    error_message = models.TextField(blank=True)
    commit_complexity = models.CharField(
        max_length=10,
        blank=True,
        help_text="Commit complexity tier: simple | medium | complex"
    )
    complexity_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Raw heuristic score from CommitClassifier"
    )
    prompt_version = models.CharField(
        max_length=32,
        blank=True,
        help_text="Hash/version of the LLM prompt used for this evaluation"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    evaluated_at = models.DateTimeField(null=True, blank=True)

    objects = EvaluationQuerySet.as_manager()
    
    class Meta:
        db_table = 'evaluations'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['project', 'created_at']),
            models.Index(fields=['commit_sha']),
            models.Index(fields=['author_email']),
        ]
    
    def __str__(self):
        return f"{self.project.name} - {self.commit_sha[:7]}"
    
    @property
    def finding_count(self):
        return self.findings.count()
    
    @property
    def critical_count(self):
        return self.findings.filter(severity=Finding.Severity.CRITICAL).count()
    
    @property
    def warning_count(self):
        return self.findings.filter(severity=Finding.Severity.WARNING).count()


class Finding(models.Model):
    """
    Individual code issue found during evaluation.
    """
    
    class Severity(models.TextChoices):
        CRITICAL = 'critical', 'Critical'
        WARNING = 'warning', 'Warning'
        INFO = 'info', 'Info'
        SUGGESTION = 'suggestion', 'Suggestion'
    
    evaluation = models.ForeignKey(
        Evaluation,
        on_delete=models.CASCADE,
        related_name='findings'
    )
    
    # Issue details
    title = models.CharField(max_length=200)
    description = models.TextField()
    severity = models.CharField(
        max_length=20,
        choices=Severity.choices,
        default=Severity.WARNING
    )
    
    # Location
    file_path = models.CharField(max_length=500)
    line_start = models.PositiveIntegerField()
    line_end = models.PositiveIntegerField()
    
    # Code
    original_code = models.TextField(help_text="The problematic code")
    suggested_code = models.TextField(
        blank=True,
        help_text="Suggested fix"
    )
    explanation = models.TextField(
        blank=True,
        help_text="Why this is better"
    )
    
    # Fix tracking
    is_fixed = models.BooleanField(default=False)
    fixed_at = models.DateTimeField(null=True, blank=True)
    fixed_in_commit = models.CharField(max_length=40, blank=True)

    # Fix & Learn — developer understanding
    developer_explanation = models.TextField(
        blank=True,
        help_text="Developer's explanation of why the original code was wrong"
    )
    understanding_level = models.CharField(
        max_length=20,
        blank=True,
        choices=[('got_it', 'Got It'), ('partial', 'Partial'), ('not_yet', 'Not Yet')],
        help_text="LLM-assessed understanding level"
    )
    understanding_feedback = models.TextField(
        blank=True,
        help_text="LLM feedback on the developer's explanation"
    )

    # Skills (many-to-many via FindingSkill)
    skills = models.ManyToManyField(
        'skills.Skill',
        through='FindingSkill',
        related_name='findings'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'findings'
        ordering = ['-evaluation__created_at', '-severity']
    
    def __str__(self):
        return f"{self.title} ({self.file_path}:{self.line_start})"
    
    def mark_fixed(self, commit_sha: str = None):
        """Mark finding as fixed."""
        from django.utils import timezone
        
        self.is_fixed = True
        self.fixed_at = timezone.now()
        if commit_sha:
            self.fixed_in_commit = commit_sha
        self.save()
        
        # Update skill metrics — improve score on fix
        for finding_skill in self.finding_skills.all():
            metric = finding_skill.skill.metrics.filter(
                user=self.evaluation.author,
                project=self.evaluation.project
            ).first()
            if metric:
                metric.improve_score(
                    fixed_issues=1,
                    recovery=finding_skill.impact_score * 0.6,  # recover 60% of the deduction
                )


class FindingSkill(models.Model):
    """
    Maps findings to skills with impact score.
    """
    
    finding = models.ForeignKey(
        Finding,
        on_delete=models.CASCADE,
        related_name='finding_skills'
    )
    skill = models.ForeignKey(
        'skills.Skill',
        on_delete=models.CASCADE,
        related_name='finding_skills'
    )
    impact_score = models.FloatField(
        default=5.0,
        help_text="Points deducted from skill score"
    )
    
    class Meta:
        db_table = 'finding_skills'
        unique_together = ['finding', 'skill']
    
    def __str__(self):
        return f"{self.finding.title} -> {self.skill.name}"


class Pattern(models.Model):
    """
    Recurring issue pattern for a user.
    Used for generating personalized learning recommendations.
    """
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='patterns'
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='patterns',
        null=True,
        blank=True,
        help_text="Optional: project-specific pattern"
    )
    
    # Pattern identification
    pattern_type = models.CharField(
        max_length=100,
        help_text="Type of recurring issue"
    )
    pattern_key = models.CharField(
        max_length=200,
        help_text="Unique key for this pattern"
    )
    
    # Tracking
    frequency = models.PositiveIntegerField(
        default=1,
        help_text="Number of occurrences"
    )
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    
    # Resolution
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Sample findings (for context)
    sample_findings = models.ManyToManyField(
        Finding,
        related_name='patterns',
        blank=True
    )
    
    class Meta:
        db_table = 'patterns'
        unique_together = ['user', 'project', 'pattern_key']
    
    def __str__(self):
        return f"{self.pattern_type} ({self.frequency}x)"
    
    def increment(self, finding: Finding = None):
        """Increment pattern frequency."""
        from django.utils import timezone
        
        self.frequency += 1
        self.last_seen = timezone.now()
        if finding:
            self.sample_findings.add(finding)
        self.save()
    
    def apply_decay(self, decay_rate: float = 0.9, min_frequency: int = 1):
        """
        Reduce frequency over time. Called periodically (e.g. weekly).
        Patterns that decay below min_frequency are marked resolved.
        """
        from django.utils import timezone
        
        self.frequency = max(min_frequency, int(self.frequency * decay_rate))
        if self.frequency <= min_frequency:
            self.is_resolved = True
            self.resolved_at = timezone.now()
        self.save()
    
    @classmethod
    def apply_global_decay(cls, decay_rate: float = 0.9):
        """Apply decay to all active (unresolved) patterns."""
        from django.utils import timezone
        
        active = cls.objects.filter(is_resolved=False)
        for pattern in active:
            pattern.apply_decay(decay_rate)


class DeterministicFinding(models.Model):
    """
    Layer 1 shadow-mode finding produced by a deterministic runner
    (ruff, ESLint, etc.). Kept SEPARATE from Finding so teachers never
    see these until we've validated hit-rate against the LLM.

    Scope B2 of Nakijken Copilot v1 — hybrid architecture Layer 1.
    Purely additive, not surfaced in any teacher-facing API yet.
    """

    class Severity(models.TextChoices):
        CRITICAL = 'critical', 'Critical'
        WARNING = 'warning', 'Warning'
        INFO = 'info', 'Info'
        SUGGESTION = 'suggestion', 'Suggestion'

    class Runner(models.TextChoices):
        RUFF = 'ruff', 'ruff (Python)'
        ESLINT = 'eslint', 'ESLint (JS/TS)'
        # Added v1.1 (May 2 2026): PHP is the most-used MBO-4 ICT stack.
        # ai_engine has shipped phpcs (PSR-12) + phpstan (level 5) runners
        # for a while; before this enum entry their findings were silently
        # dropped at the Django serializer because runner='phpcs' wasn't
        # valid. v1.1 task F4.
        PHPCS = 'phpcs', 'phpcs (PHP / PSR-12)'
        PHPSTAN = 'phpstan', 'phpstan (PHP)'

    evaluation = models.ForeignKey(
        Evaluation,
        on_delete=models.CASCADE,
        related_name='deterministic_findings',
    )
    runner = models.CharField(
        max_length=20,
        choices=Runner.choices,
        help_text="Which deterministic runner produced this finding.",
    )
    rule_id = models.CharField(
        max_length=64,
        help_text="Runner-native rule id, e.g. 'E501', 'no-unused-vars'.",
    )
    message = models.TextField()
    severity = models.CharField(
        max_length=20,
        choices=Severity.choices,
        default=Severity.WARNING,
    )
    file_path = models.CharField(max_length=500)
    line_start = models.PositiveIntegerField()
    line_end = models.PositiveIntegerField()
    # Cross-reference: if the LLM also surfaced a matching finding, we can
    # measure Layer 1 overlap. Nullable — shadow mode starts uncorrelated.
    matched_llm_finding = models.ForeignKey(
        Finding,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matched_deterministic_findings',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'deterministic_findings'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['evaluation', 'runner']),
            models.Index(fields=['runner', 'rule_id']),
        ]

    def __str__(self):
        return f"[{self.runner}] {self.rule_id} {self.file_path}:{self.line_start}"


class LearningRecommendation(models.Model):
    """
    Learning resource recommendations based on patterns.
    """
    
    class ResourceType(models.TextChoices):
        ARTICLE = 'article', 'Article'
        VIDEO = 'video', 'Video'
        BOOK = 'book', 'Book'
        COURSE = 'course', 'Course'
        DOCUMENTATION = 'documentation', 'Documentation'
    
    class Difficulty(models.TextChoices):
        BEGINNER = 'beginner', 'Beginner'
        INTERMEDIATE = 'intermediate', 'Intermediate'
        ADVANCED = 'advanced', 'Advanced'
    
    # What triggers this recommendation
    pattern_type = models.CharField(
        max_length=100,
        unique=True,
        help_text="Pattern type that triggers this recommendation"
    )
    skill = models.ForeignKey(
        'skills.Skill',
        on_delete=models.CASCADE,
        related_name='recommendations',
        null=True,
        blank=True
    )
    
    # Resource details
    title = models.CharField(max_length=200)
    description = models.TextField()
    resource_url = models.URLField(blank=True)
    resource_type = models.CharField(
        max_length=20,
        choices=ResourceType.choices,
        default=ResourceType.ARTICLE
    )
    difficulty = models.CharField(
        max_length=20,
        choices=Difficulty.choices,
        default=Difficulty.INTERMEDIATE
    )
    
    # Priority for ordering
    priority = models.PositiveIntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'learning_recommendations'
        ordering = ['priority', 'title']
    
    def __str__(self):
        return f"{self.title} ({self.resource_type})"
