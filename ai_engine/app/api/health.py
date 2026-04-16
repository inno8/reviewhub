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
    """Status check — returns operational state only (no infrastructure details)."""
    return {
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
    }
