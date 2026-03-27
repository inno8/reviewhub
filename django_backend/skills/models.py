"""
Skills Models - Categories, skills, and metrics tracking
"""
from django.db import models
from django.conf import settings


class SkillCategory(models.Model):
    """
    Skill category grouping related skills.
    
    Categories:
    1. Code Quality
    2. Design Patterns
    3. Logic & Algorithms
    4. Security
    5. Testing
    6. Frontend
    7. Backend
    8. DevOps
    """
    
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Icon name or emoji")
    color = models.CharField(max_length=7, default='#6366f1', help_text="Hex color")
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'skill_categories'
        ordering = ['order', 'name']
        verbose_name_plural = 'Skill Categories'
    
    def __str__(self):
        return self.name


class Skill(models.Model):
    """
    Individual skill within a category.
    
    32 skills total (4 per category).
    """
    
    category = models.ForeignKey(
        SkillCategory,
        on_delete=models.CASCADE,
        related_name='skills'
    )
    name = models.CharField(max_length=50)
    slug = models.SlugField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    weight = models.FloatField(
        default=1.0,
        help_text="Weight for scoring calculations"
    )
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'skills'
        ordering = ['category__order', 'order', 'name']
    
    def __str__(self):
        return f"{self.category.name} > {self.name}"


class SkillMetric(models.Model):
    """
    Track skill scores per user per project.
    Updated after each evaluation.
    """
    
    class Trend(models.TextChoices):
        UP = 'up', 'Improving'
        DOWN = 'down', 'Declining'
        STABLE = 'stable', 'Stable'
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='skill_metrics'
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='skill_metrics'
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.CASCADE,
        related_name='metrics'
    )
    
    # Current state
    score = models.FloatField(
        default=100.0,
        help_text="Current skill score (0-100)"
    )
    issue_count = models.PositiveIntegerField(
        default=0,
        help_text="Total issues found for this skill"
    )
    fixed_count = models.PositiveIntegerField(
        default=0,
        help_text="Total issues fixed for this skill"
    )
    
    # Trend tracking
    trend = models.CharField(
        max_length=10,
        choices=Trend.choices,
        default=Trend.STABLE
    )
    previous_score = models.FloatField(null=True, blank=True)
    
    # Timestamps
    first_evaluated_at = models.DateTimeField(null=True, blank=True)
    last_evaluated_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'skill_metrics'
        unique_together = ['user', 'project', 'skill']
    
    def __str__(self):
        return f"{self.user.email} - {self.skill.name}: {self.score}"
    
    @property
    def fix_rate(self):
        """Calculate fix rate percentage."""
        if self.issue_count == 0:
            return 100.0
        return (self.fixed_count / self.issue_count) * 100
    
    def update_score(self, new_issues: int, impact: float = 5.0):
        """
        Update skill score based on new issues found.
        
        Args:
            new_issues: Number of new issues found
            impact: Points deducted per issue (default 5)
        """
        from django.utils import timezone
        
        self.previous_score = self.score
        self.issue_count += new_issues
        
        # Calculate new score (min 0, max 100)
        self.score = max(0, min(100, 100 - (self.issue_count * impact)))
        
        # Update trend
        if self.previous_score:
            diff = self.score - self.previous_score
            if diff > 2:
                self.trend = self.Trend.UP
            elif diff < -2:
                self.trend = self.Trend.DOWN
            else:
                self.trend = self.Trend.STABLE
        
        # Update timestamps
        if not self.first_evaluated_at:
            self.first_evaluated_at = timezone.now()
        self.last_evaluated_at = timezone.now()
        
        self.save()
