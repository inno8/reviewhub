"""
Grading models — Nakijken Copilot v1.

Design doc: ~/.gstack/projects/inno8-reviewhub/yanic-main-design-20260417-175102.md
Eng review addenda: see Appendix: Eng Review Addenda in the same doc.

Model relationships (ASCII):

    Organization ──< Cohort ──< CohortMembership >── User (student, one cohort each)
         │             │
         │             └──< Course ──> Rubric (FK, default for course)
         │                     │
         │                     └──> User owner (TEACHER role = docent)
         │
         └──< Rubric                      (org-scoped; templates are global is_template=True)

    Course ──< Submission ──< Evaluation       (evaluation is per-commit, existing model)
                  │
                  └──> GradingSession (OneToOne w/ Submission; holds AI draft + docent review state)

    GradingSession ──< PostedComment         (idempotency ledger for GitHub comment posts)

    LLMCostLog                                (append-only cost metering, queried per docent/class)

    WebhookDelivery                           (idempotency table for GitHub webhook re-delivery)

Notes:
  - Submission is the PR-level grouping. A PR with N commits = 1 Submission with N Evaluations.
  - GradingSession is OneToOne with Submission (the PR is what gets graded, not the commit).
  - PostedComment is the per-comment idempotency record (client_mutation_id hash).
  - All user-scoped models FK to Organization for OrgScopedManager.
"""
from __future__ import annotations

import hashlib
import json

from django.conf import settings
from django.db import models
from django.utils import timezone

from .managers import OrgScopedManager


# ─────────────────────────────────────────────────────────────────────────────
# Rubric
# ─────────────────────────────────────────────────────────────────────────────
class Rubric(models.Model):
    """
    A grading rubric — criteria + level definitions + calibration hints.

    Shape of `criteria` JSON:
        [
          {
            "id": "readability",
            "name": "Readability",
            "weight": 0.2,
            "levels": [
              {"score": 1, "description": "Cannot understand without author"},
              {"score": 2, "description": "Variable names are cryptic"},
              {"score": 3, "description": "Clear with minor issues"},
              {"score": 4, "description": "Clear, idiomatic, professional"}
            ]
          },
          ...
        ]

    Shape of `calibration` JSON (docent's voice):
        {
          "tone": "formal" | "informal",
          "language": "nl" | "en" | "mix",
          "depth": "terse" | "detailed",
          "example_comments": [
            {"context": "missing type hint", "comment": "Geef type-hints toe..."}
          ]
        }
    """

    org = models.ForeignKey(
        "users.Organization",
        on_delete=models.CASCADE,
        related_name="rubrics",
        null=True,
        blank=True,
        help_text="Org that owns the rubric. Null for global templates (is_template=True).",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_rubrics",
        help_text="Teacher/docent who created this rubric. Null for built-in templates.",
    )
    is_template = models.BooleanField(
        default=False,
        help_text="True for built-in crebo 25187/25188 templates shipped with the product.",
    )
    name = models.CharField(max_length=150)
    criteria = models.JSONField(
        default=list,
        help_text="List of criterion dicts. Validated at save time.",
    )
    calibration = models.JSONField(
        default=dict,
        blank=True,
        help_text="Docent voice calibration (tone, language, depth, example_comments).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = OrgScopedManager()

    class Meta:
        db_table = "grading_rubrics"
        indexes = [
            models.Index(fields=["org", "is_template", "-updated_at"]),
        ]
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        scope = "template" if self.is_template else (self.org.name if self.org else "orphan")
        return f"{self.name} ({scope})"


# ─────────────────────────────────────────────────────────────────────────────
# Cohort (the student-group, licensing unit — €200/cohort/month)
# ─────────────────────────────────────────────────────────────────────────────
class Cohort(models.Model):
    """
    A group of students studying together (MBO 'klas').
    One student belongs to ONE cohort. A cohort has many Courses
    (one per subject, each with its own teacher + rubric).
    This is the licensing unit for billing (€200/cohort/month).
    """

    org = models.ForeignKey(
        "users.Organization",
        on_delete=models.CASCADE,
        related_name="cohorts",
    )
    name = models.CharField(max_length=150)  # e.g., "Klas 2A ICT 2026"
    year = models.CharField(max_length=20, blank=True)  # e.g., "2026-2027"
    starts_at = models.DateField(null=True, blank=True)
    ends_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = OrgScopedManager()

    class Meta:
        db_table = "grading_cohorts"
        indexes = [
            models.Index(fields=["org", "-created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.org.name if self.org else 'no org'})"


# ─────────────────────────────────────────────────────────────────────────────
# Course (was "Classroom" — one teacher + one subject + one rubric, in a cohort)
# ─────────────────────────────────────────────────────────────────────────────
class Course(models.Model):
    """
    One teacher + one subject + one rubric, within a Cohort.

    A Cohort (klas) has many Courses (subjects), each taught by a different
    teacher. E.g. "Klas 2A ICT" cohort has Frontend, Backend, Databases,
    DevOps courses — 4 teachers, 4 rubrics, same 20 students.

    Students connect their OWN GitHub/GitLab via GitProviderConnection
    (existing model in users app). The course tracks which repo each
    student uses for which assignment through CohortMembership at the
    cohort level (one repo-per-cohort, not per-course, in v1).
    """

    class SourceControlType(models.TextChoices):
        GITHUB_ORG = "github_org", "GitHub (personal or org repos)"
        GITLAB = "gitlab", "GitLab (personal or group repos)"
        # bitbucket / gitea added in v2

    org = models.ForeignKey(
        "users.Organization",
        on_delete=models.CASCADE,
        related_name="courses",
    )
    cohort = models.ForeignKey(
        Cohort,
        on_delete=models.CASCADE,
        related_name="courses",
        null=True,
        blank=True,
        help_text="Cohort (klas) this course belongs to. Nullable during initial migration; application-level code treats it as required post-migration.",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_courses",
        help_text="Primary docent. Must have role=TEACHER.",
    )
    secondary_docent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="secondary_courses",
    )
    name = models.CharField(max_length=150)
    source_control_type = models.CharField(
        max_length=20,
        choices=SourceControlType.choices,
        default=SourceControlType.GITHUB_ORG,
    )
    target_branch_pattern = models.CharField(
        max_length=100,
        default="main",
        help_text='Branch(es) to grade. Supports "main" or "main,develop" or "*" (all).',
    )
    rubric = models.ForeignKey(
        Rubric,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="courses_using",
    )
    starts_at = models.DateField(null=True, blank=True)
    ends_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = OrgScopedManager()

    class Meta:
        db_table = "grading_courses"
        indexes = [
            models.Index(fields=["org", "owner", "-created_at"]),
            models.Index(fields=["cohort", "-created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.owner.email})"


class CohortMembership(models.Model):
    """
    A student joining a Cohort (klas). Links a student to their own repo
    (usually via their personal GitProviderConnection) for this cohort.

    One student → ONE cohort (enforced by OneToOneField on student).
    A cohort has many students; all courses in the cohort share those
    students.

    Semantic change from the old ClassroomMembership: membership is now
    at the cohort level, not the course level.
    """

    cohort = models.ForeignKey(
        Cohort,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    student = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cohort_membership",
        help_text="A student belongs to exactly one cohort. Enforced at the DB level via OneToOne.",
    )
    student_repo_url = models.URLField(
        blank=True,
        null=True,
        help_text="Student's chosen repo URL for this cohort (e.g., github.com/jandeboer/assignment-q3).",
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "grading_cohort_memberships"
        ordering = ["cohort", "student"]

    def __str__(self) -> str:
        return f"{self.student.email} in {self.cohort.name}"


# ─────────────────────────────────────────────────────────────────────────────
# Submission + GradingSession
# ─────────────────────────────────────────────────────────────────────────────
class Submission(models.Model):
    """
    A PR-level grouping. One PR from one student in one class = one Submission.
    A Submission has many Evaluations (one per commit pushed to the PR).

    The GradingSession is OneToOne with Submission (the PR is what gets graded).
    """

    class Status(models.TextChoices):
        OPEN = "open", "Open (student may still push)"
        SUBMITTED = "submitted", "Submitted for grading"
        GRADED = "graded", "Graded and closed"

    org = models.ForeignKey(
        "users.Organization",
        on_delete=models.CASCADE,
        related_name="grading_submissions",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="grading_submissions",
    )
    repo_full_name = models.CharField(max_length=200)  # e.g., "jandeboer/assignment-q3"
    pr_number = models.IntegerField()
    pr_url = models.URLField()
    pr_title = models.CharField(max_length=500, blank=True)
    base_branch = models.CharField(max_length=100, default="main")
    head_branch = models.CharField(max_length=100)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )
    due_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = OrgScopedManager()

    class Meta:
        db_table = "grading_submissions"
        unique_together = [("course", "repo_full_name", "pr_number")]
        indexes = [
            models.Index(fields=["org", "course", "status"]),
            models.Index(fields=["student", "-created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.student.email} → {self.repo_full_name}#{self.pr_number}"


class GradingSession(models.Model):
    """
    The AI-draft + docent-review state machine for grading a Submission.

    State transitions (enforced by the `transition_to` method below):
        pending    → drafting   : when docent opens inbox or AI worker picks up
        drafting   → drafted    : AI draft complete
        drafting   → failed     : LLM error beyond retries
        drafted    → reviewing  : docent opens the session UI
        reviewing  → sending    : docent clicks Send (idempotency lock)
        sending    → posted     : all comments successfully posted to PR
        sending    → partial    : some comments posted, network failure
        partial    → sending    : docent clicks Resume
        partial    → posted     : Resume completes successfully
        any        → discarded  : student pushed new commits + docent chose "discard draft"

    Per eng-review concurrency bundle, every state-change uses select_for_update.
    """

    class State(models.TextChoices):
        PENDING = "pending", "Pending (draft not yet requested)"
        DRAFTING = "drafting", "Drafting (AI running)"
        DRAFTED = "drafted", "Draft ready"
        REVIEWING = "reviewing", "Docent reviewing"
        SENDING = "sending", "Sending comments"
        POSTED = "posted", "All comments posted"
        PARTIAL = "partial", "Partial post (needs Resume)"
        FAILED = "failed", "Draft generation failed"
        DISCARDED = "discarded", "Draft discarded (student pushed new code)"

    org = models.ForeignKey(
        "users.Organization",
        on_delete=models.CASCADE,
        related_name="grading_sessions",
    )
    submission = models.OneToOneField(
        Submission,
        on_delete=models.CASCADE,
        related_name="grading_session",
    )
    rubric = models.ForeignKey(
        Rubric,
        on_delete=models.PROTECT,
        related_name="grading_sessions",
    )
    # Evaluations (commits) included in this grading snapshot.
    # FK from Evaluation side is added below via nullable FK; we expose the
    # reverse accessor here for convenience. v1 keeps this as a M2M via a
    # through table to avoid coupling Evaluation to grading directly.
    state = models.CharField(
        max_length=20,
        choices=State.choices,
        default=State.PENDING,
    )

    # AI draft (populated by rubric_grader service)
    ai_draft_scores = models.JSONField(
        default=dict,
        blank=True,
        help_text='Per-criterion: {criterion_id: {"score": int, "evidence": "quote from diff"}}',
    )
    ai_draft_comments = models.JSONField(
        default=list,
        blank=True,
        help_text='List of {"file", "line", "body", "client_mutation_id"} comments.',
    )
    ai_draft_model = models.CharField(max_length=80, blank=True)
    ai_draft_generated_at = models.DateTimeField(null=True, blank=True)
    ai_draft_truncated = models.BooleanField(
        default=False,
        help_text="True if diff was truncated before being sent to the LLM (>3000 lines).",
    )

    # Docent-edited final version
    final_scores = models.JSONField(default=dict, blank=True)
    final_comments = models.JSONField(default=list, blank=True)
    final_summary = models.TextField(blank=True)

    # Timing and send state
    docent_review_started_at = models.DateTimeField(null=True, blank=True)
    docent_review_time_seconds = models.IntegerField(
        null=True, blank=True,
        help_text="Stopwatch metric: time from open to send. THE core v1 validation metric.",
    )
    sending_started_at = models.DateTimeField(null=True, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)

    # Partial-post recovery (eng-review concurrency bundle)
    partial_post_error = models.JSONField(
        null=True, blank=True,
        help_text='{"error_class", "message", "failed_at_comment_idx"} when state=partial',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = OrgScopedManager()

    class Meta:
        db_table = "grading_sessions"
        indexes = [
            models.Index(fields=["org", "state", "-created_at"]),
            models.Index(fields=["state", "updated_at"]),  # janitor query for stuck sessions
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"GradingSession({self.submission}) [{self.state}]"

    # ── state machine helpers ────────────────────────────────────────────
    ALLOWED_TRANSITIONS = {
        State.PENDING: {State.DRAFTING, State.DISCARDED},
        State.DRAFTING: {State.DRAFTED, State.FAILED, State.DISCARDED},
        State.DRAFTED: {State.REVIEWING, State.DRAFTING, State.DISCARDED},
        State.REVIEWING: {State.SENDING, State.DRAFTING, State.DISCARDED},
        State.SENDING: {State.POSTED, State.PARTIAL},
        State.PARTIAL: {State.SENDING, State.POSTED, State.DISCARDED},
        State.FAILED: {State.DRAFTING, State.DISCARDED},
        State.POSTED: set(),  # terminal
        State.DISCARDED: set(),  # terminal
    }

    def can_transition_to(self, new_state: str) -> bool:
        allowed = self.ALLOWED_TRANSITIONS.get(self.state, set())
        return new_state in {s.value if hasattr(s, "value") else s for s in allowed}


class SessionEvaluation(models.Model):
    """
    Through-table linking GradingSession to Evaluation (existing model from
    evaluations app). Lets the rubric grader see ALL commits in the PR, not
    just the latest.

    Kept as a separate model rather than M2M to carry a `was_graded_in_draft`
    flag in case the session regenerates against an updated commit list.
    """

    grading_session = models.ForeignKey(
        GradingSession,
        on_delete=models.CASCADE,
        related_name="session_evaluations",
    )
    evaluation = models.ForeignKey(
        "evaluations.Evaluation",
        on_delete=models.CASCADE,
        related_name="grading_session_links",
    )
    included_in_draft = models.BooleanField(default=True)

    class Meta:
        db_table = "grading_session_evaluations"
        unique_together = [("grading_session", "evaluation")]


# ─────────────────────────────────────────────────────────────────────────────
# Posted comment ledger (concurrency bundle)
# ─────────────────────────────────────────────────────────────────────────────
class PostedComment(models.Model):
    """
    Idempotency ledger for comments successfully posted to GitHub.

    Per the eng-review concurrency bundle, each comment has a `client_mutation_id`
    which is a hash of (session_id, file_path, line, body_hash). If the same
    comment is sent twice (Send + Resume, double-click, retry storm), we skip
    the duplicate at the persistence layer.

    Each row is written in its own short transaction immediately after the
    GitHub API 201 response. The comment loop is NOT wrapped in atomic().
    """

    grading_session = models.ForeignKey(
        GradingSession,
        on_delete=models.CASCADE,
        related_name="posted_comments",
    )
    client_mutation_id = models.CharField(
        max_length=64,
        help_text="Hash of (session_id, file, line, body_hash). Idempotency key.",
    )
    github_comment_id = models.BigIntegerField(
        null=True, blank=True,
        help_text="The numeric id GitHub returned on POST /pulls/comments.",
    )
    file_path = models.CharField(max_length=500)
    line_number = models.IntegerField()
    body_preview = models.CharField(max_length=200, blank=True)  # first N chars for debugging
    posted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "grading_posted_comments"
        unique_together = [("grading_session", "client_mutation_id")]
        indexes = [
            models.Index(fields=["grading_session", "posted_at"]),
        ]

    def __str__(self) -> str:
        return f"PostedComment({self.client_mutation_id}) for {self.grading_session_id}"

    @staticmethod
    def compute_mutation_id(session_id: int, file_path: str, line: int, body: str) -> str:
        """
        Deterministic idempotency key.
        Changing the body changes the id → new comment, not a dupe.
        """
        key = f"{session_id}|{file_path}|{line}|{hashlib.sha256(body.encode('utf-8')).hexdigest()}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:64]


# ─────────────────────────────────────────────────────────────────────────────
# Webhook delivery dedupe (concurrency bundle)
# ─────────────────────────────────────────────────────────────────────────────
class WebhookDelivery(models.Model):
    """
    Idempotency table for GitHub / GitLab webhook redelivery.

    GitHub re-delivers on timeout; manual replays are common. Without this
    table, a redelivered push webhook would fire two evaluations and double
    LLM spend silently. This model rejects re-delivery at the edge in <5ms.

    Rows can be pruned after 14 days (GitHub does not replay older than that).
    """

    class Provider(models.TextChoices):
        GITHUB = "github", "GitHub"
        GITLAB = "gitlab", "GitLab"

    provider = models.CharField(max_length=20, choices=Provider.choices)
    delivery_id = models.CharField(
        max_length=100,
        help_text="X-GitHub-Delivery header or GitLab equivalent.",
    )
    event_type = models.CharField(max_length=50, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "grading_webhook_deliveries"
        unique_together = [("provider", "delivery_id")]
        indexes = [
            models.Index(fields=["received_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.provider}:{self.delivery_id}"


# ─────────────────────────────────────────────────────────────────────────────
# LLM cost metering
# ─────────────────────────────────────────────────────────────────────────────
class LLMCostLog(models.Model):
    """
    Append-only cost metering log. Internal admin dashboard only.
    Queried per docent and per class per week for the alert threshold.
    Hard ceiling is enforced at the ai_engine boundary, not here.

    Do NOT show to docents (UX decision + GDPR: cost data reveals usage patterns).
    """

    class Tier(models.TextChoices):
        CHEAP = "cheap", "Cheap tier (on-commit)"
        PREMIUM = "premium", "Premium tier (docent grading)"

    org = models.ForeignKey(
        "users.Organization",
        on_delete=models.CASCADE,
        related_name="llm_cost_logs",
    )
    docent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="llm_cost_logs",
        help_text="Null for cheap-tier background evals (no docent in the loop).",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="llm_cost_logs",
    )
    grading_session = models.ForeignKey(
        GradingSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="llm_cost_logs",
    )
    tier = models.CharField(max_length=20, choices=Tier.choices)
    model_name = models.CharField(max_length=80)
    tokens_in = models.IntegerField(default=0)
    tokens_out = models.IntegerField(default=0)
    cost_eur = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    latency_ms = models.IntegerField(null=True, blank=True)
    ceiling_rejected = models.BooleanField(
        default=False,
        help_text="True if ai_engine rejected this call due to hard per-docent daily ceiling.",
    )
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "grading_llm_cost_logs"
        indexes = [
            models.Index(fields=["docent", "occurred_at"]),
            models.Index(fields=["course", "occurred_at"]),
            models.Index(fields=["tier", "occurred_at"]),
        ]
        ordering = ["-occurred_at"]

    def __str__(self) -> str:
        return f"{self.tier}:{self.model_name} €{self.cost_eur} by {self.docent_id}"
