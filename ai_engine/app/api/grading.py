"""
Rubric-aware grading endpoint for Nakijken Copilot v1.

Called by Django's grading.services.rubric_grader.generate_draft().
See ~/.gstack/projects/inno8-reviewhub/yanic-main-design-20260417-175102.md.

Contract (matches the Django-side client):
  POST /api/v1/grade
  body: {
    "redacted_diff": str,
    "rubric": {"criteria": [...], "calibration": {...}},
    "context": {...},
    "tier": "premium" | "cheap",
    "docent_id": int | null,
  }
  200: { "scores": {...}, "comments": [...], "model": "...",
         "tokens_in": N, "tokens_out": N, "latency_ms": N }
  429: { "error": "ceiling_exceeded", "docent_id": ... }
  502: { "error": "llm_upstream_failed", "inner": str }

v1 notes (tech debt acknowledged):
  - Calls Anthropic directly (bypasses LLMAdapter). Refactor in v1.1 to add
    grade_with_rubric() on the adapter so OpenAI/Google/OpenClaw work too.
  - Hard per-docent daily cost ceiling is a stub in v1; the Django side does
    weekly €15 alerts. Full daily-ceiling enforcement lands in v1.1 (needs
    Redis or a dedicated cost table queried on the hot path).
  - PII redaction is done on the Django side BEFORE the payload arrives here.
    This endpoint never touches raw student identity data.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings


router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Request / response schemas
# ─────────────────────────────────────────────────────────────────────────────
class RubricCriterion(BaseModel):
    id: str
    name: str
    weight: float = 1.0
    levels: list[dict] = Field(default_factory=list)


class RubricSpec(BaseModel):
    criteria: list[RubricCriterion]
    calibration: dict = Field(default_factory=dict)


class GradeRequest(BaseModel):
    redacted_diff: str
    rubric: RubricSpec
    context: dict = Field(default_factory=dict)
    tier: str = "premium"
    docent_id: int | None = None


class CriterionScore(BaseModel):
    score: int
    evidence: str = ""


class InlineComment(BaseModel):
    file: str
    line: int
    body: str


class GradeResponse(BaseModel):
    scores: dict[str, dict]  # {criterion_id: {"score": int, "evidence": "..."}}
    comments: list[dict]
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: int


# ─────────────────────────────────────────────────────────────────────────────
# Prompt construction
# ─────────────────────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """You are a grading assistant for MBO-4 ICT teachers in the Netherlands.
Your job is to help the teacher grade a student's pull request against a rubric.

You NEVER see the student's real name, email, or GitHub handle. The student is
referred to by a pseudonym (e.g., "Student-A"). Use the pseudonym in every comment.

You produce a STRUCTURED JSON output with two parts:
  1. "scores": a score per rubric criterion, with an evidence quote from the diff.
  2. "comments": inline review comments, in the teacher's calibrated voice.

You are DRAFTING. The teacher will review and edit before sending to the student.
Be concrete, reference specific lines, and never invent code that isn't in the diff.
"""


def _build_user_prompt(req: GradeRequest) -> str:
    """
    Build the rubric-aware user prompt. Keeps the structure explicit so the
    LLM is more likely to return parseable JSON.
    """
    calibration = req.rubric.calibration or {}
    tone = calibration.get("tone", "formal")
    language = calibration.get("language", "en")
    depth = calibration.get("depth", "detailed")
    examples = calibration.get("example_comments", [])

    criteria_block = "\n".join(
        f"  - id: {c.id}\n"
        f"    name: {c.name}\n"
        f"    weight: {c.weight}\n"
        f"    levels: {json.dumps(c.levels, ensure_ascii=False)}"
        for c in req.rubric.criteria
    )

    example_block = ""
    if examples:
        example_block = "TEACHER VOICE EXAMPLES (mimic this style):\n"
        for ex in examples[:4]:
            example_block += f"  - context: {ex.get('context', '')}\n"
            example_block += f"    comment: {ex.get('comment', '')}\n"

    context_block = ""
    if req.context:
        context_block = (
            "STUDENT CONTEXT (past patterns, level; no identity):\n"
            f"  {json.dumps(req.context, ensure_ascii=False)[:1500]}\n"
        )

    return f"""RUBRIC:
{criteria_block}

CALIBRATION:
  tone: {tone}
  language: {language}
  depth: {depth}

{example_block}
{context_block}

DIFF TO GRADE:
```
{req.redacted_diff}
```

Return ONLY valid JSON matching this exact schema (no prose, no markdown fences):

{{
  "scores": {{
    "<criterion_id>": {{
      "score": <integer matching one of the rubric levels>,
      "evidence": "<short quote from the diff supporting the score>"
    }}
  }},
  "comments": [
    {{
      "file": "<file path from the diff>",
      "line": <integer line number>,
      "body": "<teacher-voiced review comment referencing the student by pseudonym>"
    }}
  ]
}}

Keep comments focused on real issues. Quality over quantity.
If language is 'nl', write comments in Dutch. If 'en', English. If 'mix', use the language of the code comments in the diff.
"""


# ─────────────────────────────────────────────────────────────────────────────
# LLM call (Anthropic direct for v1; refactor into adapter in v1.1)
# ─────────────────────────────────────────────────────────────────────────────
_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"


def _tier_to_model(tier: str) -> tuple[str, int]:
    """Return (model_name, max_tokens) for the tier."""
    if tier == "cheap":
        return ("claude-haiku-4-5", 2048)  # or claude-3-5-haiku; model name tracks provider
    return ("claude-sonnet-4-5", 4096)


async def _call_anthropic(model: str, max_tokens: int, system: str, user: str) -> dict:
    """Direct Anthropic messages call. Returns parsed response dict."""
    api_key = os.getenv("ANTHROPIC_API_KEY") or getattr(settings, "ANTHROPIC_API_KEY", None)
    if not api_key:
        raise HTTPException(
            status_code=502,
            detail={"error": "llm_upstream_failed", "inner": "No ANTHROPIC_API_KEY configured"},
        )

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": _ANTHROPIC_VERSION,
        "content-type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=28.0) as client:
            resp = await client.post(_ANTHROPIC_URL, json=payload, headers=headers)
    except httpx.TimeoutException as e:
        raise HTTPException(
            status_code=502,
            detail={"error": "llm_upstream_failed", "inner": f"timeout: {e}"},
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=502,
            detail={"error": "llm_upstream_failed", "inner": str(e)},
        )

    if resp.status_code == 429:
        raise HTTPException(
            status_code=502,
            detail={"error": "llm_upstream_failed", "inner": "rate_limited"},
        )
    if resp.status_code >= 500:
        raise HTTPException(
            status_code=502,
            detail={"error": "llm_upstream_failed", "inner": f"anthropic_{resp.status_code}"},
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail={"error": "llm_upstream_failed", "inner": resp.text[:500]},
        )

    return resp.json()


def _extract_text_from_anthropic(body: dict) -> tuple[str, int, int]:
    """Pull the text content + token counts out of an Anthropic response."""
    content_blocks = body.get("content") or []
    text_parts = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
    text = "".join(text_parts).strip()
    usage = body.get("usage") or {}
    return (
        text,
        int(usage.get("input_tokens", 0)),
        int(usage.get("output_tokens", 0)),
    )


def _parse_grade_json(text: str) -> dict:
    """
    Parse the LLM output as JSON. Tolerates extra whitespace and accidental
    markdown fences; rejects anything else.
    """
    candidate = text.strip()
    # Strip leading ```json / ```
    if candidate.startswith("```"):
        first_newline = candidate.find("\n")
        if first_newline != -1:
            candidate = candidate[first_newline + 1 :]
        if candidate.endswith("```"):
            candidate = candidate[:-3].strip()

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=502,
            detail={"error": "llm_upstream_failed", "inner": f"non_json: {e}"},
        )

    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=502,
            detail={"error": "llm_upstream_failed", "inner": "response not an object"},
        )
    if "scores" not in parsed or "comments" not in parsed:
        raise HTTPException(
            status_code=502,
            detail={"error": "llm_upstream_failed", "inner": "missing scores/comments"},
        )
    return parsed


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/grade", response_model=GradeResponse)
async def grade(request: GradeRequest) -> GradeResponse:
    """
    Rubric-aware grading. Called by Django-side grading.services.rubric_grader.

    v1 short-circuit: no hard per-docent daily cost ceiling here yet. The
    Django side logs every call to LLMCostLog and alerts when a docent's
    rolling-week cost exceeds €15. Hard daily ceiling lands in v1.1 when
    Redis is in the deploy stack.
    """
    if not request.redacted_diff.strip():
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_request", "inner": "redacted_diff is empty"},
        )

    model, max_tokens = _tier_to_model(request.tier)
    system = _SYSTEM_PROMPT
    user = _build_user_prompt(request)

    started = time.monotonic()
    body = await _call_anthropic(model, max_tokens, system, user)
    latency_ms = int((time.monotonic() - started) * 1000)

    text, tokens_in, tokens_out = _extract_text_from_anthropic(body)
    if not text:
        raise HTTPException(
            status_code=502,
            detail={"error": "llm_upstream_failed", "inner": "empty_response"},
        )

    parsed = _parse_grade_json(text)

    return GradeResponse(
        scores=parsed["scores"],
        comments=parsed["comments"],
        model=model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_ms=latency_ms,
    )
