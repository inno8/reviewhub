"""
Backend API Client - Communication with Node.js/Prisma backend.
"""
import httpx
from typing import Optional

from app.core.config import settings


class DjangoClient:
    """
    HTTP client for backend API communication.
    
    Handles:
    - Creating evaluations
    - Storing findings
    - Updating skill metrics
    """
    
    def __init__(self):
        self.base_url = settings.BACKEND_API_URL.rstrip("/")
        self.api_key = settings.BACKEND_API_KEY
    
    def _get_headers(self) -> dict:
        """Get request headers."""
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers
    
    async def create_evaluation(self, data: dict) -> Optional[dict]:
        """
        Create a new evaluation in Django.
        
        Args:
            data: Evaluation data including findings
            
        Returns:
            Created evaluation or None on error
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/evaluations/internal/",
                    headers=self._get_headers(),
                    json=data,
                    timeout=30.0
                )
                
                if response.status_code == 201:
                    return response.json()
                else:
                    commit_sha = (data.get("commit_sha") or "")[:7]
                    print(
                        f"[DJANGO] create_evaluation FAILED {response.status_code} "
                        f"commit={commit_sha}: {response.text[:600]}",
                        flush=True,
                    )
                    return None

        except Exception as e:
            print(f"[DJANGO] create_evaluation error: {e}", flush=True)
            return None
    
    async def get_project(self, project_id: int) -> Optional[dict]:
        """Get project details from Django."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/projects/{project_id}/",
                    headers=self._get_headers(),
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    return None
                    
        except Exception as e:
            print(f"Django client error: {e}")
            return None
    
    async def get_user_by_email(self, email: str) -> Optional[dict]:
        """Find user by git email."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/users/by-email/",
                    params={"email": email},
                    headers=self._get_headers(),
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    return None
                    
        except Exception as e:
            print(f"Django client error: {e}")
            return None
    
    async def get_project_member_by_email(self, project_id: int, email: str) -> Optional[dict]:
        """Find project member by git email for user resolution."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/projects/{project_id}/members/",
                    headers=self._get_headers(),
                    timeout=10.0
                )
                if response.status_code == 200:
                    members = response.json()
                    for m in members:
                        if m.get('git_email', '').lower() == email.lower() or m.get('user_email', '').lower() == email.lower():
                            return m
                return None
        except Exception as e:
            print(f"Django client error: {e}")
            return None

    async def get_org_llm_config(self, user_id: int = None, email: str = None) -> Optional[dict]:
        """Fetch the org's default LLM config for a user.

        Returns dict with keys: provider, api_key, model — or None.
        """
        try:
            params = {}
            if user_id:
                params["user_id"] = user_id
            elif email:
                params["email"] = email
            else:
                return None

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/users/org-llm-config/",
                    params=params,
                    headers=self._get_headers(),
                    timeout=10.0,
                )
                if response.status_code == 200:
                    return response.json()
                return None
        except Exception as e:
            print(f"[DJANGO] get_org_llm_config error: {e}", flush=True)
            return None

    async def get_user_skill_profile(self, user_id: int) -> Optional[dict]:
        """Get user's skill metrics for adaptive prompt enrichment."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/skills/user/{user_id}/",
                    headers=self._get_headers(),
                    timeout=10.0
                )
                if response.status_code == 200:
                    return response.json()
                return None
        except Exception as e:
            print(f"Django client error: {e}")
            return None

    async def get_adaptive_profile(
        self, user_id: int, project_id: Optional[int] = None
    ) -> Optional[dict]:
        """
        Fetch the full adaptive developer profile used for prompt enrichment.
        Returns a dict with level, strengths, weaknesses, frequent_patterns, etc.
        Falls back to get_user_skill_profile if the richer endpoint is missing.
        """
        try:
            params: dict = {}
            if project_id:
                params["project"] = project_id
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/users/{user_id}/adaptive-profile/",
                    params=params,
                    headers=self._get_headers(),
                    timeout=10.0,
                )
                if response.status_code == 200:
                    return response.json()
                # Fallback to skill profile
                return await self.get_user_skill_profile(user_id)
        except Exception as e:
            print(f"Django client error (adaptive profile): {e}")
            return None

    async def update_skill_metrics(
        self,
        user_id: int,
        project_id: int,
        skill_updates: dict
    ) -> bool:
        """
        Update skill metrics for a user.
        
        Args:
            user_id: User ID
            project_id: Project ID
            skill_updates: Dict of skill_slug -> {issues: int, score: float}
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/skills/metrics/update/",
                    headers=self._get_headers(),
                    json={
                        "user_id": user_id,
                        "project_id": project_id,
                        "updates": skill_updates
                    },
                    timeout=30.0
                )
                
                return response.status_code == 200
                    
        except Exception as e:
            print(f"Django client error: {e}")
            return False
