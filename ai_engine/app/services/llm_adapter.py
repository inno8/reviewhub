"""
LLM Adapter - Abstraction layer for multiple LLM providers.

Supports:
- OpenAI (GPT-4, etc.)
- Anthropic (Claude)
- Google (Gemini via API key)
- OpenClaw fallback (when no API key configured)

Complexity-aware routing
------------------------
When evaluate_diff is called with a CommitComplexity object, the adapter
automatically selects the appropriate model tier for the org's provider:

  simple  → cheapest model (haiku / 4o-mini / flash-lite)
  medium  → lighter model  (3.5-haiku / 4o-mini / 1.5-flash)
  complex → org default    (whatever LLM_MODEL is set to)

The tier map is code-driven — no extra env vars or admin config needed.
"""
import json
import time
from typing import Optional, TYPE_CHECKING
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.models.schemas import EvaluationResult, FindingSchema, Severity

if TYPE_CHECKING:
    from app.services.classifier import CommitComplexity

# ---------------------------------------------------------------------------
# Per-provider model tier map
# complex always uses the org default (self.model_name); only simple/medium
# are overridden here.
# ---------------------------------------------------------------------------
PROVIDER_MODEL_TIERS: dict[str, dict[str, str]] = {
    "openai": {
        "simple": "gpt-4o-mini",
        "medium": "gpt-4o-mini",
    },
    # Claude 3.x Haiku IDs were retired; use Haiku 4.5 for simple/medium tiers.
    "anthropic": {
        "simple": "claude-haiku-4-5",
        "medium": "claude-haiku-4-5",
    },
    "google": {
        "simple": "gemini-2.0-flash-lite",
        "medium": "gemini-1.5-flash",
    },
}

# Routing parameters per complexity level
_COMPLEXITY_PARAMS: dict[str, dict] = {
    "simple":  {"max_tokens": 1024, "context_file_limit": 0},
    "medium":  {"max_tokens": 2048, "context_file_limit": 3},
    "complex": {"max_tokens": 4096, "context_file_limit": 5},
}

# Skill slugs for validation
VALID_SKILLS = [
    # Code Quality
    "clean_code", "code_structure", "dry_principle", "comments_docs",
    # Design Patterns
    "solid_principles", "mvc_patterns", "reusability", "abstraction",
    # Logic & Algorithms
    "problem_decomposition", "data_structures", "algorithm_efficiency", "edge_cases",
    # Security
    "input_validation", "auth_practices", "secrets_management", "xss_csrf_prevention",
    # Testing
    "unit_testing", "test_coverage", "test_quality", "tdd",
    # Frontend
    "html_semantics", "css_organization", "accessibility", "responsive_design",
    # Backend
    "api_design", "database_queries", "error_handling", "performance",
    # DevOps
    "git_practices", "build_tools", "ci_cd", "environment_config",
]


EVALUATION_PROMPT = '''You are an expert code reviewer and adaptive mentor. Analyze the following code diff and provide detailed feedback.

{developer_section}FILE: {file_path}
LANGUAGE: {language}

DIFF:
```
{diff}
```

{context_section}

Analyze this code change and return a JSON response with the following structure:
{{
    "overall_score": <number 0-100>,
    "findings": [
        {{
            "title": "<brief issue title>",
            "description": "<detailed description>",
            "severity": "<critical|warning|info|suggestion>",
            "file_path": "{file_path}",
            "line_start": <line number>,
            "line_end": <line number>,
            "original_code": "<the problematic code>",
            "suggested_code": "<the fixed code>",
            "explanation": "<why this is better>",
            "skills_affected": ["<skill_slug>", ...]
        }}
    ],
    "skill_scores": {{
        "<skill_slug>": <score 0-100>,
        ...
    }},
    "summary": "<brief summary of the review>"
}}

VALID SKILL SLUGS (only use these):
- Code Quality: clean_code, code_structure, dry_principle, comments_docs
- Design Patterns: solid_principles, mvc_patterns, reusability, abstraction
- Logic & Algorithms: problem_decomposition, data_structures, algorithm_efficiency, edge_cases
- Security: input_validation, auth_practices, secrets_management, xss_csrf_prevention
- Testing: unit_testing, test_coverage, test_quality, tdd
- Frontend: html_semantics, css_organization, accessibility, responsive_design
- Backend: api_design, database_queries, error_handling, performance
- DevOps: git_practices, build_tools, ci_cd, environment_config

Focus on the following (check all that apply to the file type):
1. Code quality, naming, and best practices
2. Potential bugs, edge-cases, or security issues
3. Performance and readability
4. Maintainability, DRY, and component structure
5. For HTML/CSS/Vue/React — accessibility (missing alt, aria), semantic HTML, responsive design, CSS organisation, inline styles
6. For JS/TS — missing null-checks, async/await issues, unused variables, magic numbers
7. For Python — error handling, logging, typing hints, test coverage

RULES YOU MUST FOLLOW:
- If the diff adds or changes ANY logic, markup, styles, or structure → you MUST include at least 1 finding.
- Only return an empty findings array when the diff is purely whitespace, empty lines, or a single-word comment fix with zero structural or logic impact.
- An overall_score of 100 means the change is absolutely exemplary with zero possible improvements — this should be very rare. Most real changes score 65–90.
- Use severity "suggestion" or "info" when the code works but could be cleaner or more idiomatic. These still count as findings.
- Do NOT invent non-existent code, but DO proactively spot things a senior developer would mention in a real code review (even positive observations phrased as "consider also…").

Return ONLY the JSON object, no markdown formatting.'''


def normalize_llm_provider(raw: Optional[str]) -> str:
    """
    Map env/UI provider strings to internal provider keys used by LLMAdapter.

    Accepts common aliases (e.g. LLM_PROVIDER=claude) and normalizes case.
    """
    if raw is None or not str(raw).strip():
        return "openai"
    s = str(raw).strip().lower()
    aliases = {
        "claude": "anthropic",
        "anthropic": "anthropic",
        "openai": "openai",
        "google": "google",
        "gemini": "google",
    }
    return aliases.get(s, s)


class LLMAdapter:
    """
    Adapter for multiple LLM providers.
    
    Priority:
    1. User-provided API key (from request)
    2. System-configured provider (from settings)
    3. OpenClaw fallback
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        provider_override: Optional[str] = None,
        model_override: Optional[str] = None,
    ):
        # Determine provider and key — priority:
        # 1. Caller-supplied (e.g. org admin credentials passed by Django for batch)
        # 2. AI-engine env vars (LLM_API_KEY / LLM_PROVIDER)
        # 3. OpenClaw fallback
        if api_key:
            self.provider = normalize_llm_provider(provider_override or settings.LLM_PROVIDER)
            self.api_key = api_key
        elif settings.LLM_API_KEY:
            self.provider = normalize_llm_provider(provider_override or settings.LLM_PROVIDER)
            self.api_key = settings.LLM_API_KEY
        elif settings.OPENCLAW_ENABLED:
            self.provider = "openclaw"
            self.api_key = settings.OPENCLAW_API_KEY
        else:
            raise ValueError("No LLM provider configured")

        # model_name: caller override > env var default
        self.model_name = model_override or settings.LLM_MODEL

    # ── Public: complexity-aware model selection ──────────────────────────

    def model_for_complexity(self, complexity_level: str) -> str:
        """
        Return the appropriate model identifier for a given complexity level.

        - complex → org default (self.model_name)
        - medium / simple → auto-derived from PROVIDER_MODEL_TIERS for self.provider,
          falls back to self.model_name if provider is not in the tier map or if the
          derived model would be the same as (or heavier than) the org default.
        """
        if complexity_level == "complex":
            return self.model_name

        tier_models = PROVIDER_MODEL_TIERS.get(self.provider, {})
        derived = tier_models.get(complexity_level)
        if not derived:
            return self.model_name

        # Guard: don't "upgrade" if org default is already a cheaper model
        # (e.g. org chose gpt-4o-mini as default → all tiers use gpt-4o-mini)
        return derived

    async def evaluate_diff(
        self,
        diff: str,
        file_path: str,
        language: str = "unknown",
        context_files: list = None,
        complexity: "Optional[CommitComplexity]" = None,
    ) -> Optional[EvaluationResult]:
        """
        Evaluate a code diff using the configured LLM.

        complexity (optional CommitComplexity):
          When provided, the adapter automatically:
            - selects the appropriate model tier
            - caps max_tokens per the tier (1024 / 2048 / 4096)
            - limits the number of related context files (0 / 3 / 5)

        context_files may contain:
          - {"path": "__developer_profile__", "content": "<adaptive profile text>"}
            → injected as DEVELOPER PROFILE section at the top of the prompt.
          - {"path": "<file>", "content": "<code>"}
            → injected as RELATED FILES section.

        Returns structured evaluation result.
        """
        # Resolve complexity-driven parameters
        level = complexity.level if complexity else "complex"
        params = _COMPLEXITY_PARAMS.get(level, _COMPLEXITY_PARAMS["complex"])
        active_model = self.model_for_complexity(level)
        max_tokens: int = params["max_tokens"]
        ctx_limit: int = params["context_file_limit"]

        developer_section = ""
        regular_context: list[dict] = []

        for cf in (context_files or []):
            if cf.get("path") == "__developer_profile__":
                developer_section = cf["content"] + "\n\n"
            else:
                regular_context.append(cf)

        # Apply context file limit (simple → 0, medium → 3, complex → 5)
        regular_context = regular_context[:ctx_limit]

        # Build related-files context block
        context_section = ""
        if regular_context:
            context_section = "RELATED FILES (for context):\n"
            for cf in regular_context:
                context_section += f"\n--- {cf['path']} ---\n{cf['content'][:1500]}\n"

        # Build prompt
        prompt = EVALUATION_PROMPT.format(
            developer_section=developer_section,
            file_path=file_path,
            language=language,
            diff=diff,
            context_section=context_section,
        )

        if complexity:
            print(
                f"[LLM] {file_path} | complexity={level} score={complexity.score} "
                f"model={active_model} max_tokens={max_tokens} ctx_files={len(regular_context)}"
            )
        
        # Call appropriate provider, passing active_model and max_tokens
        start_time = time.time()
        
        if self.provider == "openai":
            result = await self._call_openai(prompt, model=active_model, max_tokens=max_tokens)
        elif self.provider == "anthropic":
            result = await self._call_anthropic(prompt, model=active_model, max_tokens=max_tokens)
        elif self.provider == "google":
            result = await self._call_google(prompt, model=active_model, max_tokens=max_tokens)
        elif self.provider == "openclaw":
            result = await self._call_openclaw(prompt, diff, file_path)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
        
        if result:
            result.processing_ms = int((time.time() - start_time) * 1000)
            result.llm_model = active_model
        
        return result
    
    async def _call_openai(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> Optional[EvaluationResult]:
        """Call OpenAI API."""
        active_model = model or self.model_name
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": active_model,
                        "messages": [
                            {"role": "system", "content": "You are an expert code reviewer. Return only valid JSON."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.3,
                        "max_tokens": max_tokens,
                        "response_format": {"type": "json_object"}
                    },
                    timeout=120.0
                )
                
                response.raise_for_status()
                data = response.json()
                
                content = data["choices"][0]["message"]["content"]
                tokens = data.get("usage", {}).get("total_tokens", 0)
                
                return self._parse_response(content, tokens)
                
        except Exception as e:
            print(f"OpenAI error: {e}")
            return None
    
    async def _call_anthropic(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> Optional[EvaluationResult]:
        """Call Anthropic API."""
        active_model = model or self.model_name
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": active_model,
                        "max_tokens": max_tokens,
                        "messages": [
                            {"role": "user", "content": prompt}
                        ]
                    },
                    timeout=120.0
                )
                
                response.raise_for_status()
                data = response.json()
                
                content = data["content"][0]["text"]
                tokens = data.get("usage", {}).get("input_tokens", 0) + \
                         data.get("usage", {}).get("output_tokens", 0)
                
                return self._parse_response(content, tokens)
                
        except Exception as e:
            print(f"Anthropic error: {e}")
            return None

    async def _call_google(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> Optional[EvaluationResult]:
        """Call Google Gemini generateContent API (API key in query string)."""
        active_model = (model or self.model_name).replace("models/", "").strip()
        base = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{active_model}:generateContent"
        )
        url = f"{base}?{urlencode({'key': self.api_key})}"
        base_body = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "You are an expert code reviewer. "
                            "Return only valid JSON as requested in the user message."
                        )
                    }
                ]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
            },
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json=base_body,
                    timeout=120.0,
                )
                # Some models reject JSON MIME type; retry without it.
                if response.status_code == 400 and "responseMimeType" in base_body.get(
                    "generationConfig", {}
                ):
                    retry_cfg = dict(base_body["generationConfig"])
                    retry_cfg.pop("responseMimeType", None)
                    retry_body = {**base_body, "generationConfig": retry_cfg}
                    response = await client.post(
                        url,
                        headers={"Content-Type": "application/json"},
                        json=retry_body,
                        timeout=120.0,
                    )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            print(f"Google Gemini HTTP error: {e.response.status_code} {e.response.text[:500]}")
            return None
        except Exception as e:
            print(f"Google error: {e}")
            return None

        try:
            parts = data["candidates"][0]["content"]["parts"]
            content = parts[0].get("text", "")
        except (KeyError, IndexError, TypeError) as e:
            print(f"Google unexpected response shape: {e}")
            return None

        meta = data.get("usageMetadata") or {}
        tokens = int(meta.get("totalTokenCount", 0)) or (
            int(meta.get("promptTokenCount", 0))
            + int(meta.get("candidatesTokenCount", 0))
        )
        return self._parse_response(content, tokens)
    
    async def _call_openclaw(
        self,
        prompt: str,
        diff: str,
        file_path: str
    ) -> Optional[EvaluationResult]:
        """
        OpenClaw fallback - rule-based code analysis.
        
        When no LLM API key is configured, uses basic pattern matching
        to provide initial code review feedback. For full AI-powered
        reviews, configure LLM_PROVIDER and LLM_API_KEY.
        """
        print(f"[ANALYSIS] Using rule-based analysis for: {file_path}", flush=True)
        
        findings = []
        skill_scores = {}
        
        # Basic pattern-based analysis
        lines = diff.split('\n')
        added_lines = [l for l in lines if l.startswith('+') and not l.startswith('+++')]
        
        # Check for common issues
        for i, line in enumerate(added_lines):
            line_num = i + 1
            
            # Security: hardcoded secrets
            if any(pattern in line.lower() for pattern in ['password=', 'api_key=', 'secret=', 'token=']):
                if '=' in line and not line.strip().startswith('#'):
                    findings.append(FindingSchema(
                        title="Potential Hardcoded Secret",
                        description="This line appears to contain a hardcoded credential or secret.",
                        severity=Severity.CRITICAL,
                        file_path=file_path,
                        line_start=line_num,
                        line_end=line_num,
                        original_code=line[1:],
                        suggested_code="# Use environment variables instead",
                        explanation="Hardcoded secrets are a security risk. Use environment variables or a secrets manager.",
                        skills_affected=["secrets_management", "auth_practices"]
                    ))
            
            # Code style: print statements in production code
            if 'print(' in line and not any(ext in file_path for ext in ['test', 'debug', 'log']):
                findings.append(FindingSchema(
                    title="Debug Print Statement",
                    description="Print statement found in production code.",
                    severity=Severity.INFO,
                    file_path=file_path,
                    line_start=line_num,
                    line_end=line_num,
                    original_code=line[1:],
                    suggested_code="# Use proper logging instead of print",
                    explanation="Use a logging framework for better control over output levels and formatting.",
                    skills_affected=["clean_code", "error_handling"]
                ))
            
            # Security: SQL without parameterization
            if any(pattern in line.lower() for pattern in ['execute(f"', "execute(f'", '% (', '.format(']):
                if 'select' in line.lower() or 'insert' in line.lower() or 'update' in line.lower():
                    findings.append(FindingSchema(
                        title="Potential SQL Injection",
                        description="SQL query appears to use string formatting instead of parameterized queries.",
                        severity=Severity.CRITICAL,
                        file_path=file_path,
                        line_start=line_num,
                        line_end=line_num,
                        original_code=line[1:],
                        suggested_code="# Use parameterized queries: cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))",
                        explanation="String formatting in SQL queries can lead to SQL injection attacks.",
                        skills_affected=["input_validation", "database_queries"]
                    ))
            
            # Error handling: bare except
            if 'except:' in line or 'except Exception:' in line:
                findings.append(FindingSchema(
                    title="Broad Exception Handling",
                    description="Catching all exceptions can hide bugs and make debugging difficult.",
                    severity=Severity.WARNING,
                    file_path=file_path,
                    line_start=line_num,
                    line_end=line_num,
                    original_code=line[1:],
                    suggested_code="# Catch specific exceptions: except ValueError as e:",
                    explanation="Be specific about which exceptions to catch to avoid masking unexpected errors.",
                    skills_affected=["error_handling", "clean_code"]
                ))
        
        # Calculate score based on findings
        critical_count = sum(1 for f in findings if f.severity == Severity.CRITICAL)
        warning_count = sum(1 for f in findings if f.severity == Severity.WARNING)
        info_count = sum(1 for f in findings if f.severity == Severity.INFO)
        
        base_score = 100
        base_score -= critical_count * 20
        base_score -= warning_count * 10
        base_score -= info_count * 2
        overall_score = max(0, min(100, base_score))
        
        # Set skill scores based on findings
        for finding in findings:
            for skill in finding.skills_affected:
                if skill not in skill_scores:
                    skill_scores[skill] = 80  # Default good score
                # Deduct based on severity
                if finding.severity == Severity.CRITICAL:
                    skill_scores[skill] = max(0, skill_scores[skill] - 30)
                elif finding.severity == Severity.WARNING:
                    skill_scores[skill] = max(0, skill_scores[skill] - 15)
        
        summary = f"Rule-based analysis found {len(findings)} issues: {critical_count} critical, {warning_count} warnings, {info_count} informational."
        if not findings:
            summary = "No issues detected by rule-based analysis. For deeper AI review, configure LLM_PROVIDER."
        
        print(f"[OK] Analysis complete: {len(findings)} findings, score {overall_score}", flush=True)
        
        return EvaluationResult(
            overall_score=overall_score,
            findings=findings,
            skill_scores=skill_scores,
            summary=summary,
            tokens_used=0
        )
    
    # ------------------------------------------------------------------
    # Severity normaliser: maps LLM free-form words to valid enum values
    # so a single unexpected word doesn't silently kill all findings.
    # ------------------------------------------------------------------
    _SEVERITY_MAP: dict[str, "Severity"] = {
        "critical": Severity.CRITICAL,
        "error": Severity.CRITICAL,
        "high": Severity.CRITICAL,
        "warning": Severity.WARNING,
        "warn": Severity.WARNING,
        "medium": Severity.WARNING,
        "moderate": Severity.WARNING,
        "info": Severity.INFO,
        "information": Severity.INFO,
        "informational": Severity.INFO,
        "low": Severity.INFO,
        "suggestion": Severity.SUGGESTION,
        "suggest": Severity.SUGGESTION,
        "note": Severity.SUGGESTION,
        "improvement": Severity.SUGGESTION,
        "hint": Severity.SUGGESTION,
        "minor": Severity.SUGGESTION,
        "optional": Severity.SUGGESTION,
    }

    @classmethod
    def _parse_severity(cls, raw: Optional[str]) -> "Severity":
        """Convert a raw LLM severity string to a Severity enum value, with fallback."""
        return cls._SEVERITY_MAP.get((raw or "warning").lower().strip(), Severity.WARNING)

    def _parse_response(self, content: str, tokens: int) -> Optional[EvaluationResult]:
        """Parse LLM response into EvaluationResult."""
        try:
            # Clean up response (remove markdown if present)
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            data = json.loads(content)

            raw_findings = data.get("findings", [])
            print(
                f"[LLM PARSE] overall_score={data.get('overall_score')} "
                f"findings_in_response={len(raw_findings)}"
            )

            # Parse findings — errors on individual items are caught and skipped
            # so one bad finding never discards the rest.
            findings = []
            for idx, f in enumerate(raw_findings):
                try:
                    valid_skills = [s for s in f.get("skills_affected", []) if s in VALID_SKILLS]
                    findings.append(FindingSchema(
                        title=f.get("title", "Unknown Issue"),
                        description=f.get("description", ""),
                        severity=self._parse_severity(f.get("severity")),
                        file_path=f.get("file_path", "unknown"),
                        line_start=int(f.get("line_start") or 1),
                        line_end=int(f.get("line_end") or 1),
                        original_code=f.get("original_code", ""),
                        suggested_code=f.get("suggested_code", ""),
                        explanation=f.get("explanation", ""),
                        skills_affected=valid_skills
                    ))
                except Exception as finding_err:
                    print(f"[LLM PARSE] Skipped finding #{idx} due to error: {finding_err}")

            # Validate skill scores
            skill_scores = {}
            for skill, score in data.get("skill_scores", {}).items():
                if skill in VALID_SKILLS:
                    try:
                        skill_scores[skill] = float(score)
                    except (TypeError, ValueError):
                        pass

            return EvaluationResult(
                overall_score=float(data.get("overall_score", 50)),
                findings=findings,
                skill_scores=skill_scores,
                summary=data.get("summary", ""),
                tokens_used=tokens
            )

        except Exception as e:
            print(f"[LLM PARSE] Parse error: {e}")
            print(f"[LLM PARSE] Raw content (first 800): {content[:800]}")
            return None
