"""
User API Views
"""
import random
from datetime import timedelta

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken

from django.db import IntegrityError
from django.db.models import Count, Avg, Q, F
from django.conf import settings as django_settings
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.http import HttpResponseRedirect
from django.views import View
from urllib.parse import quote

from .models import User, OnboardCode, UserCategory, LLMConfiguration, GitProviderConnection, UserDevProfile
from .serializers import (
    UserSerializer,
    UserCreateSerializer,
    UserLLMConfigSerializer,
    ChangePasswordSerializer,
    UserCategorySerializer,
    UserCategoryDetailSerializer,
    UserDevProfileSerializer,
    GitProviderConnectionSerializer,
)


class IsAdminRole(permissions.BasePermission):
    """Allow access to users with role='admin' OR is_staff."""
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            (request.user.role == 'admin' or request.user.is_staff)
        )


class UserListView(generics.ListAPIView):
    """List all users (admin only)."""
    
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminRole]


class UserDetailView(generics.RetrieveUpdateAPIView):
    """Get/update a specific user."""
    
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.role == 'admin' or self.request.user.is_staff:
            return User.objects.all()
        return User.objects.filter(id=self.request.user.id)


class CurrentUserView(APIView):
    """Get/update current authenticated user."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get current user profile."""
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
    
    def patch(self, request):
        """Update current user profile (partial update)."""
        serializer = UserSerializer(
            request.user, 
            data=request.data, 
            partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RegisterView(generics.CreateAPIView):
    """Register a new user."""
    
    queryset = User.objects.all()
    serializer_class = UserCreateSerializer
    permission_classes = [permissions.AllowAny]
    
    def create(self, request, *args, **kwargs):
        """Create user and return user data with tokens."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generate JWT tokens
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)


class ChangePasswordView(APIView):
    """Change user password."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Change password for authenticated user."""
        serializer = ChangePasswordSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                serializer.errors, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check old password
        if not request.user.check_password(serializer.data.get('old_password')):
            return Response(
                {'old_password': ['Wrong password.']},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Set new password
        request.user.set_password(serializer.data.get('new_password'))
        request.user.save()
        
        # Update session to prevent logout
        update_session_auth_hash(request, request.user)
        
        return Response({
            'message': 'Password updated successfully'
        }, status=status.HTTP_200_OK)


class UserByEmailView(APIView):
    """Find user by email (internal API for FastAPI — protected by X-API-Key)."""

    def get_permissions(self):
        from reviewhub.permissions import IsInternalAPIKey
        return [IsInternalAPIKey()]
    
    def get(self, request):
        email = request.query_params.get('email')
        if not email:
            return Response(
                {'error': 'Email required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(email=email)
            serializer = UserSerializer(user)
            return Response(serializer.data)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class OnboardCheckEmailView(APIView):
    """Check if email exists and send OTP code for onboarding."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip().lower()
        if not email:
            return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'found': False})

        if user.onboard_completed:
            return Response({'found': True, 'alreadyOnboarded': True})

        # Generate 5-digit code
        code = f"{random.randint(0, 99999):05d}"

        # Save code with 15-minute expiry
        OnboardCode.objects.create(
            user=user,
            code=code,
            expires_at=timezone.now() + timedelta(minutes=15),
        )

        # Log code to console (email sending not implemented yet)
        print(f"[ONBOARD] Code for {email}: {code}")

        return Response({
            'found': True,
            'username': user.username,
            'codeSent': True,
        })


class OnboardVerifyCodeView(APIView):
    """Verify OTP code for onboarding."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip().lower()
        code = request.data.get('code', '').strip()

        if not email or not code:
            return Response({'error': 'Email and code are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'valid': False, 'error': 'Invalid or expired code'})

        # Find valid (not used, not expired) code
        onboard_code = OnboardCode.objects.filter(
            user=user,
            code=code,
            used=False,
            expires_at__gt=timezone.now(),
        ).order_by('-created_at').first()

        if not onboard_code:
            return Response({'valid': False, 'error': 'Invalid or expired code'})

        # Mark code as used
        onboard_code.used = True
        onboard_code.save()

        # Generate short-lived token (5 min) for password reset
        token = AccessToken.for_user(user)
        token.set_exp(lifetime=timedelta(minutes=5))

        return Response({
            'valid': True,
            'token': str(token),
        })


class OnboardSetPasswordView(APIView):
    """Set password for first-time onboarding."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        token_str = request.data.get('token', '')
        password = request.data.get('password', '')

        if not token_str or not password:
            return Response({'error': 'Token and password are required'}, status=status.HTTP_400_BAD_REQUEST)

        if len(password) < 8:
            return Response({'error': 'Password must be at least 8 characters'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = AccessToken(token_str)
            user_id = token['user_id']
            user = User.objects.get(id=user_id)
        except Exception:
            return Response({'error': 'Invalid or expired token'}, status=status.HTTP_400_BAD_REQUEST)

        user.password = make_password(password)
        user.onboard_completed = True
        user.save()

        return Response({'success': True})


# ─── User Categories ──────────────────────────────────────────────────────

class UserCategoryListCreateView(generics.ListCreateAPIView):
    """List / create user categories for the current admin."""
    
    serializer_class = UserCategorySerializer
    permission_classes = [IsAdminRole]
    
    def get_queryset(self):
        return UserCategory.objects.filter(created_by=self.request.user)


class UserCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get / update / delete a single category."""
    
    permission_classes = [IsAdminRole]
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return UserCategoryDetailSerializer
        return UserCategorySerializer
    
    def get_queryset(self):
        return UserCategory.objects.filter(created_by=self.request.user)


# ─── Admin: all users with stats ──────────────────────────────────────────

class AdminUserListView(APIView):
    """Return all non-admin users with evaluation/finding stats."""
    
    permission_classes = [IsAdminRole]
    
    def get(self, request):
        from evaluations.models import Evaluation, Finding
        
        search = request.query_params.get('search', '').strip()
        category_id = request.query_params.get('category')
        project_id = request.query_params.get('project')
        
        qs = User.objects.exclude(role='admin').exclude(is_staff=True)
        
        if search:
            qs = qs.filter(
                Q(username__icontains=search) |
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search)
            )
        
        if category_id:
            qs = qs.filter(categories__id=category_id)
        
        if project_id:
            qs = qs.filter(project_memberships__project_id=project_id)
        
        qs = qs.annotate(
            total_evaluations=Count('evaluations', distinct=True),
            total_findings=Count('evaluations__findings', distinct=True),
            avg_score=Avg('evaluations__overall_score'),
            total_commits=Count('evaluations', distinct=True),
            fixed_findings=Count(
                'evaluations__findings',
                filter=Q(evaluations__findings__is_fixed=True),
                distinct=True,
            ),
        )
        
        users_data = []
        for u in qs:
            fix_rate = 0
            if u.total_findings and u.total_findings > 0:
                fix_rate = round((u.fixed_findings / u.total_findings) * 100, 1)
            
            users_data.append({
                'id': u.id,
                'username': u.username,
                'email': u.email,
                'first_name': u.first_name,
                'last_name': u.last_name,
                'display_name': u.display_name,
                'avatar_url': u.avatar_url,
                'role': u.role,
                'categories': list(u.categories.values('id', 'name')),
                'total_evaluations': u.total_evaluations,
                'total_findings': u.total_findings,
                'avg_score': round(u.avg_score or 0, 1),
                'total_commits': u.total_commits,
                'fixed_findings': u.fixed_findings,
                'fix_rate': fix_rate,
            })
        
        return Response(users_data)


# ─── LLM Configuration (Admin) ────────────────────────────────────────────

class LLMConfigView(APIView):
    """Get/create/update LLM configurations for the current admin."""

    permission_classes = [IsAdminRole]

    def get(self, request):
        configs = LLMConfiguration.objects.filter(user=request.user)
        data = []
        for c in configs:
            masked = ""
            if c.api_key:
                masked = ("*" * 20) + c.api_key[-4:]
            row = {
                'provider': c.provider,
                'auth_method': c.auth_method,
                'model': c.model,
                'is_default': c.is_default,
            }
            if c.auth_method == LLMConfiguration.AuthMethod.ACCESS_TOKEN:
                row['access_token'] = masked
                row['api_key'] = ""
            elif c.auth_method == LLMConfiguration.AuthMethod.API_KEY:
                row['api_key'] = masked
                row['access_token'] = ""
            else:
                row['api_key'] = ""
                row['access_token'] = ""
            data.append(row)
        return Response({'configs': data})

    def post(self, request):
        provider = request.data.get('provider', '').strip()

        if request.data.get('is_default_only'):
            if not provider:
                return Response(
                    {'error': 'Provider is required'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                cfg = LLMConfiguration.objects.get(user=request.user, provider=provider)
            except LLMConfiguration.DoesNotExist:
                return Response(
                    {'error': 'Configuration not found'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            LLMConfiguration.objects.filter(user=request.user).update(is_default=False)
            cfg.is_default = True
            cfg.save(update_fields=['is_default', 'updated_at'])
            return Response({'success': True})

        model = (request.data.get('model') or '').strip()
        is_default = bool(request.data.get('is_default', False))
        auth_method = (request.data.get('auth_method') or LLMConfiguration.AuthMethod.API_KEY).strip()

        valid_methods = {m for m, _ in LLMConfiguration.AuthMethod.choices}
        if auth_method not in valid_methods:
            auth_method = LLMConfiguration.AuthMethod.API_KEY

        if auth_method == LLMConfiguration.AuthMethod.OAUTH_GOOGLE:
            return Response(
                {
                    'error': 'Use “Sign in with Google” in the UI to connect Gemini via OAuth.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not provider:
            return Response({'error': 'Provider is required'}, status=status.HTTP_400_BAD_REQUEST)

        api_key_in = (request.data.get('api_key') or '').strip()
        access_token_in = (request.data.get('access_token') or '').strip()

        try:
            existing = LLMConfiguration.objects.get(user=request.user, provider=provider)
        except LLMConfiguration.DoesNotExist:
            existing = None

        secret_to_store = None
        if auth_method == LLMConfiguration.AuthMethod.API_KEY:
            if api_key_in and not api_key_in.startswith('*'):
                secret_to_store = api_key_in
            elif existing and existing._api_key and len(bytes(existing._api_key)) > 0:
                secret_to_store = None
            elif not existing:
                return Response(
                    {'error': 'API key is required'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            if access_token_in and not access_token_in.startswith('*'):
                secret_to_store = access_token_in
            elif existing and existing._api_key and len(bytes(existing._api_key)) > 0:
                secret_to_store = None
            elif not existing:
                return Response(
                    {'error': 'Access token is required'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if existing and existing.auth_method != auth_method:
            if secret_to_store is None:
                return Response(
                    {
                        'error': 'Changing authentication method requires a new API key or access token.',
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if is_default:
            LLMConfiguration.objects.filter(user=request.user).update(is_default=False)

        config, created = LLMConfiguration.objects.get_or_create(
            user=request.user,
            provider=provider,
            defaults={
                'model': model,
                'is_default': is_default,
                'auth_method': auth_method,
            },
        )
        config.auth_method = auth_method
        if secret_to_store:
            config.api_key = secret_to_store
        config.clear_oauth_tokens()
        if model:
            config.model = model
        config.is_default = is_default
        if created and LLMConfiguration.objects.filter(user=request.user).count() == 1:
            config.is_default = True
        config.save()

        return Response({'success': True})


class LLMConfigTestView(APIView):
    """
    Send a minimal prompt ("How are you?") to verify API key and model.
    Body: { "provider": "openai" } uses saved config, or pass api_key/model to test before save.
    """

    permission_classes = [IsAdminRole]

    def post(self, request):
        from .llm_test import LLMTestError, ping_llm, ping_llm_with_config
        from .models import LLMConfiguration

        provider = (request.data.get("provider") or "").strip().lower()
        if provider not in ("openai", "anthropic", "google"):
            return Response(
                {"success": False, "error": "Invalid or missing provider."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_secret = (
            (request.data.get("api_key") or request.data.get("access_token") or "")
            .strip()
        )
        raw_model = (request.data.get("model") or "").strip()
        use_saved = not raw_secret or raw_secret.startswith("*")

        try:
            if use_saved:
                try:
                    cfg = LLMConfiguration.objects.get(
                        user=request.user, provider=provider
                    )
                except LLMConfiguration.DoesNotExist:
                    return Response(
                        {
                            "success": False,
                            "error": "No saved configuration for this provider. Save or paste credentials first.",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                model = raw_model or (cfg.model or "").strip()
                if not model:
                    return Response(
                        {"success": False, "error": "Model is required."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                reply = ping_llm_with_config(cfg)
            else:
                model = raw_model
                if not model:
                    return Response(
                        {
                            "success": False,
                            "error": "Model is required when testing new credentials.",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                reply = ping_llm(provider, raw_secret, model)
        except LLMTestError as e:
            return Response({"success": False, "error": str(e)}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"success": False, "error": f"Connection failed: {e!s}"},
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "success": True,
                "message": f'LLM replied: "{reply}"',
                "reply_preview": reply,
            },
            status=status.HTTP_200_OK,
        )


class GoogleLLMOAuthStartView(APIView):
    """Begin Google OAuth for Gemini (returns URL to open in the browser)."""

    permission_classes = [IsAdminRole]

    def post(self, request):
        from . import llm_google_oauth

        model = (request.data.get("model") or "").strip()
        if not model:
            return Response(
                {"error": "Model is required before starting Google sign-in."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not llm_google_oauth._configured():
            return Response(
                {
                    "error": "Google OAuth is not configured. Set GOOGLE_OAUTH_CLIENT_ID and "
                    "GOOGLE_OAUTH_CLIENT_SECRET (and BACKEND_PUBLIC_URL for the redirect URI) on the server.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        signer = TimestampSigner(salt="reviewhub-llm-google-oauth")
        state = signer.sign(f"{request.user.pk}:{model}")
        try:
            url = llm_google_oauth.build_authorization_url(state)
        except RuntimeError as e:
            return Response({"error": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"authorization_url": url})


class GoogleLLMOAuthCallbackView(View):
    """Google redirects here after consent (browser GET, no JWT)."""

    def get(self, request):
        from .llm_google_oauth import apply_initial_oauth_tokens, exchange_code_for_tokens

        fe = django_settings.FRONTEND_URL.rstrip("/")
        err_base = f"{fe}/settings?tab=llm"

        oauth_err = request.GET.get("error")
        if oauth_err:
            return HttpResponseRedirect(f"{err_base}&llm_oauth_error={quote(oauth_err)}")
        code = request.GET.get("code")
        state = request.GET.get("state")
        if not code or not state:
            return HttpResponseRedirect(
                f"{err_base}&llm_oauth_error={quote('missing_code_or_state')}"
            )

        signer = TimestampSigner(salt="reviewhub-llm-google-oauth")
        try:
            raw = signer.unsign(state, max_age=600)
            uid_str, model = raw.split(":", 1)
            user = User.objects.get(pk=int(uid_str))
        except (BadSignature, SignatureExpired, ValueError, User.DoesNotExist):
            return HttpResponseRedirect(
                f"{err_base}&llm_oauth_error={quote('invalid_or_expired_state')}"
            )

        try:
            tokens = exchange_code_for_tokens(code)
        except Exception as e:
            return HttpResponseRedirect(
                f"{err_base}&llm_oauth_error={quote(str(e)[:220])}"
            )

        config, _ = LLMConfiguration.objects.get_or_create(
            user=user,
            provider="google",
            defaults={
                "model": model,
                "auth_method": LLMConfiguration.AuthMethod.OAUTH_GOOGLE,
                "is_default": False,
            },
        )
        config.auth_method = LLMConfiguration.AuthMethod.OAUTH_GOOGLE
        config.api_key = None
        config.clear_oauth_tokens()
        apply_initial_oauth_tokens(config, tokens)
        config.model = model
        if not LLMConfiguration.objects.filter(user=user, is_default=True).exists():
            config.is_default = True
        config.save()

        return HttpResponseRedirect(f"{err_base}&llm_oauth_success=1")


class LLMConfigDeleteView(APIView):
    """Delete a single LLM provider config."""

    permission_classes = [IsAdminRole]

    def delete(self, request, provider):
        LLMConfiguration.objects.filter(user=request.user, provider=provider).delete()
        return Response({'success': True})


class GitHubPersonalAccessTokenView(APIView):
    """
    Optional encrypted GitHub PAT for the current user (batch branch discovery on private repos).
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        raw = user.github_personal_access_token
        last_four = None
        if raw and len(raw) >= 4:
            last_four = raw[-4:]
        return Response({
            'configured': user.has_github_personal_access_token,
            'last_four': last_four,
        })

    def post(self, request):
        token = (request.data.get('token') or '').strip()
        user = request.user
        if not token:
            user.github_personal_access_token = None
        else:
            user.github_personal_access_token = token
        user.save(update_fields=['_github_personal_access_token', 'updated_at'])
        return Response({'success': True})

    def delete(self, request):
        user = request.user
        user.github_personal_access_token = None
        user.save(update_fields=['_github_personal_access_token', 'updated_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class GitProviderConnectionListCreateView(generics.ListCreateAPIView):
    """List / create Git host identities for the current user (multiple allowed)."""

    serializer_class = GitProviderConnectionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return GitProviderConnection.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            self.perform_create(serializer)
        except IntegrityError:
            return Response(
                {'username': ['You already have this provider and username linked.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class GitProviderConnectionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get / update / delete one Git connection (own rows only)."""

    serializer_class = GitProviderConnectionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return GitProviderConnection.objects.filter(user=self.request.user)


class AdaptiveProfileView(APIView):
    """
    Phase 5 – Adaptive Developer Profile.
    Returns level, strengths, weaknesses, frequent patterns and recommendations
    for the given user. Used by the AI engine to personalise LLM prompts.

    Protected by internal API key so the AI engine can call it without a JWT.
    Admins can request any user; regular users can only fetch their own profile.
    """

    def get_permissions(self):
        from reviewhub.permissions import IsInternalAPIKey
        return [IsInternalAPIKey()]

    def get(self, request, pk: int):
        from django.db.models import Avg
        from skills.models import SkillMetric
        from evaluations.models import Pattern, Evaluation

        STRENGTH_THRESHOLD = 70
        WEAKNESS_THRESHOLD = 45
        PATTERN_THRESHOLD = 3
        PATTERN_DECAY_DAYS = 7

        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        project_id = request.query_params.get("project")

        # ── Skill aggregation ────────────────────────────────────────────────
        metrics_qs = SkillMetric.objects.filter(user=user).select_related("skill")
        if project_id:
            metrics_qs = metrics_qs.filter(project_id=project_id)

        strengths: list[str] = []
        weaknesses: list[str] = []
        total_score = 0.0
        skill_count = 0

        for m in metrics_qs:
            score = m.score
            slug = m.skill.slug
            total_score += score
            skill_count += 1
            if score >= STRENGTH_THRESHOLD:
                strengths.append(slug)
            elif score <= WEAKNESS_THRESHOLD:
                weaknesses.append(slug)

        avg_score = (total_score / skill_count) if skill_count else 50.0

        # ── Evaluation count ─────────────────────────────────────────────────
        eval_qs = Evaluation.objects.filter(author=user)
        if project_id:
            eval_qs = eval_qs.filter(project_id=project_id)
        evaluation_count = eval_qs.count()

        # ── Level ────────────────────────────────────────────────────────────
        if evaluation_count < 10:
            level = "beginner"
        elif avg_score >= 75 and evaluation_count >= 50:
            level = "advanced"
        elif avg_score >= 50:
            level = "intermediate"
        else:
            level = "beginner"

        # ── Pattern decay (run opportunistically, max once per 7 days) ───────
        now = timezone.now()
        decay_cutoff = now - timedelta(days=PATTERN_DECAY_DAYS)
        stale_patterns = Pattern.objects.filter(
            user=user, is_resolved=False,
            last_seen__lt=decay_cutoff,
        )
        for p in stale_patterns:
            p.apply_decay()

        # ── Frequent patterns ─────────────────────────────────────────────────
        pattern_qs = Pattern.objects.filter(
            user=user, is_resolved=False, frequency__gte=PATTERN_THRESHOLD
        ).order_by("-frequency")
        if project_id:
            pattern_qs = pattern_qs.filter(project_id=project_id)

        frequent_patterns = [
            {
                "pattern_key": p.pattern_key,
                "pattern_type": p.pattern_type,
                "count": p.frequency,
                "first_seen": p.first_seen.isoformat(),
                "last_seen": p.last_seen.isoformat(),
            }
            for p in pattern_qs[:10]
        ]

        # ── Recommendations ───────────────────────────────────────────────────
        PATTERN_RECOMMENDATIONS = {
            "missing_edge_cases": "Study defensive programming and boundary testing",
            "poor_error_handling": "Read error-handling best practices for your language",
            "no_input_validation": "Review OWASP input validation guidelines",
            "hardcoded_values": "Learn about configuration management and constants",
            "missing_tests": "Practice TDD by writing tests before code",
            "code_duplication": "Study the DRY principle and refactoring patterns",
            "security_exposure": "Take a secure-coding course for your stack",
            "performance_issues": "Learn profiling tools for your language",
        }
        recommendations: list[str] = []
        for slug in (weaknesses + [p["pattern_key"].split(":")[0] for p in frequent_patterns]):
            rec = PATTERN_RECOMMENDATIONS.get(slug)
            if rec and rec not in recommendations:
                recommendations.append(rec)

        # ── UserDevProfile enrichment ─────────────────────────────────────────
        dev_profile_data: dict = {}
        try:
            dp = user.dev_profile
            dev_profile_data = {
                "job_role": dp.job_role,
                "primary_language": dp.primary_language,
                "experience_years": dp.experience_years,
                "current_goal": dp.current_goal,
                "learning_style": dp.learning_style,
                "want_to_improve": dp.want_to_improve,
                "enjoy_most": dp.enjoy_most,
            }
        except UserDevProfile.DoesNotExist:
            pass

        return Response({
            "user_id": user.id,
            "level": level,
            "avg_score": round(avg_score, 1),
            "evaluation_count": evaluation_count,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "frequent_patterns": frequent_patterns,
            "recommendations": recommendations[:5],
            **dev_profile_data,
        })


class DevProfileView(APIView):
    """
    GET  /api/users/me/dev-profile/ — return existing dev profile or 404
    POST /api/users/me/dev-profile/ — create or update profile, seed SkillMetric
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            profile = request.user.dev_profile
        except UserDevProfile.DoesNotExist:
            return Response({'detail': 'No profile yet.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(UserDevProfileSerializer(profile).data)

    def post(self, request):
        try:
            profile = request.user.dev_profile
            serializer = UserDevProfileSerializer(profile, data=request.data, partial=True)
        except UserDevProfile.DoesNotExist:
            serializer = UserDevProfileSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        profile = serializer.save(user=request.user)
        self._seed_skill_metrics(request.user, profile)

        return Response(UserDevProfileSerializer(profile).data, status=status.HTTP_200_OK)

    @staticmethod
    def _seed_skill_metrics(user, profile: UserDevProfile):
        """
        Map self_scores (1-5) → SkillMetric initial score (40-100).
        Seeds one record per (user, project, skill) for each project the user belongs to.
        Only creates new records; does not overwrite metrics that already have real data.
        """
        from skills.models import Skill, SkillMetric
        from projects.models import Project, ProjectMember

        self_scores: dict = profile.self_scores or {}
        if not self_scores:
            return

        # Seed for every project the user is a member of (or created)
        from django.db.models import Q
        user_projects = Project.objects.filter(
            Q(created_by=user) | Q(members__user=user)
        ).distinct()

        if not user_projects.exists():
            # No projects yet — seeding deferred until the user joins one
            return

        for slug, raw_score in self_scores.items():
            try:
                skill = Skill.objects.get(slug=slug)
            except Skill.DoesNotExist:
                continue

            initial_score = profile.skill_score_for_metric(int(raw_score))

            for project in user_projects:
                metric, created = SkillMetric.objects.get_or_create(
                    user=user,
                    project=project,
                    skill=skill,
                    defaults={'score': initial_score},
                )
                if not created and metric.issue_count == 0:
                    # No real data yet — update from new self-assessment
                    metric.score = initial_score
                    metric.save(update_fields=['score'])


class DevCalibrationSummaryView(APIView):
    """
    GET /api/users/me/dev-calibration/?job=<batch_job_id>
    Aggregates questionnaire (UserDevProfile), optional batch job status,
    batch-derived DeveloperProfile (if any), and LLM evaluation stats for the results page.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from batch.models import BatchJob, DeveloperProfile
        from batch.serializers import DeveloperProfileSerializer, BatchJobListSerializer
        from evaluations.models import Evaluation, Finding, FindingSkill
        from skills.models import Skill

        # Admin can view any user's profile via ?user=<id>
        target_user = request.user
        user_id_param = request.query_params.get('user')
        if user_id_param and (request.user.role == 'admin' or request.user.is_staff):
            try:
                target_user = User.objects.get(pk=user_id_param)
            except User.DoesNotExist:
                pass

        job_param = request.query_params.get('job')
        batch_job = None
        if job_param:
            batch_job = BatchJob.objects.filter(pk=job_param, user=target_user).first()
        if batch_job is None:
            batch_job = (
                BatchJob.objects.filter(user=target_user).order_by('-created_at').first()
            )

        questionnaire = None
        try:
            questionnaire = UserDevProfileSerializer(target_user.dev_profile).data
        except UserDevProfile.DoesNotExist:
            pass

        job_data = BatchJobListSerializer(batch_job).data if batch_job else None

        developer_profile_data = None
        try:
            dp = DeveloperProfile.objects.get(user=target_user)
            developer_profile_data = DeveloperProfileSerializer(dp).data
        except DeveloperProfile.DoesNotExist:
            pass

        evals = Evaluation.objects.for_user(target_user)
        if batch_job:
            evals = evals.filter(batch_job=batch_job)

        agg = evals.aggregate(cnt=Count('id'), avg=Avg('overall_score'))
        eval_ids = list(evals.values_list('pk', flat=True))
        total_findings = (
            Finding.objects.filter(evaluation_id__in=eval_ids).count()
            if eval_ids
            else 0
        )

        severity_breakdown: dict = {}
        if eval_ids:
            for row in (
                Finding.objects.filter(evaluation_id__in=eval_ids)
                .values('severity')
                .annotate(c=Count('id'))
            ):
                severity_breakdown[row['severity']] = row['c']

        skill_counts: dict[str, int] = {}
        if eval_ids:
            for fs in FindingSkill.objects.filter(
                finding__evaluation_id__in=eval_ids
            ).select_related('skill'):
                slug = fs.skill.slug
                skill_counts[slug] = skill_counts.get(slug, 0) + 1

        top_skill_issues = []
        for slug, cnt in sorted(skill_counts.items(), key=lambda x: -x[1])[:10]:
            try:
                sk = Skill.objects.get(slug=slug)
                top_skill_issues.append(
                    {'slug': slug, 'name': sk.name, 'issue_count': cnt}
                )
            except Skill.DoesNotExist:
                top_skill_issues.append(
                    {'slug': slug, 'name': slug.replace('_', ' '), 'issue_count': cnt}
                )

        evaluation_insights = {
            'evaluation_count': agg['cnt'] or 0,
            'avg_score': round(agg['avg'] or 0, 1),
            'total_findings': total_findings,
            'severity_breakdown': severity_breakdown,
            'top_skill_issues': top_skill_issues,
        }

        return Response(
            {
                'questionnaire': questionnaire,
                'batch_job': job_data,
                'developer_profile': developer_profile_data,
                'evaluation_insights': evaluation_insights,
            }
        )
