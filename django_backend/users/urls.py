"""
User API URLs
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.UserListView.as_view(), name='user-list'),
    path('me/', views.CurrentUserView.as_view(), name='user-me'),
    path(
        'me/github-token/',
        views.GitHubPersonalAccessTokenView.as_view(),
        name='user-github-token',
    ),
    path('change-password/', views.ChangePasswordView.as_view(), name='change-password'),
    path('<int:pk>/', views.UserDetailView.as_view(), name='user-detail'),
    path('register/', views.RegisterView.as_view(), name='user-register'),
    path('by-email/', views.UserByEmailView.as_view(), name='user-by-email'),
    path('org-llm-config/', views.OrgLLMConfigView.as_view(), name='org-llm-config'),

    # User categories (admin)
    path('categories/', views.UserCategoryListCreateView.as_view(), name='category-list'),
    path('categories/<int:pk>/', views.UserCategoryDetailView.as_view(), name='category-detail'),

    # Admin: users with stats
    path('admin/stats/', views.AdminUserListView.as_view(), name='admin-user-stats'),

    # LLM Configuration (admin)
    path('me/llm-config/', views.LLMConfigView.as_view(), name='llm-config'),
    path('me/llm-config/test/', views.LLMConfigTestView.as_view(), name='llm-config-test'),
    path(
        'me/llm-config/oauth/google/start/',
        views.GoogleLLMOAuthStartView.as_view(),
        name='llm-google-oauth-start',
    ),
    path(
        'me/llm-config/oauth/google/callback/',
        views.GoogleLLMOAuthCallbackView.as_view(),
        name='llm-google-oauth-callback',
    ),
    path('me/llm-config/<str:provider>/', views.LLMConfigDeleteView.as_view(), name='llm-config-delete'),

    # Git host identities (developer — multiple per user)
    path('me/git-connections/', views.GitProviderConnectionListCreateView.as_view(), name='git-connections'),
    path('me/git-connections/<int:pk>/', views.GitProviderConnectionDetailView.as_view(), name='git-connection-detail'),

    # Phase 5 – Adaptive profile (internal AI engine use)
    path('<int:pk>/adaptive-profile/', views.AdaptiveProfileView.as_view(), name='user-adaptive-profile'),

    # Developer onboarding profile questionnaire
    path('me/dev-profile/', views.DevProfileView.as_view(), name='user-dev-profile'),
    path(
        'me/dev-calibration/',
        views.DevCalibrationSummaryView.as_view(),
        name='user-dev-calibration',
    ),

    # Organization onboarding (Phase 2)
    path('org-signup/', views.OrgSignupView.as_view(), name='org-signup'),
    path('invite/', views.InviteStudentView.as_view(), name='invite-student'),
    path('accept-invite/', views.AcceptInviteView.as_view(), name='accept-invite'),
    path('org/members/', views.OrgMembersView.as_view(), name='org-members'),
    path(
        'org/members/<int:user_id>/',
        views.OrgMemberRemoveView.as_view(),
        name='org-member-remove',
    ),
    path('org/invitations/', views.OrgInvitationsView.as_view(), name='org-invitations'),
    path('org/subscription/', views.OrgSubscriptionView.as_view(), name='org-subscription'),
    path(
        'org/invitations/<int:invitation_id>/resend/',
        views.ResendInvitationView.as_view(),
        name='org-invitation-resend',
    ),
    path(
        'org/invitations/<int:invitation_id>/',
        views.CancelInvitationView.as_view(),
        name='org-invitation-cancel',
    ),
]
