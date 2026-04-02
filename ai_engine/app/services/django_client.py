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
                    print(f"Django error: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            print(f"Django client error: {e}")
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
