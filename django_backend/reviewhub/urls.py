"""
ReviewHub URL Configuration
"""
from django.contrib import admin
from django.http import JsonResponse
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from users.serializers import CustomTokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from users.views import OnboardCheckEmailView, OnboardVerifyCodeView, OnboardSetPasswordView


def custom_404(request, exception=None):
    return JsonResponse({"detail": "Not found"}, status=404)


def custom_500(request):
    return JsonResponse({"detail": "Internal server error"}, status=500)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


urlpatterns = [
    path('admin/', admin.site.urls),

    # JWT Auth
    path('api/auth/token/', CustomTokenObtainPairView.as_view(), name='token_obtain'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # API endpoints
    path('api/users/', include('users.urls')),
    path('api/projects/', include('projects.urls')),
    path('api/evaluations/', include('evaluations.urls')),
    path('api/skills/', include('skills.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('api/batch/', include('batch.urls')),  # Phase 6: Batch analysis
    path('api/grading/', include('grading.urls')),  # Nakijken Copilot v1
    path('api/github/', include('users.github_urls')),  # GitHub App install flow

    # Onboard (public endpoints)
    path('api/onboard/check-email/', OnboardCheckEmailView.as_view(), name='onboard-check-email'),
    path('api/onboard/verify-code/', OnboardVerifyCodeView.as_view(), name='onboard-verify-code'),
    path('api/onboard/set-password/', OnboardSetPasswordView.as_view(), name='onboard-set-password'),

    # Health check
    path('api/health/', lambda r: __import__('django.http', fromlist=['JsonResponse']).JsonResponse({'status': 'healthy'})),
]

handler404 = custom_404
handler500 = custom_500
