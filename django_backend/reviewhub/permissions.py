"""
Custom permissions for internal API endpoints.
"""
import os
from rest_framework import permissions


class IsInternalAPIKey(permissions.BasePermission):
    """
    Authenticate requests from the FastAPI AI engine using X-API-Key header.
    Falls back to AllowAny if INTERNAL_API_KEY is not set (dev mode).
    """

    def has_permission(self, request, view):
        expected_key = os.getenv('INTERNAL_API_KEY', '')
        if not expected_key:
            return True
        return request.headers.get('X-API-Key') == expected_key
