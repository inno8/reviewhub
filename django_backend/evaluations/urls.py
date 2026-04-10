"""
Evaluation API URLs
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.EvaluationListView.as_view(), name='evaluation-list'),
    path('chart/', views.EvaluationChartView.as_view(), name='evaluation-chart'),
    path('<int:pk>/', views.EvaluationDetailView.as_view(), name='evaluation-detail'),
    path('internal/', views.InternalEvaluationCreateView.as_view(), name='evaluation-internal-create'),
    
    # Findings
    path('findings/', views.FindingListView.as_view(), name='finding-list'),
    path('findings/<int:pk>/', views.FindingDetailView.as_view(), name='finding-detail'),
    path('findings/<int:pk>/file-content/', views.FindingFileContentView.as_view(), name='finding-file-content'),
    path('findings/<int:pk>/fix/', views.MarkFindingFixedView.as_view(), name='finding-fix'),
    path('findings/check-understanding/', views.CheckUnderstandingView.as_view(), name='finding-check-understanding'),
    path('findings/resolved/', views.ResolvedFindingsView.as_view(), name='finding-resolved-list'),
    
    # Dashboard & Calendar
    path('dashboard/', views.DashboardView.as_view(), name='evaluation-dashboard'),
    path('calendar/', views.CalendarView.as_view(), name='evaluation-calendar'),

    # Pattern tracker
    path('patterns/', views.PatternListView.as_view(), name='pattern-list'),
    path('patterns/<int:pk>/resolve/', views.PatternResolveView.as_view(), name='pattern-resolve'),
]
