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
    
    def update_score(self, new_issues: int = 0, impact: float = 5.0, observed_score: float = None):
        """
        Update skill score using exponential moving average (EMA).

        Two modes:
          1. Issue-based: deduct points per issue (called from evaluation flow).
          2. Score-based: blend observed_score from LLM into current score.

        The learning rate decays with evaluation count so early evaluations
        have more influence and the score stabilises over time.
        """
        from django.utils import timezone

        self.previous_score = self.score
        self.issue_count += new_issues

        eval_count = self.issue_count + self.fixed_count + 1
        learning_rate = max(0.05, 1.0 / eval_count)

        if observed_score is not None:
            # Blend observed score with current score
            self.score = self.score * (1 - learning_rate) + observed_score * learning_rate
        else:
            # Deduction mode: compute an "observed" score from the penalty
            penalty = new_issues * impact
            instant_score = max(0, self.score - penalty)
            self.score = self.score * (1 - learning_rate) + instant_score * learning_rate

        # Fixes push the score up (reward)
        if self.fixed_count > 0 and self.issue_count > 0:
            fix_bonus = (self.fixed_count / self.issue_count) * 10 * learning_rate
            self.score = min(100, self.score + fix_bonus)

        self.score = max(0.0, min(100.0, round(self.score, 2)))

        # Trend
        if self.previous_score is not None:
            diff = self.score - self.previous_score
            if diff > 2:
                self.trend = self.Trend.UP
            elif diff < -2:
                self.trend = self.Trend.DOWN
            else:
                self.trend = self.Trend.STABLE

        if not self.first_evaluated_at:
            self.first_evaluated_at = timezone.now()
        self.last_evaluated_at = timezone.now()

        self.save()

    def improve_score(self, fixed_issues: int = 1, recovery: float = 3.0):
        """
        Improve score when developer fixes an issue and demonstrates understanding.
        Called from Finding.mark_fixed().
        """
        from django.utils import timezone

        self.previous_score = self.score
        self.fixed_count += fixed_issues
        self.score = min(100.0, self.score + (fixed_issues * recovery))
        self.score = round(self.score, 2)

        # Update trend
        if self.previous_score is not None:
            diff = self.score - self.previous_score
            if diff > 2:
                self.trend = self.Trend.UP
            elif diff < -2:
                self.trend = self.Trend.DOWN
            else:
                self.trend = self.Trend.STABLE

        self.last_evaluated_at = timezone.now()
        self.save()
