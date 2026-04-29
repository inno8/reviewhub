"""
ReviewHub v2 - Django Settings
"""
import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv
import dj_database_url

# Load environment variables
load_dotenv()

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Security
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_filters',
    
    # Local apps
    'users',
    'projects',
    'evaluations',
    'skills',
    'notifications',
    'batch',  # Phase 6: Batch commit analysis
    'grading',  # Nakijken Copilot v1 — teacher grading copilot
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'reviewhub.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'reviewhub.wsgi.application'

# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///db.sqlite3')
DATABASES = {
    'default': dj_database_url.parse(DATABASE_URL)
}

# Custom User Model
AUTH_USER_MODEL = 'users.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ═══════════════════════════════════════════════════════════════════════════════
# REST Framework
# ═══════════════════════════════════════════════════════════════════════════════
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}

# P4-14: BrowsableAPI removed — always use JSON-only renderer in all environments

# ═══════════════════════════════════════════════════════════════════════════════
# JWT Settings
# P4-8: Access token default reduced from 60 to 15 min for production safety
# ═══════════════════════════════════════════════════════════════════════════════
SIMPLE_JWT = {
    # `or` so empty strings in .env fall through to the default
    # (os.getenv returns '' for "KEY=", not None).
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=int(os.getenv('JWT_ACCESS_TOKEN_LIFETIME_MINUTES') or 15)),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=int(os.getenv('JWT_REFRESH_TOKEN_LIFETIME_DAYS') or 7)),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'SIGNING_KEY': os.getenv('JWT_SECRET_KEY', SECRET_KEY),
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ═══════════════════════════════════════════════════════════════════════════════
# CORS Settings
# P4-1: Always use explicit allowlist — never CORS_ALLOW_ALL_ORIGINS
# ═══════════════════════════════════════════════════════════════════════════════
CORS_ALLOWED_ORIGINS = os.getenv(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174'
).split(',')
CORS_ALLOW_CREDENTIALS = True

# ═══════════════════════════════════════════════════════════════════════════════
# P4-22: Security headers
# ═══════════════════════════════════════════════════════════════════════════════
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_BROWSER_XSS_FILTER = True
if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# ═══════════════════════════════════════════════════════════════════════════════
# FastAPI AI Engine
# ═══════════════════════════════════════════════════════════════════════════════
FASTAPI_URL = os.getenv('FASTAPI_URL', 'http://localhost:8001')
# Optional server fallback for GitHub API (batch branch list). Users can store a PAT in Settings instead.
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')

# ai_engine FastAPI service. Nakijken's webhook gateway forwards push
# events here for the per-commit Code Review pipeline. Both services
# share GITHUB_WEBHOOK_SECRET so the forwarded signature stays valid.
AI_ENGINE_URL = os.getenv('AI_ENGINE_URL', 'http://localhost:8001')
GITHUB_WEBHOOK_SECRET = os.getenv('GITHUB_WEBHOOK_SECRET', '')

# ═══════════════════════════════════════════════════════════════════════════════
# LLM settings UI — Google OAuth (Gemini) & post-OAuth redirect
# ═══════════════════════════════════════════════════════════════════════════════
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5173').rstrip('/')
# Public URL of this Django API (used in Google OAuth redirect_uri). Must match Google Console.
BACKEND_PUBLIC_URL = os.getenv('BACKEND_PUBLIC_URL', 'http://localhost:8000').rstrip('/')
GOOGLE_OAUTH_CLIENT_ID = os.getenv('GOOGLE_OAUTH_CLIENT_ID', '')
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET', '')

# ═══════════════════════════════════════════════════════════════════════════════
# Email configuration
# Dev: local SMTP (mailhog/mailpit on port 1025)
# Prod: Resend via SMTP relay (or custom backend)
# Test: in-memory backend (django.core.mail.backends.locmem.EmailBackend)
# ═══════════════════════════════════════════════════════════════════════════════
EMAIL_BACKEND = os.getenv(
    'EMAIL_BACKEND',
    'django.core.mail.backends.smtp.EmailBackend',
)
EMAIL_HOST = os.getenv('EMAIL_HOST', 'localhost')
# `os.getenv(KEY, default)` only falls back to `default` when KEY is
# *unset* — an empty string ("EMAIL_PORT=" in .env) returns '' which
# blows up `int('')`. Use `or` so an empty value also falls through.
EMAIL_PORT = int(os.getenv('EMAIL_PORT') or '1025')
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'false').lower() == 'true'
# Hard cap on SMTP connect/operation time. Without this, Python's
# socket.create_connection() blocks indefinitely when the destination
# port is firewalled (e.g. DigitalOcean blocks outbound SMTP by default).
# A 30s gunicorn worker timeout fires before the SMTP call returns,
# the worker is killed mid-request, and the client sees a 500.
# 10s is generous for a healthy SMTP relay (Gmail/Brevo round-trip is
# ~200ms in EU) and short enough to keep workers alive when egress is
# blocked, so our error path returns a clean 502 instead of a worker
# crash.
EMAIL_TIMEOUT = int(os.getenv('EMAIL_TIMEOUT') or '10')
EMAIL_FROM = os.getenv('DEFAULT_FROM_EMAIL', os.getenv('EMAIL_FROM', 'noreply@reviewhub.com'))
DEFAULT_FROM_EMAIL = EMAIL_FROM
RESEND_API_KEY = os.getenv('RESEND_API_KEY', '')
