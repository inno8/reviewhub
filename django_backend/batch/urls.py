"""
Batch Processing URLs
"""
from django.urls import path
from . import views

urlpatterns = [
    # Batch jobs
    path('jobs/', views.BatchJobListCreateView.as_view(), name='batch-job-list'),
    path('jobs/<int:pk>/', views.BatchJobDetailView.as_view(), name='batch-job-detail'),
    path('jobs/<int:pk>/internal/', views.BatchJobInternalUpdateView.as_view(), name='batch-job-internal'),
    path('jobs/<int:job_id>/results/', views.BatchJobResultsView.as_view(), name='batch-job-results'),
    
    # Developer profile
    path('profile/', views.DeveloperProfileView.as_view(), name='developer-profile'),
    
    # Stats
    path('stats/', views.BatchStatsView.as_view(), name='batch-stats'),
]
