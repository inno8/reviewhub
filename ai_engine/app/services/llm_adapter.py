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
        Call OpenClaw as fallback.
        
        This routes through the OpenClaw gateway, which will use
        the configured model (yo handles the actual LLM call).
        """
        # TODO: Implement OpenClaw webhook integration
        # For now, return a placeholder
        print("OpenClaw fallback not yet implemented - returning mock result")
        
        return EvaluationResult(
            overall_score=75.0,
            findings=[],
            skill_scores={},
            summary="OpenClaw evaluation (mock)",
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
