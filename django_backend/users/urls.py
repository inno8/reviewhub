"""
User API URLs
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.UserListView.as_view(), name='user-list'),
    path('me/', views.CurrentUserView.as_view(), name='user-me'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change-password'),
    path('<int:pk>/', views.UserDetailView.as_view(), name='user-detail'),
    path('register/', views.RegisterView.as_view(), name='user-register'),
    path('by-email/', views.UserByEmailView.as_view(), name='user-by-email'),
]
