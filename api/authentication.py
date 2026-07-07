from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

from api.models import AuthSession


class SessionJWTAuthentication(JWTAuthentication):
    def get_validated_token(self, raw_token):
        validated_token = super().get_validated_token(raw_token)
        session_id = validated_token.get("sid")

        if not session_id:
            raise InvalidToken("Token contained no recognizable session identification.")

        try:
            session = AuthSession.objects.get(public_id=session_id)
        except AuthSession.DoesNotExist as exc:
            raise InvalidToken("Session not found.") from exc

        if not session.is_active:
            raise InvalidToken("Session has been revoked or expired.")

        return validated_token
