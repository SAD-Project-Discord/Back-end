from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from api.models import User
from api.serializers import (
    PublicUserProfileSerializer,
    UpdateUserProfileSerializer,
    UserPrivacySettingSerializer,
    UserSerializer,
)
from api.services.privacy import get_user_privacy, update_user_privacy
from api.utils.responses import error_response, success_response


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def my_profile(request):
    if request.method == "GET":
        return success_response(
            UserSerializer(request.user).data
        )

    serializer = UpdateUserProfileSerializer(
        request.user,
        data=request.data,
        partial=True,
    )

    if not serializer.is_valid():
        return error_response(
            "VALIDATION_ERROR",
            "اطلاعات ارسالی نامعتبر است.",
            status.HTTP_400_BAD_REQUEST,
            serializer.errors,
        )

    user = serializer.save()

    return success_response(
        UserSerializer(user).data
    )


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def user_privacy_view(request):
    privacy = get_user_privacy(request.user)
    if request.method == "GET":
        return success_response(UserPrivacySettingSerializer(privacy).data)

    serializer = UserPrivacySettingSerializer(privacy, data=request.data, partial=True)
    if not serializer.is_valid():
        return error_response(
            "VALIDATION_ERROR",
            "اطلاعات حریم خصوصی نامعتبر است.",
            status.HTTP_400_BAD_REQUEST,
            serializer.errors,
        )

    updated_privacy = update_user_privacy(request.user, serializer.validated_data)
    return success_response(UserPrivacySettingSerializer(updated_privacy).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_profile(request, user_id):
    try:
        user = User.objects.get(
            public_id=user_id,
            deleted_at__isnull=True,
        )
    except User.DoesNotExist:
        return error_response(
            "NOT_FOUND",
            "کاربر مورد نظر یافت نشد.",
            status.HTTP_404_NOT_FOUND,
        )

    return success_response(
        PublicUserProfileSerializer(user).data
    )