"""
Health check endpoints.
"""
from fastapi import APIRouter
from datetime import datetime

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "reviewhub-ai-engine"
    }


@router.get("/status")
async def status():
    """Detailed status check."""
    from app.core.config import settings
    
    return {
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "config": {
            "django_api": settings.DJANGO_API_URL,
            "llm_provider": settings.LLM_PROVIDER or "openclaw",
            "llm_model": settings.LLM_MODEL,
            "openclaw_enabled": settings.OPENCLAW_ENABLED,
        }
    }
