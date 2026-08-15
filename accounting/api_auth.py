# -*- coding: utf-8 -*-
"""
Authentication API Views for React Frontend Integration
========================================================
JWT-based authentication endpoints for the LogistikoCRM React frontend.

Endpoints:
    POST /api/auth/login/    - Obtain JWT tokens
    POST /api/auth/refresh/  - Refresh access token
    POST /api/auth/logout/   - Blacklist refresh token
    GET  /api/auth/me/       - Get current user info
    GET  /api/health/        - Health check endpoint
"""
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from drf_spectacular.utils import extend_schema, OpenApiExample

from common.utils.api_response import api_success, api_error

User = get_user_model()


# ==============================================================================
# SERIALIZERS
# ==============================================================================

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom token serializer that includes user info in response."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add custom claims
        token['username'] = user.username
        token['email'] = user.email
        token['is_staff'] = user.is_staff
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        # Add user info to response
        data['user'] = {
            'id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'is_staff': self.user.is_staff,
            'is_superuser': self.user.is_superuser,
        }
        return data


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user info."""

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name',
                  'is_staff', 'is_superuser', 'is_active', 'date_joined', 'last_login']
        read_only_fields = fields


class LogoutSerializer(serializers.Serializer):
    """Serializer for logout request."""
    refresh = serializers.CharField(help_text="The refresh token to blacklist")


# ==============================================================================
# VIEWS
# ==============================================================================

class CustomTokenObtainPairView(TokenObtainPairView):
    """
    POST /api/auth/login/

    Obtain JWT access and refresh tokens.

    Request body:
        - username: string
        - password: string

    Response:
        - access: JWT access token
        - refresh: JWT refresh token
        - user: User object with id, username, email, etc.
    """
    serializer_class = CustomTokenObtainPairSerializer
    # Χωρίς δικό του scope το login έπεφτε στο γενικό anon throttle
    # (100/hour) — πολύ χαλαρό για endpoint που δοκιμάζει κωδικούς.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'


class CustomTokenRefreshView(TokenRefreshView):
    """
    POST /api/auth/refresh/

    Refresh the access token using a valid refresh token.

    Request body:
        - refresh: JWT refresh token

    Response:
        - access: New JWT access token
        - refresh: New JWT refresh token (if rotation is enabled)
    """
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'token_refresh'


class CustomTokenVerifyView(TokenVerifyView):
    """
    POST /api/auth/verify/

    Verify that a token is valid.

    Request body:
        - token: JWT token to verify

    Response:
        - 200: Token is valid
        - 401: Token is invalid or expired
    """
    pass


@extend_schema(
    request=LogoutSerializer,
    responses={
        200: {'description': 'Successfully logged out'},
        400: {'description': 'Invalid token'},
    },
    examples=[
        OpenApiExample(
            'Logout Request',
            value={'refresh': 'your-refresh-token-here'},
            request_only=True,
        ),
    ],
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    POST /api/auth/logout/

    Blacklist the refresh token to logout the user.

    Request body:
        - refresh: JWT refresh token to blacklist

    Response:
        - success: true/false
        - message: Status message
    """
    try:
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return api_error('Refresh token is required', status=400)

        token = RefreshToken(refresh_token)
        token.blacklist()

        return api_success(message='Successfully logged out')
    except Exception as e:
        return api_error(f'Invalid token: {str(e)}', status=400)


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile."""

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']


@extend_schema(
    responses={200: UserSerializer},
)
@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def current_user_view(request):
    """
    GET /api/auth/me/
    Get the currently authenticated user's information.

    PATCH /api/auth/me/
    Update the current user's profile (first_name, last_name, email).

    Response:
        - success: true
        - data: User object
    """
    if request.method == 'PATCH':
        serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return api_success(
                data=UserSerializer(request.user).data,
                message='Το προφίλ ενημερώθηκε επιτυχώς'
            )
        return api_error(
            'Σφάλμα επικύρωσης',
            status=400,
            errors=serializer.errors
        )

    serializer = UserSerializer(request.user)
    return api_success(data=serializer.data)


@extend_schema(
    responses={
        200: {'description': 'API is healthy'},
    },
)
@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    GET /api/health/

    Health check endpoint to verify the API is running.
    No authentication required.

    Response:
        - success: true
        - data: Status information
    """
    from django.conf import settings
    from django.db import connection

    # Check database connection
    db_healthy = True
    try:
        connection.ensure_connection()
    except Exception:
        db_healthy = False

    return api_success(data={
        'status': 'healthy',
        'database': 'connected' if db_healthy else 'disconnected',
        'debug': settings.DEBUG,
        'version': '1.0.0',
    })


@extend_schema(
    responses={200: {'description': 'API test response'}},
)
@api_view(['GET'])
@permission_classes([AllowAny])
def api_test(request):
    """
    GET /api/test/

    Simple test endpoint to verify the API setup.
    No authentication required.

    Response:
        - success: true
        - data: Test message
    """
    return api_success(
        data={
            'message': 'LogistikoCRM API is working!',
            'authenticated': request.user.is_authenticated,
            'user': request.user.username if request.user.is_authenticated else None,
        },
        message='API test successful'
    )
