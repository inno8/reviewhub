"""
Evaluation Models - Code reviews, findings, and patterns
"""
from django.db import models
from django.conf import settings


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
    author_email = models.EmailField()
    
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
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    evaluated_at = models.DateTimeField(null=True, blank=True)
    
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
        
        # Update skill metrics
        for finding_skill in self.finding_skills.all():
            metric = finding_skill.skill.metrics.filter(
                user=self.evaluation.author,
                project=self.evaluation.project
            ).first()
            if metric:
                metric.fixed_count += 1
                metric.save()


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
