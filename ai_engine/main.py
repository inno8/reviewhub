"""
ReviewHub v2 - FastAPI AI Engine
Handles webhooks, diff analysis, and LLM evaluation.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api import webhooks, analysis, health
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    print("🚀 ReviewHub AI Engine starting...")
    print(f"   Django API: {settings.DJANGO_API_URL}")
    print(f"   LLM Provider: {settings.LLM_PROVIDER or 'OpenClaw (fallback)'}")
    yield
    # Shutdown
    print("👋 ReviewHub AI Engine shutting down...")


app = FastAPI(
    title="ReviewHub AI Engine",
    description="AI-powered code review and skill tracking",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(webhooks.router, prefix="/api/v1/webhook", tags=["Webhooks"])
app.include_router(analysis.router, prefix="/api/v1/analyze", tags=["Analysis"])


@app.get("/")
async def root():
    return {
        "service": "ReviewHub AI Engine",
        "version": "2.0.0",
        "status": "running"
    }
