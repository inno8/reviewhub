"""
Pydantic schemas for request/response models.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════════
# GitHub Webhook Payloads
# ═══════════════════════════════════════════════════════════════════════════════

class GitHubCommit(BaseModel):
    """GitHub commit from push event."""
    id: str
    message: str
    timestamp: str
    author: dict
    added: list[str] = []
    removed: list[str] = []
    modified: list[str] = []


class GitHubRepository(BaseModel):
    """GitHub repository info."""
    id: int
    name: str
    full_name: str
    html_url: str
    default_branch: str


class GitHubPushEvent(BaseModel):
    """GitHub push webhook payload."""
    ref: str
    before: str
    after: str
    repository: GitHubRepository
    commits: list[GitHubCommit]
    pusher: dict
    sender: dict


# ═══════════════════════════════════════════════════════════════════════════════
# LLM Evaluation Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class Severity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
    SUGGESTION = "suggestion"


class FindingSchema(BaseModel):
    """Individual code issue."""
    title: str
    description: str
    severity: Severity = Severity.WARNING
    file_path: str
    line_start: int
    line_end: int
    original_code: str
    suggested_code: str = ""
    explanation: str = ""
    skills_affected: list[str] = Field(default_factory=list)


class EvaluationResult(BaseModel):
    """Result from LLM evaluation."""
    overall_score: float = Field(ge=0, le=100)
    findings: list[FindingSchema] = Field(default_factory=list)
    skill_scores: dict[str, float] = Field(default_factory=dict)
    summary: str = ""
    llm_model: str = ""
    tokens_used: int = 0
    processing_ms: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# Analysis Request/Response
# ═══════════════════════════════════════════════════════════════════════════════

class DiffAnalysisRequest(BaseModel):
    """Request to analyze a code diff."""
    project_id: int
    commit_sha: str
    diff: str
    file_path: str
    language: str = "unknown"
    context_files: list[dict] = Field(default_factory=list)  # Phase 3+
    user_api_key: Optional[str] = None  # User's own LLM key


class DiffAnalysisResponse(BaseModel):
    """Response from diff analysis."""
    success: bool
    evaluation: Optional[EvaluationResult] = None
    error: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
# Internal API Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class CreateEvaluationRequest(BaseModel):
    """Request to create evaluation in Django."""
    project_id: int
    commit_sha: str
    commit_message: str
    commit_timestamp: Optional[datetime] = None
    branch: str
    author_name: str
    author_email: str
    files_changed: int
    lines_added: int
    lines_removed: int
    overall_score: float
    llm_model: str
    llm_tokens_used: int
    processing_ms: int
    findings: list[dict]


class WebhookResponse(BaseModel):
    """Response to webhook request."""
    success: bool
    message: str
    evaluation_id: Optional[int] = None
    commits_processed: int = 0
