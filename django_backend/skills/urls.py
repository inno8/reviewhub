"""
Skills API URLs
"""
from django.urls import path
from . import views
from .recommendations import LearningRecommendationsView

urlpatterns = [
    path('', views.SkillListView.as_view(), name='skill-list'),
    path('categories/', views.SkillCategoryListView.as_view(), name='skill-category-list'),
    path('metrics/', views.SkillMetricListView.as_view(), name='skill-metric-list'),
    path('metrics/update/', views.UpdateSkillMetricsView.as_view(), name='skill-metric-update'),
    path('trends/', views.SkillTrendsView.as_view(), name='skill-trends'),
    path('user/<int:user_id>/', views.UserSkillsView.as_view(), name='user-skills'),
    path('user/<int:user_id>/breakdown/<int:skill_id>/', views.SkillBreakdownView.as_view(), name='skill-breakdown'),

    # Performance Insights
    path('performance/<int:user_id>/', views.PerformanceStatsView.as_view(), name='performance-stats'),
    path('performance/<int:user_id>/trends/', views.PerformanceTrendsView.as_view(), name='performance-trends'),

    # Dashboard endpoints
    path('dashboard/overview/', views.DashboardOverviewView.as_view(), name='dashboard-overview'),
    path('dashboard/skills/', views.DashboardSkillsView.as_view(), name='dashboard-skills'),
    path('dashboard/progress/', views.DashboardProgressView.as_view(), name='dashboard-progress'),
    path('dashboard/recent/', views.DashboardRecentView.as_view(), name='dashboard-recent'),

    # Recommendations
    path('recommendations/', LearningRecommendationsView.as_view(), name='learning-recommendations'),

    # Unified developer home
    path('dashboard/developer-home/', views.DeveloperHomeView.as_view(), name='developer-home'),

    # Admin team overview
    path('dashboard/admin-team/', views.AdminTeamOverviewView.as_view(), name='admin-team-overview'),
]
