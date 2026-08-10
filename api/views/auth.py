from django.contrib.auth import authenticate
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


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_all(request):
    from django.utils import timezone

    AuthSession.objects.filter(user=request.user, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )
    return no_content_response()


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
