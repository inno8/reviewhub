"""
Skills Models - Categories, skills, metrics tracking, and learning algorithm.

The learning algorithm uses three measurement layers:
  Layer 1: Commit Quality Snapshot (SkillObservation)
  Layer 2: Growth Trajectory (GrowthSnapshot, Pattern integration)
  Layer 3: Decision Quality (captured in SkillObservation)

Scoring uses a Bayesian approach starting from uncertainty (50),
not optimism (100). Confidence grows with evidence.

See docs/LEARNING_ALGORITHM.md for full specification.
"""
from django.db import models
from django.conf import settings


# ═══════════════════════════════════════════════════════════════════════════════
# Learning Algorithm Constants
# ═══════════════════════════════════════════════════════════════════════════════

# Complexity weights (from CommitClassifier level)
COMPLEXITY_WEIGHTS = {
    'simple': 0.4,
    'medium': 0.7,
    'complex': 1.0,
    '': 0.7,       # fallback when not classified
}

# Severity impact on score
SEVERITY_WEIGHTS = {
    'critical': 10.0,
    'warning': 5.0,
    'info': 2.0,
    'suggestion': 1.0,
}

# Bayesian scoring parameters
INITIAL_SCORE = 50.0
INITIAL_CONFIDENCE = 0.0
MAX_LEARNING_RATE = 0.35
MIN_LEARNING_RATE = 0.05
CONFIDENCE_GAIN_PER_OBS = 0.02

# Behavioral proof scoring
PROOF_REQUIRED_EVIDENCE = 2
PROOF_PROVEN_BONUS = 8.0
PROOF_REINFORCED_BONUS = 3.0
PROOF_RELAPSE_PENALTY = -5.0
PROOF_RELAPSE_AFTER_PROVEN_PENALTY = -10.0
FIX_LEARN_GOT_IT_BONUS = 2.0
FIX_LEARN_PARTIAL_BONUS = 1.0

# Pattern scoring
PATTERN_RESOLVED_BONUS = 5.0
PATTERN_RELAPSED_PENALTY = -8.0
PATTERN_RECURRING_PENALTY = -3.0

# Confidence thresholds for display
CONFIDENCE_PRELIMINARY = 0.15
CONFIDENCE_DEVELOPING = 0.40
CONFIDENCE_ESTABLISHED = 0.70
CONFIDENCE_VERIFIED = 0.85

# Level thresholds (Bayesian score ranges)
LEVEL_THRESHOLDS = {
    'master': 85,
    'expert': 70,
    'proficient': 50,
    'competent': 30,
    'beginner': 15,
    'novice': 0,
}

# Minimum evaluations required before showing a level label
MIN_EVALS_FOR_LEVEL = {
    'master': 50,
    'expert': 30,
    'proficient': 20,
    'competent': 10,
    'beginner': 5,
    'novice': 0,
}


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
    
    # Legacy score (kept for backward compat; new code reads bayesian_score)
    score = models.FloatField(
        default=100.0,
        help_text="Legacy skill score (0-100). Use bayesian_score instead."
    )
    issue_count = models.PositiveIntegerField(
        default=0,
        help_text="Total issues found for this skill"
    )
    fixed_count = models.PositiveIntegerField(
        default=0,
        help_text="Total issues fixed for this skill"
    )

    # ── Bayesian Learning Algorithm fields ────────────────────────────────
    bayesian_score = models.FloatField(
        default=INITIAL_SCORE,
        help_text="Bayesian skill score (0-100). Starts at 50 (uncertain)."
    )
    confidence = models.FloatField(
        default=INITIAL_CONFIDENCE,
        help_text="Confidence in the score (0.0-1.0). Grows with observations."
    )
    observation_count = models.PositiveIntegerField(
        default=0,
        help_text="Total SkillObservation records for this skill."
    )
    proven_concepts = models.PositiveIntegerField(
        default=0,
        help_text="Fix & Learn concepts proven by future behavior."
    )
    relapsed_concepts = models.PositiveIntegerField(
        default=0,
        help_text="Fix & Learn concepts where developer relapsed."
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
        indexes = [
            models.Index(fields=['user', 'project']),
            models.Index(fields=['skill', 'project']),
            models.Index(fields=['user', 'score']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.skill.name}: {self.score}"
    
    @property
    def fix_rate(self):
        """Calculate fix rate percentage."""
        if self.issue_count == 0:
            return 100.0
        return (self.fixed_count / self.issue_count) * 100
    
    @property
    def display_score(self):
        """The score to use for display. Prefers bayesian_score."""
        return self.bayesian_score

    @property
    def confidence_label(self):
        """Human-readable confidence level."""
        if self.confidence >= CONFIDENCE_VERIFIED:
            return 'verified'
        if self.confidence >= CONFIDENCE_ESTABLISHED:
            return 'established'
        if self.confidence >= CONFIDENCE_DEVELOPING:
            return 'developing'
        if self.confidence >= CONFIDENCE_PRELIMINARY:
            return 'preliminary'
        return 'insufficient'

    @property
    def level_label(self):
        """Skill level based on bayesian_score. Returns None if insufficient data."""
        if self.confidence < CONFIDENCE_PRELIMINARY:
            return None  # Not enough data to label
        score = self.bayesian_score
        for level, threshold in LEVEL_THRESHOLDS.items():
            if score >= threshold:
                return level
        return 'novice'

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
            self.score = self.score * (1 - learning_rate) + observed_score * learning_rate
        else:
            penalty = new_issues * impact
            instant_score = max(0, self.score - penalty)
            self.score = self.score * (1 - learning_rate) + instant_score * learning_rate

        if self.fixed_count > 0 and self.issue_count > 0:
            fix_bonus = (self.fixed_count / self.issue_count) * 10 * learning_rate
            self.score = min(100, self.score + fix_bonus)

        self.score = max(0.0, min(100.0, round(self.score, 2)))

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

    def update_bayesian(self, weighted_score: float, complexity_weight: float = 0.7):
        """
        Update bayesian_score using evidence-based Bayesian formula.

        Unlike update_score() which starts at 100 and deducts, this starts
        at 50 (uncertain) and converges on the developer's true skill level.

        Args:
            weighted_score: quality_score × complexity_weight (0-100)
            complexity_weight: how complex the code was (0.4-1.0)
        """
        from django.utils import timezone

        self.previous_score = self.bayesian_score
        self.observation_count += 1

        # Learning rate decreases as confidence grows
        learning_rate = max(
            MIN_LEARNING_RATE,
            MAX_LEARNING_RATE * (1 - self.confidence),
        )

        # Update score: blend current with new observation
        self.bayesian_score = (
            self.bayesian_score * (1 - learning_rate)
            + weighted_score * learning_rate
        )
        self.bayesian_score = max(0.0, min(100.0, round(self.bayesian_score, 2)))

        # Update confidence (complex code gives more confidence)
        self.confidence = min(
            1.0,
            self.confidence + CONFIDENCE_GAIN_PER_OBS * complexity_weight,
        )
        self.confidence = round(self.confidence, 4)

        # Trend
        if self.previous_score is not None:
            diff = self.bayesian_score - self.previous_score
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

    def apply_bonus(self, bonus: float):
        """
        Apply a bonus/penalty to bayesian_score (e.g. from proof events).
        Scaled by current learning rate so bonuses shrink as confidence grows.
        """
        learning_rate = max(
            MIN_LEARNING_RATE,
            MAX_LEARNING_RATE * (1 - self.confidence),
        )
        adjustment = bonus * learning_rate
        self.bayesian_score = max(
            0.0,
            min(100.0, round(self.bayesian_score + adjustment, 2)),
        )
        self.save(update_fields=['bayesian_score', 'updated_at'])

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

        # Also nudge bayesian_score
        self.apply_bonus(recovery)

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


# ═══════════════════════════════════════════════════════════════════════════════
# Layer 1: Commit Quality Snapshot
# ═══════════════════════════════════════════════════════════════════════════════

class SkillObservation(models.Model):
    """
    Per-commit, per-skill quality snapshot — the raw evidence.

    Every time an evaluation touches a skill, one SkillObservation is created.
    This is the foundational data for the Bayesian scoring model.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='skill_observations',
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='skill_observations',
    )
    evaluation = models.ForeignKey(
        'evaluations.Evaluation',
        on_delete=models.CASCADE,
        related_name='skill_observations',
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.CASCADE,
        related_name='observations',
    )
    # Optional link back to the GradingSession (Nakijken Copilot v1) that
    # produced this observation. Nullable because legacy (pre-grading)
    # observations are written by the evaluations app and have no session.
    # Used for idempotent bind — re-running bind_rubric_to_observations
    # update_or_creates per (session, user, skill) instead of duplicating.
    grading_session = models.ForeignKey(
        'grading.GradingSession',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='skill_observations',
    )
    commit_sha = models.CharField(max_length=40)

    # Quality measurement
    quality_score = models.FloatField(
        help_text="Raw LLM score for this skill (0-100)"
    )
    complexity_weight = models.FloatField(
        default=0.7,
        help_text="From CommitClassifier: simple=0.4, medium=0.7, complex=1.0"
    )
    weighted_score = models.FloatField(
        help_text="quality_score × complexity_weight"
    )
    lines_changed = models.PositiveIntegerField(default=0)

    # Issue breakdown
    issue_count = models.PositiveIntegerField(default=0)
    critical_count = models.PositiveIntegerField(default=0)
    warning_count = models.PositiveIntegerField(default=0)
    info_count = models.PositiveIntegerField(default=0)
    suggestion_count = models.PositiveIntegerField(default=0)
    issue_density = models.FloatField(
        default=0,
        help_text="weighted_issues / max(lines_changed, 10)"
    )

    # Decision quality (Layer 3)
    decision_appropriate = models.PositiveIntegerField(default=0)
    decision_suboptimal = models.PositiveIntegerField(default=0)
    decision_poor = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'skill_observations'
        indexes = [
            models.Index(fields=['user', 'skill', 'created_at']),
            models.Index(fields=['user', 'project', 'created_at']),
            models.Index(fields=['evaluation']),
        ]

    def __str__(self):
        return (
            f"{self.user.email} - {self.skill.name} "
            f"[{self.weighted_score:.0f}] @ {self.commit_sha[:7]}"
        )

    def save(self, **kwargs):
        # Auto-compute weighted_score and issue_density on save
        if self.quality_score is not None and self.complexity_weight:
            self.weighted_score = round(
                self.quality_score * self.complexity_weight, 2
            )
        severity_total = (
            self.critical_count * SEVERITY_WEIGHTS['critical']
            + self.warning_count * SEVERITY_WEIGHTS['warning']
            + self.info_count * SEVERITY_WEIGHTS['info']
            + self.suggestion_count * SEVERITY_WEIGHTS['suggestion']
        )
        self.issue_density = round(
            severity_total / max(self.lines_changed, 10), 4
        )
        # If the caller passed update_fields (e.g. via update_or_create),
        # add the auto-computed columns so the recomputed values actually
        # hit the DB. Without this, an update_or_create that changes
        # quality_score leaves a stale weighted_score behind — a silent
        # bug that masked the SkillMetric regrade fix.
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)
            if "quality_score" in update_fields or "complexity_weight" in update_fields:
                update_fields.add("weighted_score")
            if any(f in update_fields for f in (
                "critical_count", "warning_count", "info_count",
                "suggestion_count", "lines_changed",
            )):
                update_fields.add("issue_density")
            kwargs["update_fields"] = update_fields
        super().save(**kwargs)


# ═══════════════════════════════════════════════════════════════════════════════
# Behavioral Proof System
# ═══════════════════════════════════════════════════════════════════════════════

class LearningProof(models.Model):
    """
    Connects Fix & Learn understanding to future behavioral evidence.

    When a developer says "got it" in Fix & Learn, a LearningProof is created
    with status PENDING. Future commits are checked for the same issue type.
    If the issue doesn't recur, the proof is marked PROVEN. If it does, RELAPSED.
    """

    class Status(models.TextChoices):
        # TODO (future feature): state for "taught but not yet verified by clean
        # commit." Currently never set — PENDING is used for all new proofs.
        # Will be used when the Fix & Learn flow splits "explained" from "applied".
        TAUGHT = 'taught', 'Taught'
        PENDING = 'pending', 'Pending Proof'
        PROVEN = 'proven', 'Proven'
        REINFORCED = 'reinforced', 'Reinforced'
        RELAPSED = 'relapsed', 'Relapsed'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='learning_proofs',
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.CASCADE,
        related_name='learning_proofs',
    )
    finding = models.ForeignKey(
        'evaluations.Finding',
        on_delete=models.CASCADE,
        related_name='learning_proofs',
    )
    issue_type = models.CharField(
        max_length=200,
        help_text="Pattern key, e.g. 'bare_except', 'sql_injection'"
    )

    # Teaching context
    taught_at = models.DateTimeField()
    understanding_level = models.CharField(
        max_length=20,
        help_text="got_it / partial / not_yet from Fix & Learn"
    )
    concept_summary = models.TextField(
        blank=True,
        help_text="What was explained to the developer"
    )

    # Proof tracking
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.TAUGHT,
    )
    proof_evidence_count = models.PositiveIntegerField(
        default=0,
        help_text="Commits where similar code handled correctly"
    )
    proof_commit = models.CharField(
        max_length=40,
        blank=True,
        help_text="Commit SHA that proved understanding"
    )
    proven_at = models.DateTimeField(null=True, blank=True)
    relapse_commit = models.CharField(
        max_length=40,
        blank=True,
        help_text="Commit SHA where mistake was repeated"
    )
    relapsed_at = models.DateTimeField(null=True, blank=True)
    score_impact_applied = models.FloatField(
        default=0,
        help_text="Total score impact applied from this proof"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'learning_proofs'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['user', 'skill', 'issue_type']),
        ]

    def __str__(self):
        return (
            f"{self.user.email} - {self.issue_type} "
            f"[{self.status}]"
        )

    @property
    def project(self):
        """Resolve the project this proof belongs to via its originating finding."""
        try:
            return self.finding.evaluation.project if self.finding and self.finding.evaluation else None
        except Exception:
            return None

    def mark_proven(self, commit_sha: str):
        """Mark this concept as proven by behavioral evidence."""
        from django.utils import timezone

        was_relapsed = self.status == self.Status.RELAPSED
        self.status = self.Status.PROVEN
        self.proof_commit = commit_sha
        self.proven_at = timezone.now()

        # Apply score bonus to the relevant SkillMetric
        bonus = PROOF_PROVEN_BONUS
        self.score_impact_applied += bonus
        self.save()

        metric = SkillMetric.objects.filter(
            user=self.user, skill=self.skill, project=self.project,
        ).first()
        if metric:
            metric.proven_concepts += 1
            metric.apply_bonus(bonus)

    def mark_reinforced(self, commit_sha: str):
        """Mark as reinforced — pattern fully internalized (3+ correct)."""
        self.status = self.Status.REINFORCED
        self.proof_commit = commit_sha

        bonus = PROOF_REINFORCED_BONUS
        self.score_impact_applied += bonus
        self.save()

        metric = SkillMetric.objects.filter(
            user=self.user, skill=self.skill, project=self.project,
        ).first()
        if metric:
            metric.apply_bonus(bonus)

    def mark_relapsed(self, commit_sha: str):
        """Mark as relapsed — same mistake appeared again."""
        from django.utils import timezone

        was_proven = self.status in (self.Status.PROVEN, self.Status.REINFORCED)
        self.status = self.Status.RELAPSED
        self.relapse_commit = commit_sha
        self.relapsed_at = timezone.now()

        penalty = (
            PROOF_RELAPSE_AFTER_PROVEN_PENALTY
            if was_proven
            else PROOF_RELAPSE_PENALTY
        )
        self.score_impact_applied += penalty
        self.save()

        metric = SkillMetric.objects.filter(
            user=self.user, skill=self.skill, project=self.project,
        ).first()
        if metric:
            metric.relapsed_concepts += 1
            metric.apply_bonus(penalty)


# ═══════════════════════════════════════════════════════════════════════════════
# Growth Tracking
# ═══════════════════════════════════════════════════════════════════════════════

class GrowthSnapshot(models.Model):
    """
    Weekly growth snapshot for timeline visualization.

    Aggregated from SkillObservation records. One per user per project per week.
    Used to render the developer journey timeline and compute growth velocity.

    TODO: Not yet populated. A weekly aggregation Celery task is planned
    (see v1.1 roadmap) that will write one row per (user, project, week_start)
    aggregating SkillMetric state. No writer logic exists today.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='growth_snapshots',
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='growth_snapshots',
        null=True,
        blank=True,
        help_text="null = cross-project snapshot"
    )
    week_start = models.DateField(
        help_text="Monday of the snapshot week"
    )

    # Score summary
    avg_weighted_score = models.FloatField(default=0)
    avg_complexity = models.FloatField(default=0)
    evaluation_count = models.PositiveIntegerField(default=0)

    # Severity distribution (percentages, 0-100)
    pct_critical = models.FloatField(default=0)
    pct_warning = models.FloatField(default=0)
    pct_info = models.FloatField(default=0)
    pct_suggestion = models.FloatField(default=0)

    # Growth signals
    patterns_resolved = models.PositiveIntegerField(default=0)
    patterns_relapsed = models.PositiveIntegerField(default=0)
    concepts_proven = models.PositiveIntegerField(default=0)
    concepts_relapsed = models.PositiveIntegerField(default=0)
    new_skills_touched = models.PositiveIntegerField(default=0)

    # Computed
    growth_velocity = models.FloatField(
        default=0,
        help_text="Score change rate vs. previous week"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'growth_snapshots'
        unique_together = ['user', 'project', 'week_start']
        indexes = [
            models.Index(fields=['user', 'week_start']),
        ]

    def __str__(self):
        return f"{self.user.email} - week {self.week_start}"
