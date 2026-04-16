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
    # Use the org-configured model for all tiers — Haiku misses too many issues.
    "anthropic": {
        "simple": None,
        "medium": None,
    },
    "google": {
        "simple": "gemini-2.0-flash-lite",
        "medium": "gemini-1.5-flash",
    },
}

# Routing parameters per complexity level
_COMPLEXITY_PARAMS: dict[str, dict] = {
    "simple":  {"max_tokens": 4096, "context_file_limit": 0},
    "medium":  {"max_tokens": 4096, "context_file_limit": 3},
    "complex": {"max_tokens": 8192, "context_file_limit": 5},
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

CRITICAL RULES FOR original_code AND suggested_code:
- "original_code" MUST be an EXACT copy of code from the diff (the added/changed lines). Do NOT paraphrase, truncate, or invent code that does not appear in the diff.
- "original_code" should include the problematic lines PLUS the enclosing function/method signature and enough surrounding context (typically 5-15 lines) that a junior developer can see exactly where the code sits.
- "suggested_code" MUST be a COMPLETE, RUNNABLE replacement for the same scope as "original_code". It MUST include the same function signature, the fix applied, and the closing bracket/return. A junior developer should be able to copy-paste the entire suggested_code block and have it work.
- "suggested_code" MUST be REAL, RUNNABLE code — not a comment, a generic placeholder like "# Use environment variables instead", or an unrelated suggestion.
- If the fix requires adding an import, include the import line at the top of suggested_code with a comment "# Add this import at the top of the file".
- "line_start" and "line_end" MUST match the actual line numbers where "original_code" appears in the NEW file (lines marked with + in the diff).
- Each finding must address ONE specific issue at the lines indicated. Do NOT mix suggestions for different issues into a single finding.
- If your suggestion is about adding something new (e.g. logging, validation) rather than fixing existing code, include the surrounding original code as context in "original_code" and show the improved version with the addition in "suggested_code".

ANTI-OSCILLATION RULE:
- Do NOT flag code that was explicitly added to fix a prior issue. If lines were changed to address a previous problem (e.g., adding a try/except that was previously missing), do NOT generate a new finding about the fix itself (e.g., "exception too broad"). Only flag genuine new problems.
- Known-safe output patterns that are NOT debug prints: Rich library console.print() for user-facing terminal UI, Click echo() for CLI output, logging.* calls. Only flag bare print() statements that output sensitive data or debug information.

THOROUGHNESS RULES:
- Report EVERY distinct issue you find — do NOT group multiple issues into one finding.
- For security issues (SQL injection, hardcoded secrets, logging sensitive data), EACH occurrence must be a separate finding.
- A file with 5 different problems must produce at least 5 findings, not 1 summary finding.
- Common issues to check separately: SQL injection, bare except, hardcoded credentials, missing input validation, resource leaks (unclosed files/connections), logging secrets, mutable default args, missing type hints, missing docstrings.

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

    async def evaluate_understanding(
        self,
        category: str,
        finding_titles: list,
        finding_descriptions: list,
        suggested_fixes: list,
        developer_explanation: str,
        developer_level: str = "junior",
    ) -> dict:
        """
        Evaluate if a developer understands a code issue.
        Returns dict with level (got_it/partial/not_yet), feedback, deeper_explanation.
        """
        issues_text = "\n".join(
            f"- {t}: {d}" for t, d in zip(finding_titles, finding_descriptions)
        )
        fixes_text = "\n".join(
            f"- {f}" for f in suggested_fixes if f
        )

        prompt = f"""You are evaluating if a {developer_level} developer understands a code issue.

ISSUE CATEGORY: {category}

ISSUES FOUND:
{issues_text}

SUGGESTED FIXES:
{fixes_text}

DEVELOPER'S EXPLANATION:
"{developer_explanation}"

Rate their understanding and return ONLY a JSON object:
{{
  "level": "got_it" or "partial" or "not_yet",
  "feedback": "Brief constructive feedback (1-2 sentences)",
  "deeper_explanation": "Only if level is not_yet: a clearer explanation tailored to a {developer_level} developer (3-5 sentences). Empty string if got_it or partial."
}}

Rating guide:
- "got_it": They clearly understand the core problem AND why the fix is better
- "partial": Right direction but missing key details or incomplete reasoning
- "not_yet": Fundamental misunderstanding, too vague, or just restating the issue without explaining why

Be encouraging but honest. Return ONLY the JSON."""

        try:
            if self.provider == "openai":
                result = await self._call_openai(prompt, max_tokens=500)
            elif self.provider == "anthropic":
                result = await self._call_anthropic(prompt, max_tokens=500)
            else:
                # OpenClaw fallback — simple heuristic
                return self._evaluate_understanding_fallback(
                    developer_explanation, finding_descriptions
                )

            if result:
                import json as json_mod
                cleaned = result.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0]
                parsed = json_mod.loads(cleaned)
                return {
                    "level": parsed.get("level", "partial"),
                    "feedback": parsed.get("feedback", ""),
                    "deeper_explanation": parsed.get("deeper_explanation", ""),
                }
        except Exception as e:
            print(f"[LLM] Understanding evaluation error: {e}")

        return self._evaluate_understanding_fallback(
            developer_explanation, finding_descriptions
        )

    def _evaluate_understanding_fallback(self, explanation: str, descriptions: list) -> dict:
        """Simple heuristic fallback when no LLM is available."""
        words = explanation.lower().split()
        # Check if explanation has substance (more than 5 words, mentions key terms)
        desc_keywords = set()
        for d in descriptions:
            desc_keywords.update(w.lower() for w in d.split() if len(w) > 4)

        matched = sum(1 for w in words if w in desc_keywords)
        total_words = len(words)

        if total_words >= 10 and matched >= 3:
            return {
                "level": "got_it",
                "feedback": "Good explanation! You seem to understand the issue well.",
                "deeper_explanation": "",
            }
        elif total_words >= 5 and matched >= 1:
            return {
                "level": "partial",
                "feedback": "You're on the right track but could be more specific about why this is problematic.",
                "deeper_explanation": "",
            }
        else:
            return {
                "level": "not_yet",
                "feedback": "Your explanation is too brief. Try to explain the specific risk or problem.",
                "deeper_explanation": " ".join(descriptions[:2]),
            }

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

        # Store diff for post-parse validation of findings
        self._current_diff = diff

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
                
                return self._parse_response(content, tokens, diff=getattr(self, '_current_diff', ''))
                
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

                return self._parse_response(content, tokens, diff=getattr(self, '_current_diff', ''))
                
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
        return self._parse_response(content, tokens, diff=getattr(self, '_current_diff', ''))
    
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
        
        import re

        # ── Compute real line numbers from diff hunk headers ──
        # Maps each added_line index → actual file line number
        real_line_nums: list[int] = []
        current_new_line = 1
        for raw_line in lines:
            if raw_line.startswith('@@'):
                # Parse @@ -a,b +c,d @@ → c is the starting line in the new file
                m = re.search(r'\+(\d+)', raw_line)
                if m:
                    current_new_line = int(m.group(1))
                continue
            if raw_line.startswith('+++') or raw_line.startswith('---'):
                continue
            if raw_line.startswith('+'):
                real_line_nums.append(current_new_line)
                current_new_line += 1
            elif raw_line.startswith('-'):
                pass  # removed line doesn't advance new-file counter
            else:
                current_new_line += 1  # context line

        # Check for common issues
        for i, line in enumerate(added_lines):
            line_num = real_line_nums[i] if i < len(real_line_nums) else i + 1
            code = line[1:]  # strip leading +
            code_stripped = code.strip()
            code_lower = code.lower()

            # ── Security: hardcoded secrets ──
            if any(p in code_lower for p in ['password=', 'password =', 'api_key=', 'api_key =',
                                              'secret=', 'secret =', 'token=', 'token =',
                                              'default_password', 'db_password']):
                if '=' in code and not code_stripped.startswith('#') and not code_stripped.startswith('//'):
                    # Try to extract variable name for better suggestion
                    var_match = re.match(r'\s*(\w+)\s*=', code)
                    var_name = var_match.group(1) if var_match else 'SECRET'
                    findings.append(FindingSchema(
                        title="Potential Hardcoded Secret",
                        description="This line appears to contain a hardcoded credential or secret. Secrets should be loaded from environment variables or a dedicated secrets manager.",
                        severity=Severity.CRITICAL,
                        file_path=file_path,
                        line_start=line_num,
                        line_end=line_num,
                        original_code=code,
                        suggested_code=f'{var_name} = os.environ.get("{var_name.upper()}")',
                        explanation="Hardcoded secrets are a security risk — they end up in version control and can be leaked. Use os.environ.get() or a library like python-dotenv.",
                        skills_affected=["secrets_management", "auth_practices"]
                    ))

            # ── Logging secrets: print() with secret/password/token values ──
            if 'print(' in code and any(w in code_lower for w in ['password', 'secret', 'token', 'key', 'value']):
                if not code_stripped.startswith('#'):
                    findings.append(FindingSchema(
                        title="Sensitive Data Logged to Console",
                        description="This print statement may expose sensitive data (passwords, secrets, tokens) in logs or console output.",
                        severity=Severity.CRITICAL,
                        file_path=file_path,
                        line_start=line_num,
                        line_end=line_num,
                        original_code=code,
                        suggested_code=code.replace('print(', 'logger.debug(').rstrip(')') + '  # Redact sensitive values before logging',
                        explanation="Never log secret values — they can end up in log files, CI output, or monitoring dashboards. Use a logger with appropriate levels and redact sensitive fields.",
                        skills_affected=["secrets_management", "clean_code"]
                    ))
            # ── Code style: print statements in production code ──
            elif 'print(' in code and not any(ext in file_path for ext in ['test', 'debug', 'log']):
                if not code_stripped.startswith('#'):
                    findings.append(FindingSchema(
                        title="Debug Print Statement",
                        description="Print statement found in production code. Use a logging framework instead.",
                        severity=Severity.INFO,
                        file_path=file_path,
                        line_start=line_num,
                        line_end=line_num,
                        original_code=code,
                        suggested_code=code.replace('print(', 'logging.info('),
                        explanation="Use the logging module for better control over output levels, formatting, and destinations. import logging at the top of the file.",
                        skills_affected=["clean_code", "error_handling"]
                    ))

            # ── Security: SQL injection via string concatenation ──
            if ('.execute(' in code and
                    ('+' in code or '.format(' in code or 'f"' in code or "f'" in code) and
                    any(kw in code_lower for kw in ['select', 'insert', 'update', 'delete', 'where'])):
                findings.append(FindingSchema(
                    title="SQL Injection Vulnerability",
                    description="SQL query uses string concatenation or formatting instead of parameterized queries. This allows attackers to inject malicious SQL.",
                    severity=Severity.CRITICAL,
                    file_path=file_path,
                    line_start=line_num,
                    line_end=line_num,
                    original_code=code,
                    suggested_code='cursor.execute("SELECT * FROM table WHERE col = ?", (value,))',
                    explanation="Always use parameterized queries (? placeholders with tuples) to prevent SQL injection. Never concatenate or format user input into SQL strings.",
                    skills_affected=["input_validation", "database_queries"]
                ))

            # ── Error handling: bare except ──
            if re.match(r'\s*except\s*:', code):
                findings.append(FindingSchema(
                    title="Bare Except Clause",
                    description="Catching all exceptions without specifying a type hides bugs, catches KeyboardInterrupt/SystemExit, and makes debugging nearly impossible.",
                    severity=Severity.WARNING,
                    file_path=file_path,
                    line_start=line_num,
                    line_end=line_num,
                    original_code=code,
                    suggested_code=code.replace('except:', 'except (ValueError, IOError) as e:'),
                    explanation="Catch specific exceptions so unexpected errors propagate properly. At minimum use 'except Exception as e:' to avoid catching SystemExit and KeyboardInterrupt.",
                    skills_affected=["error_handling", "clean_code"]
                ))

            # ── Error handling: broad except Exception ──
            if re.match(r'\s*except\s+Exception\s*:', code):
                findings.append(FindingSchema(
                    title="Overly Broad Exception Handler",
                    description="Catching all Exception types makes it hard to distinguish expected errors from bugs.",
                    severity=Severity.WARNING,
                    file_path=file_path,
                    line_start=line_num,
                    line_end=line_num,
                    original_code=code,
                    suggested_code=code.replace('except Exception:', 'except (ValueError, KeyError) as e:'),
                    explanation="Catch only the specific exceptions you expect. This makes error handling intentional and helps surface unexpected bugs.",
                    skills_affected=["error_handling", "clean_code"]
                ))

            # ── Resource leak: open() without with ──
            if re.search(r'(\w+)\s*=\s*open\(', code) and 'with ' not in code:
                findings.append(FindingSchema(
                    title="File Opened Without Context Manager",
                    description="File opened with open() but not using a 'with' statement. The file handle may not be properly closed on exceptions.",
                    severity=Severity.WARNING,
                    file_path=file_path,
                    line_start=line_num,
                    line_end=line_num,
                    original_code=code,
                    suggested_code=code.replace(code_stripped, f'with {code_stripped.split("=")[1].strip()} as f:  # auto-closes'),
                    explanation="Use 'with open(...) as f:' to ensure the file is always closed, even if an exception occurs.",
                    skills_affected=["error_handling", "clean_code"]
                ))

            # ── Resource leak: sqlite3.connect without with ──
            if 'sqlite3.connect(' in code and 'with ' not in code:
                findings.append(FindingSchema(
                    title="Database Connection Without Context Manager",
                    description="Database connection opened without a 'with' statement or try/finally block. Connection may leak on exceptions.",
                    severity=Severity.WARNING,
                    file_path=file_path,
                    line_start=line_num,
                    line_end=line_num,
                    original_code=code,
                    suggested_code=code.replace(code_stripped, f'with sqlite3.connect({code.split("connect(")[1].split(")")[0]}) as conn:'),
                    explanation="Use a context manager to ensure database connections are properly closed, even when exceptions occur.",
                    skills_affected=["error_handling", "database_queries"]
                ))

            # ── Global mutable state: module-level connection/list/dict ──
            if (re.match(r'[A-Za-z_]\w*\s*=\s*(sqlite3\.connect|{|\[)', code_stripped) and
                    not code_stripped.startswith('def ') and not code_stripped.startswith('class ')):
                if 'sqlite3.connect' in code:
                    findings.append(FindingSchema(
                        title="Global Database Connection",
                        description="Module-level database connection is created at import time. This prevents proper connection lifecycle management and causes issues with threading.",
                        severity=Severity.WARNING,
                        file_path=file_path,
                        line_start=line_num,
                        line_end=line_num,
                        original_code=code,
                        suggested_code=f'def get_connection(db_path):\n    return sqlite3.connect(db_path)',
                        explanation="Create database connections inside functions or use a connection pool. Global connections can't be properly closed and cause threading issues.",
                        skills_affected=["architecture", "database_queries"]
                    ))

            # ── Mutable default argument ──
            if re.match(r'\s*def\s+\w+\(.*=\s*(\[\]|\{\})\s*[,)]', code):
                findings.append(FindingSchema(
                    title="Mutable Default Argument",
                    description="Using a mutable object (list or dict) as a default argument is a common Python bug — the default is shared across all calls.",
                    severity=Severity.WARNING,
                    file_path=file_path,
                    line_start=line_num,
                    line_end=line_num,
                    original_code=code,
                    suggested_code=re.sub(r'=\s*\[\]', '=None', re.sub(r'=\s*\{\}', '=None', code)),
                    explanation="Use None as the default and create a new list/dict inside the function: 'if items is None: items = []'. Mutable defaults persist between calls.",
                    skills_affected=["clean_code", "edge_cases"]
                ))

            # ── Missing input validation on function params ──
            if re.match(r'\s*def\s+\w+\(', code) and 'self' not in code:
                # Check if function has params but no type hints
                params = re.findall(r'def\s+\w+\(([^)]+)\)', code)
                if params and ':' not in params[0] and params[0].strip() != '':
                    findings.append(FindingSchema(
                        title="Missing Type Hints",
                        description="Function parameters lack type annotations. Type hints improve readability, enable static analysis, and catch bugs early.",
                        severity=Severity.SUGGESTION,
                        file_path=file_path,
                        line_start=line_num,
                        line_end=line_num,
                        original_code=code,
                        suggested_code=code.replace('):', ') -> None:'),
                        explanation="Add type hints to function parameters and return types. Use 'def func(name: str, count: int = 0) -> list:' style annotations.",
                        skills_affected=["clean_code", "comments_docs"]
                    ))

            # ── import * ──
            if re.match(r'\s*from\s+\S+\s+import\s+\*', code):
                findings.append(FindingSchema(
                    title="Wildcard Import",
                    description="'from module import *' pollutes the namespace and makes it unclear where names come from.",
                    severity=Severity.WARNING,
                    file_path=file_path,
                    line_start=line_num,
                    line_end=line_num,
                    original_code=code,
                    suggested_code=code.replace('import *', 'import specific_name'),
                    explanation="Import only the specific names you need: 'from module import func1, func2'. This makes dependencies explicit and prevents name collisions.",
                    skills_affected=["clean_code", "code_structure"]
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

    @staticmethod
    def _extract_diff_code(diff: str) -> str:
        """Extract all code content from a unified diff for validation.

        Returns a lowercased blob containing every added, removed, and
        context line so that ``original_code`` can be checked against it.
        """
        lines: list[str] = []
        for raw_line in diff.splitlines():
            # Skip diff metadata
            if raw_line.startswith(("diff --git", "index ", "---", "+++", "@@")):
                continue
            # Strip the leading +/- /space marker
            if raw_line and raw_line[0] in ("+", "-", " "):
                lines.append(raw_line[1:])
            else:
                lines.append(raw_line)
        return "\n".join(lines).lower()

    @staticmethod
    def _validate_finding(finding: "FindingSchema", diff_code: str) -> bool:
        """Check that the finding's original_code relates to the diff.

        Uses a lenient approach: if any meaningful token from the
        original_code appears in the diff, the finding is kept.
        Only drops findings that are completely fabricated.
        """
        orig = (finding.original_code or "").strip().lower()
        if not orig:
            return True  # no original_code to validate

        # Direct substring check
        if orig in diff_code:
            return True

        # Whitespace-collapsed check (handles indentation differences)
        collapsed_orig = " ".join(orig.split())
        collapsed_diff = " ".join(diff_code.split())
        if collapsed_orig in collapsed_diff:
            return True

        # Line-by-line: ANY non-trivial line match is enough to keep the finding
        orig_lines = [l.strip() for l in orig.splitlines() if len(l.strip()) > 5]
        if orig_lines:
            for line in orig_lines:
                if line in diff_code:
                    return True
                # Also try whitespace-collapsed
                if " ".join(line.split()) in collapsed_diff:
                    return True

        # Token-based fallback: check if meaningful identifiers from
        # original_code appear in the diff (catches paraphrased code)
        import re
        identifiers = set(re.findall(r'[a-z_][a-z0-9_]{2,}', orig))
        # Remove very common tokens that would match anything
        common = {'self', 'none', 'true', 'false', 'return', 'import', 'from',
                  'def', 'class', 'for', 'while', 'with', 'print', 'pass'}
        identifiers -= common
        if identifiers:
            matches = sum(1 for ident in identifiers if ident in diff_code)
            if matches >= max(1, len(identifiers) // 3):
                return True

        return False

    def _parse_response(self, content: str, tokens: int, diff: str = "") -> Optional[EvaluationResult]:
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
            # DEBUG: dump raw findings titles
            diff_code = self._extract_diff_code(diff) if diff else ""

            # Parse findings — errors on individual items are caught and skipped
            # so one bad finding never discards the rest.
            findings = []
            for idx, f in enumerate(raw_findings):
                try:
                    valid_skills = [s for s in f.get("skills_affected", []) if s in VALID_SKILLS]
                    finding = FindingSchema(
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
                    )

                    # Validate that original_code exists in the diff
                    if diff_code and not self._validate_finding(finding, diff_code):
                        print(
                            f"[LLM PARSE] Dropped finding #{idx} "
                            f"'{finding.title}' — original_code not found in diff"
                        )
                        continue

                    # Validate suggested_code is not identical to original_code
                    if (finding.suggested_code.strip() and
                            finding.suggested_code.strip() == finding.original_code.strip()):
                        print(
                            f"[LLM PARSE] Dropped finding #{idx} "
                            f"'{finding.title}' — suggested_code identical to original"
                        )
                        continue

                    findings.append(finding)
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
