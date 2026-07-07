from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import InvalidToken

from api.authentication import SessionJWTAuthentication
from api.models import User


@database_sync_to_async
def _get_user(token):
    authenticator = SessionJWTAuthentication()
    validated_token = authenticator.get_validated_token(token)
    user_id = validated_token.get("sub")
    return User.objects.get(public_id=user_id, deleted_at__isnull=True, is_active=True)


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        scope["user"] = AnonymousUser()
        token = self._extract_token(scope)

        if token:
            try:
                scope["user"] = await _get_user(token)
            except (InvalidToken, User.DoesNotExist):
                scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)

    @staticmethod
    def _extract_token(scope):
        query_string = scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)
        if "token" in query_params and query_params["token"]:
            return query_params["token"][0]

        for header_name, header_value in scope.get("headers", []):
            if header_name.decode().lower() == "authorization":
                value = header_value.decode()
                if value.lower().startswith("bearer "):
                    return value[7:]
        return None
