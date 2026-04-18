"""
Grading app exceptions.

Per eng review, every failure mode names its own exception class. Bare
`except Exception` is banned.
"""


class GradingError(Exception):
    """Base for all grading app errors."""


# ── LLM / rubric-grader ────────────────────────────────────────────────
class LLMError(GradingError):
    """Base for ai_engine / LLM call failures."""


class LLMTimeout(LLMError):
    """ai_engine HTTP call exceeded the 30s budget."""


class LLMRateLimit(LLMError):
    """LLM provider returned 429. Retry with backoff."""


class LLMJSONError(LLMError):
    """LLM returned a response that failed JSON schema validation."""


class LLMEmptyResponse(LLMError):
    """LLM returned empty or refusal. Surface 'grade manually' to docent."""


class LLMCeilingExceeded(LLMError):
    """Hard per-docent daily cost ceiling hit. ai_engine returned 429."""


# ── Rubric ─────────────────────────────────────────────────────────────
class RubricSchemaError(GradingError):
    """Rubric criteria JSON failed validation (at save time, not runtime)."""


# ── Diff / evaluation ──────────────────────────────────────────────────
class EmptyDiffError(GradingError):
    """Submission has no code changes to grade. Session marked skipped."""


class DiffTooLargeError(GradingError):
    """Diff exceeds our max token budget. Must truncate before LLM."""


# ── GitHub poster ──────────────────────────────────────────────────────
class GitHubError(GradingError):
    """Base for GitHub API call failures."""


class GitHubAuthExpired(GitHubError):
    """OAuth token expired. Refresh and retry."""


class PRClosedError(GitHubError):
    """PR was closed since the draft started. Abort send."""


class PartialPostError(GitHubError):
    """
    Some comments posted, then the API call chain failed.
    Session state moves to PARTIAL; Resume picks up from posted_comment_ids.
    """

    def __init__(self, posted_ids: list, failed_at: int, inner: Exception):
        self.posted_ids = posted_ids
        self.failed_at = failed_at
        self.inner = inner
        super().__init__(
            f"Posted {len(posted_ids)} comments, failed at index {failed_at}: {inner}"
        )


# ── Throttle ───────────────────────────────────────────────────────────
class ThrottleSkip(GradingError):
    """Soft throttle skip; not an error per se. Log and continue."""
