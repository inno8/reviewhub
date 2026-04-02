"""
Project API URLs
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.ProjectListCreateView.as_view(), name='project-list'),
    path('<int:pk>/', views.ProjectDetailView.as_view(), name='project-detail'),
    path('<int:pk>/webhook/', views.ProjectWebhookView.as_view(), name='project-webhook'),
    path('<int:pk>/webhook/test/', views.ProjectWebhookTestView.as_view(), name='project-webhook-test'),
    path('<int:pk>/link-repo/', views.ProjectLinkRepoView.as_view(), name='project-link-repo'),
    path('<int:pk>/unlink-repo/', views.ProjectUnlinkRepoView.as_view(), name='project-unlink-repo'),
    path('<int:pk>/members/', views.ProjectMemberListView.as_view(), name='project-members'),
    path('<int:pk>/members/<int:user_id>/', views.ProjectMemberDetailView.as_view(), name='project-member-detail'),
]
