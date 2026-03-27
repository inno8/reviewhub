"""
LLM Adapter - Abstraction layer for multiple LLM providers.

Supports:
- OpenAI (GPT-4, etc.)
- Anthropic (Claude)
- OpenClaw fallback (when no API key configured)
"""
import json
import time
from typing import Optional
import httpx

from app.core.config import settings
from app.models.schemas import EvaluationResult, FindingSchema, Severity

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


EVALUATION_PROMPT = '''You are an expert code reviewer. Analyze the following code diff and provide detailed feedback.

FILE: {file_path}
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

Focus on:
1. Code quality and best practices
2. Potential bugs or security issues
3. Performance improvements
4. Maintainability and readability

Return ONLY the JSON object, no markdown formatting.'''


class LLMAdapter:
    """
    Adapter for multiple LLM providers.
    
    Priority:
    1. User-provided API key (from request)
    2. System-configured provider (from settings)
    3. OpenClaw fallback
    """
    
    def __init__(self, api_key: Optional[str] = None):
        # Determine provider and key
        if api_key:
            # User provided their own key
            self.provider = settings.LLM_PROVIDER or "openai"
            self.api_key = api_key
        elif settings.LLM_API_KEY:
            # System-configured key
            self.provider = settings.LLM_PROVIDER or "openai"
            self.api_key = settings.LLM_API_KEY
        elif settings.OPENCLAW_ENABLED:
            # Fallback to OpenClaw
            self.provider = "openclaw"
            self.api_key = settings.OPENCLAW_API_KEY
        else:
            raise ValueError("No LLM provider configured")
        
        self.model_name = settings.LLM_MODEL
    
    async def evaluate_diff(
        self,
        diff: str,
        file_path: str,
        language: str = "unknown",
        context_files: list = None
    ) -> Optional[EvaluationResult]:
        """
        Evaluate a code diff using the configured LLM.
        
        Returns structured evaluation result.
        """
        # Build context section if available
        context_section = ""
        if context_files:
            context_section = "RELATED FILES (for context):\n"
            for cf in context_files[:3]:  # Limit context
                context_section += f"\n--- {cf['path']} ---\n{cf['content'][:1000]}\n"
        
        # Build prompt
        prompt = EVALUATION_PROMPT.format(
            file_path=file_path,
            language=language,
            diff=diff,
            context_section=context_section
        )
        
        # Call appropriate provider
        start_time = time.time()
        
        if self.provider == "openai":
            result = await self._call_openai(prompt)
        elif self.provider == "anthropic":
            result = await self._call_anthropic(prompt)
        elif self.provider == "openclaw":
            result = await self._call_openclaw(prompt, diff, file_path)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
        
        if result:
            result.processing_ms = int((time.time() - start_time) * 1000)
            result.llm_model = self.model_name
        
        return result
    
    async def _call_openai(self, prompt: str) -> Optional[EvaluationResult]:
        """Call OpenAI API."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model_name,
                        "messages": [
                            {"role": "system", "content": "You are an expert code reviewer. Return only valid JSON."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.3,
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
    
    async def _call_anthropic(self, prompt: str) -> Optional[EvaluationResult]:
        """Call Anthropic API."""
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
                        "model": self.model_name,
                        "max_tokens": 4096,
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
        print(f"[ANALYSIS] Using rule-based analysis for: {file_path}")
        
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
        
        print(f"[OK] Analysis complete: {len(findings)} findings, score {overall_score}")
        
        return EvaluationResult(
            overall_score=overall_score,
            findings=findings,
            skill_scores=skill_scores,
            summary=summary,
            tokens_used=0
        )
    
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
            
            # Parse findings
            findings = []
            for f in data.get("findings", []):
                # Validate skills
                valid_skills = [s for s in f.get("skills_affected", []) if s in VALID_SKILLS]
                
                findings.append(FindingSchema(
                    title=f.get("title", "Unknown Issue"),
                    description=f.get("description", ""),
                    severity=Severity(f.get("severity", "warning")),
                    file_path=f.get("file_path", "unknown"),
                    line_start=f.get("line_start", 1),
                    line_end=f.get("line_end", 1),
                    original_code=f.get("original_code", ""),
                    suggested_code=f.get("suggested_code", ""),
                    explanation=f.get("explanation", ""),
                    skills_affected=valid_skills
                ))
            
            # Validate skill scores
            skill_scores = {}
            for skill, score in data.get("skill_scores", {}).items():
                if skill in VALID_SKILLS:
                    skill_scores[skill] = float(score)
            
            return EvaluationResult(
                overall_score=float(data.get("overall_score", 50)),
                findings=findings,
                skill_scores=skill_scores,
                summary=data.get("summary", ""),
                tokens_used=tokens
            )
            
        except Exception as e:
            print(f"Parse error: {e}")
            print(f"Content: {content[:500]}")
            return None
