from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

from api.serializers import LoginSerializer, RegisterSerializer, UserSerializer
from api.utils.responses import error_response, success_response
from api.utils.tokens import get_tokens_for_user


def _auth_payload(user):
    return {
        "user": UserSerializer(user).data,
        "tokens": get_tokens_for_user(user),
    }


@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response(
            "VALIDATION_ERROR",
            "اطلاعات ارسالی نامعتبر است.",
            status.HTTP_400_BAD_REQUEST,
            serializer.errors,
        )

    user = serializer.save()
    return success_response(_auth_payload(user), status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    serializer = LoginSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response(
            "VALIDATION_ERROR",
            "اطلاعات ارسالی نامعتبر است.",
            status.HTTP_400_BAD_REQUEST,
            serializer.errors,
        )

    email = serializer.validated_data["email"]
    password = serializer.validated_data["password"]

    user = authenticate(request, username=email, password=password)
    if user is None or user.deleted_at is not None:
        return error_response(
            "UNAUTHORIZED",
            "ایمیل یا رمز عبور نادرست است.",
            status.HTTP_401_UNAUTHORIZED,
        )

    return success_response(_auth_payload(user))
