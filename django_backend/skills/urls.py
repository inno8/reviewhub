"""
Skills API URLs
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.SkillListView.as_view(), name='skill-list'),
    path('categories/', views.SkillCategoryListView.as_view(), name='skill-category-list'),
    path('metrics/', views.SkillMetricListView.as_view(), name='skill-metric-list'),
    path('metrics/update/', views.UpdateSkillMetricsView.as_view(), name='skill-metric-update'),
    path('trends/', views.SkillTrendsView.as_view(), name='skill-trends'),
]
