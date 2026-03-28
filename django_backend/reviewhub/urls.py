"""
ReviewHub URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from users.serializers import CustomTokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView


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
    
    # Health check
    path('api/health/', lambda r: __import__('django.http', fromlist=['JsonResponse']).JsonResponse({'status': 'healthy'})),
]
