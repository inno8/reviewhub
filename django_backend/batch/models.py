"""
Batch Processing Models - Historical commit analysis (Phase 6)
"""
from django.db import models
from django.conf import settings


class BatchJob(models.Model):
    """
    Background job for analyzing historical commits from a repository.
    Used to bootstrap developer profiles.
    """
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CLONING = 'cloning', 'Cloning Repository'
        ANALYZING = 'analyzing', 'Analyzing Commits'
        BUILDING_PROFILE = 'building_profile', 'Building Profile'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'
    
    # Who requested this
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='batch_jobs'
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='batch_jobs',
        null=True,
        blank=True,
        help_text="Optional: link to existing project"
    )
    
    # Repository info
    repo_url = models.URLField(help_text="GitHub repository URL")
    branch = models.CharField(
        max_length=100,
        default='main',
        help_text='Branch to analyze, or "__all__" to process every active branch'
    )
    resolved_branches = models.JSONField(
        default=list,
        blank=True,
        help_text='Branches the worker will process (set on create; from GitHub + optional author filter)',
    )
    
    # Processing scope (git log --author pattern; use GitHub username or name fragment)
    target_github_username = models.CharField(
        max_length=150,
        blank=True,
        help_text="Filter commits by author (passed to git log --author); empty = all commits",
    )
    max_commits = models.PositiveIntegerField(
        default=500,
        help_text="Maximum commits to process"
    )
    since_date = models.DateField(
        null=True,
        blank=True,
        help_text="Only process commits after this date"
    )
    
    # Progress tracking
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    total_commits = models.PositiveIntegerField(default=0)
    processed_commits = models.PositiveIntegerField(default=0)
    skipped_commits = models.PositiveIntegerField(
        default=0,
        help_text="Commits skipped (merge commits, too small, etc.)"
    )
    
    # Results summary
    findings_count = models.PositiveIntegerField(default=0)
    skills_detected = models.JSONField(
        default=list,
        help_text="List of skill IDs detected"
    )
    patterns_detected = models.JSONField(
        default=list,
        help_text="List of pattern types detected"
    )
    
    # Error handling
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'batch_jobs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"BatchJob {self.id}: {self.repo_url} ({self.status})"
    
    @property
    def progress_percent(self):
        """Calculate progress percentage."""
        if self.total_commits == 0:
            return 0
        return round((self.processed_commits / self.total_commits) * 100, 1)
    
    @property
    def is_running(self):
        return self.status in [
            self.Status.CLONING,
            self.Status.ANALYZING,
            self.Status.BUILDING_PROFILE
        ]
    
    def mark_started(self):
        """Mark job as started."""
        from django.utils import timezone
        self.status = self.Status.CLONING
        self.started_at = timezone.now()
        self.save()
    
    def mark_completed(self):
        """Mark job as completed."""
        from django.utils import timezone
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save()
    
    def mark_failed(self, error: str):
        """Mark job as failed."""
        from django.utils import timezone
        self.status = self.Status.FAILED
        self.error_message = error
        self.completed_at = timezone.now()
        self.save()


class BatchCommitResult(models.Model):
    """
    Result of analyzing a single commit in a batch job.
    """
    
    job = models.ForeignKey(
        BatchJob,
        on_delete=models.CASCADE,
        related_name='commit_results'
    )
    
    # Commit info
    commit_sha = models.CharField(max_length=40)
    commit_message = models.TextField()
    commit_date = models.DateTimeField()
    author_name = models.CharField(max_length=100)
    author_email = models.EmailField()
    
    # Stats
    files_changed = models.PositiveIntegerField(default=0)
    lines_added = models.PositiveIntegerField(default=0)
    lines_removed = models.PositiveIntegerField(default=0)
    
    # Analysis results
    overall_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Code quality score (0-100)"
    )
    findings_count = models.PositiveIntegerField(default=0)
    
    # Snapshots (for historical tracking)
    skills_snapshot = models.JSONField(
        default=dict,
        help_text="Skill scores at this commit: {skill_id: score}"
    )
    patterns_snapshot = models.JSONField(
        default=list,
        help_text="Patterns detected in this commit"
    )
    
    # Timestamps
    analyzed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'batch_commit_results'
        ordering = ['commit_date']
        indexes = [
            models.Index(fields=['job', 'commit_date']),
            models.Index(fields=['commit_sha']),
        ]
        unique_together = ['job', 'commit_sha']
    
    def __str__(self):
        return f"{self.commit_sha[:7]}: {self.commit_message[:50]}"


class DeveloperProfile(models.Model):
    """
    Comprehensive developer profile built from historical analysis.
    Used for personalized feedback and recommendations.
    """
    
    class Level(models.TextChoices):
        BEGINNER = 'beginner', 'Beginner'
        JUNIOR = 'junior', 'Junior'
        INTERMEDIATE = 'intermediate', 'Intermediate'
        SENIOR = 'senior', 'Senior'
        EXPERT = 'expert', 'Expert'
    
    class Trend(models.TextChoices):
        IMPROVING = 'improving', 'Improving'
        STABLE = 'stable', 'Stable'
        DECLINING = 'declining', 'Declining'
        NEW = 'new', 'New User'
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='developer_profile'
    )
    
    # Generated from batch analysis
    batch_job = models.ForeignKey(
        BatchJob,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='profiles',
        help_text="Batch job that created/updated this profile"
    )
    
    # Overall assessment
    level = models.CharField(
        max_length=20,
        choices=Level.choices,
        default=Level.BEGINNER
    )
    overall_score = models.FloatField(
        default=50.0,
        help_text="Overall coding proficiency (0-100)"
    )
    trend = models.CharField(
        max_length=20,
        choices=Trend.choices,
        default=Trend.NEW
    )
    
    # Strengths & weaknesses
    strengths = models.JSONField(
        default=list,
        help_text="List of skill IDs where user excels"
    )
    weaknesses = models.JSONField(
        default=list,
        help_text="List of skill IDs needing improvement"
    )
    
    # Patterns
    top_patterns = models.JSONField(
        default=list,
        help_text="Most frequent issue patterns"
    )
    resolved_patterns = models.JSONField(
        default=list,
        help_text="Patterns user has overcome"
    )
    
    # Historical data
    commits_analyzed = models.PositiveIntegerField(default=0)
    total_findings = models.PositiveIntegerField(default=0)
    total_fixes = models.PositiveIntegerField(default=0)
    first_commit_date = models.DateField(null=True, blank=True)
    last_commit_date = models.DateField(null=True, blank=True)
    
    # Score history (for trend calculation)
    score_history = models.JSONField(
        default=list,
        help_text="List of {date, score} for tracking progress"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'developer_profiles'
    
    def __str__(self):
        return f"{self.user.email} - {self.level} ({self.overall_score:.1f})"
    
    def calculate_level(self):
        """Determine level based on overall score."""
        if self.overall_score >= 90:
            return self.Level.EXPERT
        elif self.overall_score >= 75:
            return self.Level.SENIOR
        elif self.overall_score >= 60:
            return self.Level.INTERMEDIATE
        elif self.overall_score >= 40:
            return self.Level.JUNIOR
        return self.Level.BEGINNER
    
    def calculate_trend(self):
        """Determine trend based on recent score history."""
        if len(self.score_history) < 3:
            return self.Trend.NEW
        
        recent = self.score_history[-3:]
        avg_recent = sum(s['score'] for s in recent) / len(recent)
        
        older = self.score_history[-6:-3] if len(self.score_history) >= 6 else self.score_history[:3]
        avg_older = sum(s['score'] for s in older) / len(older)
        
        diff = avg_recent - avg_older
        if diff > 5:
            return self.Trend.IMPROVING
        elif diff < -5:
            return self.Trend.DECLINING
        return self.Trend.STABLE
    
    def update_from_analysis(self):
        """Recalculate level and trend from current data."""
        self.level = self.calculate_level()
        self.trend = self.calculate_trend()
        self.save()
