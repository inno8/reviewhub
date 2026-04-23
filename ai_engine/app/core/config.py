"""
Configuration settings for the AI Engine.
"""
from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings from environment variables."""
    
    # App
    DEBUG: bool = False
    
    # Backend API (Django origin only; paths use /api/... in clients)
    BACKEND_API_URL: str = "http://localhost:8000"
    BACKEND_API_KEY: Optional[str] = None  # For internal API calls
    
    # LLM Configuration
    LLM_PROVIDER: Optional[str] = None  # openai, anthropic, or None for OpenClaw
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL: str = "gpt-4-turbo"  # backward-compat fallback

    # Two-tier LLM routing
    # LLM_MODEL_FAST    → push/commit events (student feedback)  — cheap, quick
    # LLM_MODEL_QUALITY → PR grading (teacher rubric draft)      — best available
    # Both fall back to LLM_MODEL when unset.
    LLM_MODEL_FAST: Optional[str] = None
    LLM_MODEL_QUALITY: Optional[str] = None
    
    # OpenClaw Fallback
    OPENCLAW_ENABLED: bool = True
    OPENCLAW_WEBHOOK_URL: Optional[str] = None
    OPENCLAW_API_KEY: Optional[str] = None
    
    # GitHub Webhook
    GITHUB_WEBHOOK_SECRET: Optional[str] = None
    GITHUB_APP_ID: Optional[str] = None
    GITHUB_PRIVATE_KEY: Optional[str] = None
    
    # GitLab Webhook
    GITLAB_WEBHOOK_SECRET: Optional[str] = None
    
    # Git Cache
    GIT_CACHE_DIR: str = "./repos"
    
    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
    ]
    
    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
