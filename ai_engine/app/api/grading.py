"""
Rubric-aware grading endpoint for Nakijken Copilot v1.

Called by Django's grading.services.rubric_grader.generate_draft().

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

Two-tier LLM routing (v1.1+)
  "premium" → LLMAdapter(tier="quality") — uses LLM_MODEL_QUALITY env var.
              Best available model for teacher-facing rubric drafts.
  "cheap"   → LLMAdapter(tier="fast")    — uses LLM_MODEL_FAST env var.
              Lighter model; useful for cost-sensitive orgs or previews.

  The adapter is provider-agnostic: openai / anthropic / google all work.
  Configure via LLM_PROVIDER + LLM_API_KEY + LLM_MODEL_QUALITY/FAST.

Notes:
  - PII redaction is done on the Django side BEFORE the payload arrives here.
    This endpoint never touches raw student identity data.
  - Hard per-docent daily cost ceiling is a stub; Django side does weekly
    €15 alerts. Full daily-ceiling enforcement needs Redis (future).
"""
from __future__ import annotations

import json
import time

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.llm_adapter import LLMAdapter


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
    # Per-org LLM credentials forwarded by the Django backend (from
    # LLMConfiguration in the DB).  When present these take precedence over
    # the engine's own LLM_API_KEY / LLM_PROVIDER / LLM_MODEL_* env vars.
    llm_api_key: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None


class CriterionScore(BaseModel):
    score: int
    evidence: str = ""


class InlineComment(BaseModel):
    file: str
    line: int
    body: str
    # May 7 hero feature: LLM produces an exact snippet from the diff and a
    # rewritten snippet with the issue fixed. Both default to "" when the LLM
    # omits them or when the comment is general (not code-specific) — the
    # session detail UI renders empty placeholders in that case.
    original_snippet: str = ""
    suggested_snippet: str = ""


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
      "body": "<teacher-voiced review comment referencing the student by pseudonym>",
      "original_snippet": "<the exact 1-10 line code snippet from the diff this comment refers to, copied verbatim, preserving indentation; empty string if not applicable>",
      "suggested_snippet": "<the rewritten code with the issue fixed, same structure, ≤10 lines, preserving indentation; empty string if no obvious fix>"
    }}
  ]
}}

SNIPPET RULES (important — these fields drive the one-click "Commit suggestion"
button on GitHub, so accuracy matters):
  - `original_snippet` MUST be copied verbatim from the diff — same characters,
    same indentation, same whitespace. Do not paraphrase, reformat, or rename.
  - `suggested_snippet` is the minimal fix: same structure as the original,
    just with the issue resolved. Do not rename unrelated variables or change
    surrounding code. ≤10 lines.
  - If there is no obvious single-snippet fix (e.g. the issue is architectural,
    or the comment is general praise / a question), set `suggested_snippet`
    to "" (empty string).
  - If the comment is general and not pointing at specific code, set BOTH
    `original_snippet` and `suggested_snippet` to "".
  - Both snippets must be valid JSON strings: escape newlines as \\n, escape
    backslashes and double quotes.

FEW-SHOT EXAMPLES of good original/suggested pairs:

Example 1 — Python hardcoded password:
  file: "vault_cli/auth.py"
  line: 12
  body: "Student-A, hardcoding passwords in source code is a serious security vulnerability. Use an environment variable instead."
  original_snippet: "ADMIN_PASSWORD = \\"admin123\\"  # tijdelijk wachtwoord, later aanpassen"
  suggested_snippet: "ADMIN_PASSWORD = os.environ.get(\\"ADMIN_PASSWORD\\")\\nif not ADMIN_PASSWORD:\\n    raise RuntimeError(\\"Set ADMIN_PASSWORD env var\\")"

Example 2 — PHP Laravel controller missing validation:
  file: "app/Http/Controllers/UserController.php"
  line: 24
  body: "Student-A, the controller accepts raw request input. Use a FormRequest to centralize validation."
  original_snippet: "public function store(Request $request) {{\\n    $user = User::create($request->all());\\n    return redirect()->route('users.index');\\n}}"
  suggested_snippet: "public function store(StoreUserRequest $request) {{\\n    $user = User::create($request->validated());\\n    return redirect()->route('users.index');\\n}}"

Example 3 — Python bare except:
  file: "services/user_service.py"
  line: 45
  body: "Bare except swallows all errors including KeyboardInterrupt. Catch specific exceptions."
  original_snippet: "try:\\n    user = User.objects.get(id=user_id)\\nexcept:\\n    return None"
  suggested_snippet: "try:\\n    user = User.objects.get(id=user_id)\\nexcept User.DoesNotExist:\\n    return None"

Keep comments focused on real issues. Quality over quantity.
If language is 'nl', write comments in Dutch. If 'en', English. If 'mix', use the language of the code comments in the diff.
"""


# ─────────────────────────────────────────────────────────────────────────────
# LLM tier helpers
# ─────────────────────────────────────────────────────────────────────────────

def _tier_to_adapter_tier(request_tier: str) -> tuple[str, int]:
    """
    Map the request's tier field to an LLMAdapter tier + max_tokens.

    "premium" → quality tier, 4096 tokens  (teacher rubric draft — full model)
    "cheap"   → fast tier,    2048 tokens  (previews / cost-sensitive orgs)
    """
    if request_tier == "cheap":
        return ("fast", 2048)
    return ("quality", 4096)


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

    # Normalize comments: ensure original_snippet + suggested_snippet exist as
    # strings, defaulting to "" when the LLM omits them. Backward compat with
    # older prompts that only produced file/line/body.
    normalized_comments: list[dict] = []
    raw_comments = parsed.get("comments") or []
    if not isinstance(raw_comments, list):
        raise HTTPException(
            status_code=502,
            detail={"error": "llm_upstream_failed", "inner": "comments not a list"},
        )
    for c in raw_comments:
        if not isinstance(c, dict):
            # Skip malformed entries rather than failing the whole draft.
            continue
        normalized_comments.append(
            {
                **c,
                "file": str(c.get("file", "")),
                "line": c.get("line", 0),
                "body": str(c.get("body", "")),
                "original_snippet": str(c.get("original_snippet") or ""),
                "suggested_snippet": str(c.get("suggested_snippet") or ""),
            }
        )
    parsed["comments"] = normalized_comments
    return parsed


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/grade", response_model=GradeResponse)
async def grade(request: GradeRequest) -> GradeResponse:
    """
    Rubric-aware grading. Called by Django-side grading.services.rubric_grader.

    Uses LLMAdapter so the grading pipeline works with any configured
    provider (openai / anthropic / google), not just Anthropic.

    Tier mapping:
      "premium" → quality tier (LLM_MODEL_QUALITY) — default for PR reviews
      "cheap"   → fast tier    (LLM_MODEL_FAST)    — cost-saving option
    """
    if not request.redacted_diff.strip():
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_request", "inner": "redacted_diff is empty"},
        )

    adapter_tier, max_tokens = _tier_to_adapter_tier(request.tier)

    try:
        adapter = LLMAdapter(
            tier=adapter_tier,
            # Use per-org credentials when the Django backend supplies them;
            # fall through to engine env vars when they are absent.
            api_key=request.llm_api_key or None,
            provider_override=request.llm_provider or None,
            model_override=request.llm_model or None,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=502,
            detail={"error": "llm_upstream_failed", "inner": str(e)},
        )

    system = _SYSTEM_PROMPT
    user = _build_user_prompt(request)

    started = time.monotonic()
    try:
        text, tokens_in, tokens_out = await adapter.call_raw(system, user, max_tokens)
    except (httpx.TimeoutException, httpx.RequestError) as e:
        raise HTTPException(
            status_code=502,
            detail={"error": "llm_upstream_failed", "inner": f"network: {e}"},
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise HTTPException(
                status_code=502,
                detail={"error": "llm_upstream_failed", "inner": "rate_limited"},
            )
        raise HTTPException(
            status_code=502,
            detail={"error": "llm_upstream_failed", "inner": f"upstream_{e.response.status_code}"},
        )
    except ValueError as e:
        # Provider not supported for call_raw (e.g. openclaw)
        raise HTTPException(
            status_code=502,
            detail={"error": "llm_upstream_failed", "inner": str(e)},
        )
    latency_ms = int((time.monotonic() - started) * 1000)

    if not text:
        raise HTTPException(
            status_code=502,
            detail={"error": "llm_upstream_failed", "inner": "empty_response"},
        )

    parsed = _parse_grade_json(text)

    return GradeResponse(
        scores=parsed["scores"],
        comments=parsed["comments"],
        model=adapter.model_name,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_ms=latency_ms,
    )
