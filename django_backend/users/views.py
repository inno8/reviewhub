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

from .models import User, OnboardCode
from .serializers import (
    UserSerializer,
    UserCreateSerializer,
    UserLLMConfigSerializer,
    ChangePasswordSerializer
)


class UserListView(generics.ListAPIView):
    """List all users (admin only)."""
    
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]


class UserDetailView(generics.RetrieveUpdateAPIView):
    """Get/update a specific user."""
    
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Users can only see themselves unless admin
        if self.request.user.is_staff:
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
    """Find user by email (internal API for FastAPI)."""
    
    permission_classes = [permissions.AllowAny]  # TODO: Add API key auth
    
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


class DevProfileView(APIView):
    """GET/POST developer profile questionnaire data."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Return the user's dev profile data."""
        user = request.user
        if not user.dev_profile_completed:
            return Response(
                {"completed": False, "data": {}},
                status=status.HTTP_200_OK
            )
        return Response({
            "completed": True,
            "data": user.dev_profile_data or {},
        })

    def post(self, request):
        """Save developer profile questionnaire answers."""
        user = request.user
        user.dev_profile_data = request.data
        user.dev_profile_completed = True
        user.save(update_fields=['dev_profile_data', 'dev_profile_completed'])
        return Response({
            "completed": True,
            "data": user.dev_profile_data,
        }, status=status.HTTP_200_OK)
