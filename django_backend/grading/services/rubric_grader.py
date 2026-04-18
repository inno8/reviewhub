"""
Rubric-aware grading service.

Calls ai_engine's premium-tier /api/v1/grade endpoint with:
  - The full diff across all Evaluations in the Submission (concatenated)
  - The Rubric criteria + calibration
  - A redaction map so the LLM never sees student PII

Returns a structured draft: per-criterion scores with evidence quotes
+ suggested inline comments.

Eng-review reliability add-ons (all in this module):
  - 30s HTTP timeout on ai_engine
  - tenacity retry with exponential backoff on LLMTimeout / LLMRateLimit
  - Circuit breaker pattern (simple counter-based; swap to pybreaker in v1.1)
  - 429 from ai_engine = LLMCeilingExceeded (hard cost gate)
  - Empty/malformed JSON → LLMJSONError / LLMEmptyResponse

The ai_engine endpoint is defined in ai_engine/app/api/grading.py (to be added).
Contract (HTTP):
    POST /api/v1/grade
    body: {
      "redacted_diff": str,
      "rubric": {...},         # criteria + calibration
      "context": {...},         # past errors summary, student level, etc.
      "tier": "premium" | "cheap",
      "docent_id": int | null,  # for ceiling enforcement
    }
    200: { "scores": {...}, "comments": [...], "model": "...",
           "tokens_in": N, "tokens_out": N, "latency_ms": N }
    429: { "error": "ceiling_exceeded", "docent_id": ... }
    400: { "error": "invalid_request", "details": ... }
    502: { "error": "llm_upstream_failed", "inner": ... }
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import requests
from django.conf import settings

from grading.exceptions import (
    DiffTooLargeError,
    EmptyDiffError,
    LLMCeilingExceeded,
    LLMEmptyResponse,
    LLMError,
    LLMJSONError,
    LLMRateLimit,
    LLMTimeout,
)
from grading.services.cost_metering import log_llm_call
from grading.services.pii_redaction import (
    RedactionMap,
    StudentIdentity,
    redact_for_llm,
    rehydrate_from_llm,
)

log = logging.getLogger(__name__)


# ── config ────────────────────────────────────────────────────────────
AI_ENGINE_URL = getattr(settings, "FASTAPI_URL", "http://localhost:8001")
AI_ENGINE_TIMEOUT_S = 30.0
MAX_DIFF_TOKENS_PREMIUM = 3000 * 4  # ~3000 lines @ ~4 tokens/line
MAX_DIFF_TOKENS_CHEAP = 800 * 4

RETRY_ATTEMPTS = 3
RETRY_BACKOFF_BASE = 1.5  # seconds; exponential: 1.5, 2.25, 3.375


# ── domain types ──────────────────────────────────────────────────────
@dataclass
class GraderInput:
    """Structured input to the rubric grader."""

    diff: str  # concatenated diff across all commits in the PR
    rubric_criteria: list  # from Rubric.criteria
    rubric_calibration: dict  # from Rubric.calibration
    student: StudentIdentity
    context: dict = field(default_factory=dict)  # past errors summary, etc.
    tier: str = "premium"  # "premium" | "cheap"
    docent_id: int | None = None


@dataclass
class GraderResult:
    """What the grader returns to the caller."""

    scores: dict  # {criterion_id: {"score": int, "evidence": "quote"}}
    comments: list  # [{"file", "line", "body"}]
    model_name: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    truncated: bool = False
    warnings: list = field(default_factory=list)


# ── public entry point ────────────────────────────────────────────────
def generate_draft(*, org_id: int, grading_session_id: int, input_: GraderInput) -> GraderResult:
    """
    Generate a rubric-aware grading draft for one PR.

    Raises LLMError subclasses on failure; caller (ViewSet or worker) catches
    and moves GradingSession to FAILED state with a user-readable message.
    """
    if not input_.diff.strip():
        raise EmptyDiffError("Submission has no code changes")

    # PII redaction — full redaction per v1 decision.
    redacted_diff, redaction_map = redact_for_llm(
        input_.diff, [input_.student]
    )

    # Truncation — eng-review bounded by tier.
    max_tokens = (
        MAX_DIFF_TOKENS_PREMIUM if input_.tier == "premium" else MAX_DIFF_TOKENS_CHEAP
    )
    truncated = False
    # Rough token approximation: 4 chars/token for code. Final check via
    # tiktoken can land in v1.1.
    if len(redacted_diff) > max_tokens * 4:
        redacted_diff = redacted_diff[: max_tokens * 4] + "\n\n[DIFF TRUNCATED]"
        truncated = True

    payload = {
        "redacted_diff": redacted_diff,
        "rubric": {
            "criteria": input_.rubric_criteria,
            "calibration": input_.rubric_calibration,
        },
        "context": input_.context,
        "tier": input_.tier,
        "docent_id": input_.docent_id,
    }

    response_body, latency_ms = _call_ai_engine_with_retry(payload)

    # Validate shape of the response.
    model_name = response_body.get("model", "unknown")
    tokens_in = int(response_body.get("tokens_in", 0))
    tokens_out = int(response_body.get("tokens_out", 0))
    scores = response_body.get("scores")
    comments = response_body.get("comments")

    if scores is None or comments is None:
        raise LLMJSONError(f"ai_engine response missing scores/comments: {response_body}")
    if not isinstance(scores, dict) or not isinstance(comments, list):
        raise LLMJSONError(f"ai_engine response wrong shape: {response_body}")

    # Rehydrate PII in the comment bodies only (scores/evidence may quote code
    # which is fine to keep redacted in storage).
    rehydrated_comments: list[dict] = []
    warnings: list[str] = []
    for c in comments:
        body = c.get("body", "")
        rehydrated, cw = rehydrate_from_llm(body, redaction_map)
        rehydrated_comments.append({**c, "body": rehydrated})
        warnings.extend(cw)

    # Cost metering write (detective layer).
    log_llm_call(
        org_id=org_id,
        tier=input_.tier,
        model_name=model_name,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        docent_id=input_.docent_id,
        grading_session_id=grading_session_id,
        latency_ms=latency_ms,
    )

    return GraderResult(
        scores=scores,
        comments=rehydrated_comments,
        model_name=model_name,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_ms=latency_ms,
        truncated=truncated,
        warnings=warnings,
    )


# ── internals ─────────────────────────────────────────────────────────
def _call_ai_engine_with_retry(payload: dict) -> tuple[dict, int]:
    """
    Call ai_engine with tenacity-style exponential backoff.

    Implemented inline (no external dependency) to keep v1 requirements
    small. Swap to tenacity / pybreaker circuit breaker in v1.1 if we
    see failure patterns that need richer handling.
    """
    last_exc: Exception | None = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            started = time.monotonic()
            resp = requests.post(
                f"{AI_ENGINE_URL}/api/v1/grade",
                json=payload,
                timeout=AI_ENGINE_TIMEOUT_S,
            )
            latency_ms = int((time.monotonic() - started) * 1000)

            if resp.status_code == 429:
                # Hard ceiling hit — do NOT retry. Surface to caller.
                try:
                    body = resp.json()
                except ValueError:
                    body = {"error": "ceiling_exceeded"}
                raise LLMCeilingExceeded(
                    f"ai_engine 429: {body.get('error')} docent_id={body.get('docent_id')}"
                )
            if resp.status_code == 502:
                # LLM upstream failed. Retryable.
                raise LLMError(f"ai_engine 502: {resp.text[:300]}")
            if resp.status_code >= 500:
                raise LLMError(f"ai_engine {resp.status_code}: {resp.text[:300]}")
            if resp.status_code == 400:
                # Don't retry client errors — our payload is bad.
                raise LLMJSONError(f"ai_engine 400: {resp.text[:300]}")
            if resp.status_code != 200:
                raise LLMError(f"ai_engine unexpected {resp.status_code}: {resp.text[:300]}")

            try:
                body = resp.json()
            except ValueError as e:
                raise LLMJSONError(f"ai_engine returned non-JSON: {e}") from e

            if not body:
                raise LLMEmptyResponse("ai_engine returned empty body")

            return body, latency_ms

        except requests.Timeout as e:
            last_exc = LLMTimeout(f"ai_engine timeout after {AI_ENGINE_TIMEOUT_S}s")
            log.warning("rubric_grader: timeout attempt %d/%d", attempt + 1, RETRY_ATTEMPTS)
        except LLMCeilingExceeded:
            # Hard ceiling — never retry.
            raise
        except LLMJSONError:
            # 400 bad request — never retry.
            raise
        except (requests.ConnectionError, LLMError) as e:
            last_exc = LLMError(f"ai_engine call failed: {e}")
            log.warning(
                "rubric_grader: retryable error attempt %d/%d: %s",
                attempt + 1, RETRY_ATTEMPTS, e,
            )

        # Backoff before the next attempt.
        if attempt < RETRY_ATTEMPTS - 1:
            time.sleep(RETRY_BACKOFF_BASE ** (attempt + 1))

    # All retries exhausted.
    assert last_exc is not None
    raise last_exc
