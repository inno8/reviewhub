"""
URL routes for the GitHub App auth flow.
Mounted at /api/github/ in reviewhub/urls.py.
"""
from django.urls import path

from . import github_views

urlpatterns = [
    path(
        'install-url/',
        github_views.InstallUrlView.as_view(),
        name='github-install-url',
    ),
    path(
        'installations/',
        github_views.InstallationListView.as_view(),
        name='github-installations',
    ),
    path(
        'installations/sync/',
        github_views.InstallationSyncView.as_view(),
        name='github-installations-sync',
    ),
]
