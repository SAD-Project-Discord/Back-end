from django.contrib.auth import authenticate
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.exceptions import TokenError

from api.models import AuthSession
from api.serializers import (
    AuthSessionSerializer,
    LoginSerializer,
    RefreshTokenSerializer,
    RegisterSerializer,
    UserSerializer,
)
from api.utils.responses import error_response, no_content_response, success_response
from api.utils.tokens import (
    create_session_and_tokens,
    get_session_from_refresh_token,
    rotate_session_tokens,
)


def _auth_payload(user, request):
    _, tokens = create_session_and_tokens(user, request)
    return {
        "user": UserSerializer(user).data,
        "tokens": tokens,
    }


@extend_schema(
    tags=["Authentication"],
    summary="Register a new user",
    description="Registers a new user with username, email, password, and optional full name. Returns user profile and JWT token pair (access & refresh).",
    request=RegisterSerializer,
    responses={
        201: OpenApiResponse(description="User created successfully with access and refresh tokens."),
        400: OpenApiResponse(description="Validation error (e.g. username/email already taken, password too short)."),
    },
)
@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response(
            "VALIDATION_ERROR",
            "Invalid registration data.",
            status.HTTP_400_BAD_REQUEST,
            serializer.errors,
        )

    user = serializer.save()
    return success_response(_auth_payload(user, request), status.HTTP_201_CREATED)


@extend_schema(
    tags=["Authentication"],
    summary="User login",
    description="Authenticates user with email and password. Returns user profile and JWT token pair.",
    request=LoginSerializer,
    responses={
        200: OpenApiResponse(description="Login successful."),
        400: OpenApiResponse(description="Validation error."),
        401: OpenApiResponse(description="Invalid credentials or account deleted."),
    },
)
@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    serializer = LoginSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response(
            "VALIDATION_ERROR",
            "Invalid request data.",
            status.HTTP_400_BAD_REQUEST,
            serializer.errors,
        )

    email = serializer.validated_data["email"]
    password = serializer.validated_data["password"]

    user = authenticate(request, username=email, password=password)
    if user is None or user.deleted_at is not None:
        return error_response(
            "UNAUTHORIZED",
            "Invalid email or password.",
            status.HTTP_401_UNAUTHORIZED,
        )

    return success_response(_auth_payload(user, request))


@extend_schema(
    tags=["Authentication"],
    summary="Refresh JWT tokens",
    description="Rotates access and refresh tokens using an active refresh token.",
    request=RefreshTokenSerializer,
    responses={
        200: OpenApiResponse(description="Tokens rotated successfully."),
        400: OpenApiResponse(description="Validation error."),
        401: OpenApiResponse(description="Token is invalid, revoked, or expired."),
    },
)
@api_view(["POST"])
@permission_classes([AllowAny])
def refresh(request):
    serializer = RefreshTokenSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response(
            "VALIDATION_ERROR",
            "Invalid request data.",
            status.HTTP_400_BAD_REQUEST,
            serializer.errors,
        )

    try:
        session = get_session_from_refresh_token(serializer.validated_data["refresh_token"])
    except TokenError:
        session = None

    if session is None:
        return error_response(
            "UNAUTHORIZED",
            "Token is invalid or expired.",
            status.HTTP_401_UNAUTHORIZED,
        )

    return success_response(rotate_session_tokens(session))


@extend_schema(
    tags=["Authentication"],
    summary="Logout session",
    description="Revokes the current authentication session associated with the provided refresh token.",
    request=RefreshTokenSerializer,
    responses={
        204: OpenApiResponse(description="Logged out successfully."),
        400: OpenApiResponse(description="Validation error."),
        401: OpenApiResponse(description="Invalid or expired token."),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request):
    serializer = RefreshTokenSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response(
            "VALIDATION_ERROR",
            "Invalid request data.",
            status.HTTP_400_BAD_REQUEST,
            serializer.errors,
        )

    try:
        session = get_session_from_refresh_token(serializer.validated_data["refresh_token"])
    except TokenError:
        session = None

    if session is None or session.user_id != request.user.id:
        return error_response(
            "UNAUTHORIZED",
            "Token is invalid or expired.",
            status.HTTP_401_UNAUTHORIZED,
        )

    session.revoke()
    return no_content_response()


@extend_schema(
    tags=["Authentication"],
    summary="Logout all sessions",
    description="Revokes all active authentication sessions for the authenticated user across all devices.",
    responses={
        204: OpenApiResponse(description="All sessions revoked successfully."),
        401: OpenApiResponse(description="Unauthorized."),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_all(request):
    from django.utils import timezone

    AuthSession.objects.filter(user=request.user, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )
    return no_content_response()


@extend_schema(
    tags=["Authentication"],
    summary="List active sessions",
    description="Returns a list of all active non-expired sessions for the authenticated user.",
    responses={
        200: AuthSessionSerializer(many=True),
        401: OpenApiResponse(description="Unauthorized."),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_sessions(request):
    from django.utils import timezone

    sessions = AuthSession.objects.filter(
        user=request.user,
        revoked_at__isnull=True,
        expires_at__gt=timezone.now(),
    )
    return success_response(AuthSessionSerializer(sessions, many=True).data)


@extend_schema(
    tags=["Authentication"],
    summary="Revoke specific session",
    description="Revokes a specific active session by session public ID.",
    responses={
        204: OpenApiResponse(description="Session revoked successfully."),
        401: OpenApiResponse(description="Unauthorized."),
        404: OpenApiResponse(description="Session not found."),
    },
)
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_session(request, session_id):
    try:
        session = AuthSession.objects.get(
            public_id=session_id,
            user=request.user,
            revoked_at__isnull=True,
        )
    except AuthSession.DoesNotExist:
        return error_response(
            "NOT_FOUND",
            "Session not found.",
            status.HTTP_404_NOT_FOUND,
        )

    session.revoke()
    return no_content_response()
