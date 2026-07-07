import secrets

from django.conf import settings
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from api.models import AuthSession
from api.utils.device import parse_device


class SessionRefreshToken(RefreshToken):
    @classmethod
    def for_session(cls, user, session):
        token = cls.for_user(user)
        token["sid"] = session.public_id
        token.access_token["sid"] = session.public_id
        return token


def create_session_and_tokens(user, request):
    device = parse_device(request.META.get("HTTP_USER_AGENT", ""))
    expires_at = timezone.now() + settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]

    session = AuthSession.objects.create(
        user=user,
        refresh_jti=secrets.token_hex(16),
        device=device,
        expires_at=expires_at,
    )

    refresh = SessionRefreshToken.for_session(user, session)
    session.refresh_jti = refresh["jti"]
    session.save(update_fields=["refresh_jti"])

    return session, {
        "access_token": str(refresh.access_token),
        "refresh_token": str(refresh),
        "expires_in": int(refresh.access_token.lifetime.total_seconds()),
    }


def rotate_session_tokens(session):
    refresh = SessionRefreshToken.for_session(session.user, session)
    session.refresh_jti = refresh["jti"]
    session.expires_at = timezone.now() + settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]
    session.save(update_fields=["refresh_jti", "expires_at"])

    return {
        "access_token": str(refresh.access_token),
        "refresh_token": str(refresh),
        "expires_in": int(refresh.access_token.lifetime.total_seconds()),
    }


def get_session_from_refresh_token(refresh_token_str):
    refresh = RefreshToken(refresh_token_str)
    session_id = refresh.get("sid")
    jti = refresh.get("jti")

    if not session_id or not jti:
        return None

    try:
        session = AuthSession.objects.get(public_id=session_id, refresh_jti=jti)
    except AuthSession.DoesNotExist:
        return None

    if not session.is_active:
        return None

    return session
