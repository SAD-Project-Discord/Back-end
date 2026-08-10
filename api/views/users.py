from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
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
from api.services.storage import delete_replaced_avatar
from api.services.users import list_user_contacts, search_users
from api.utils.responses import error_response, success_response


@extend_schema(
    tags=["Users & Contacts"],
    summary="Get or update current user profile",
    description="GET: Returns profile of current authenticated user.\nPATCH/PUT: Updates current user profile (name, bio, avatar_url) and privacy settings if provided.",
    methods=["GET"],
    responses={200: UserSerializer},
)
@extend_schema(
    tags=["Users & Contacts"],
    summary="Update current user profile",
    description="Updates current user profile details (name, bio, avatar_url/profile_picture) and optional privacy settings.",
    methods=["PATCH", "PUT"],
    request=UpdateUserProfileSerializer,
    responses={
        200: UserSerializer,
        400: OpenApiResponse(description="Validation error."),
        401: OpenApiResponse(description="Unauthorized."),
    },
)
@api_view(["GET", "PATCH", "PUT"])
@permission_classes([IsAuthenticated])
def my_profile(request):
    if request.method == "GET":
        return success_response(
            UserSerializer(request.user).data
        )

    old_avatar = request.user.profile_picture

    serializer = UpdateUserProfileSerializer(
        request.user,
        data=request.data,
        partial=True,
    )

    if not serializer.is_valid():
        return error_response(
            "VALIDATION_ERROR",
            "Invalid profile data.",
            status.HTTP_400_BAD_REQUEST,
            serializer.errors,
        )

    user = serializer.save()

    if old_avatar != user.profile_picture:
        delete_replaced_avatar(request.user, old_avatar, user.profile_picture)

    # Also handle privacy settings if passed in same request
    if "group_add_permission" in request.data or "allow_direct_add" in request.data:
        privacy_serializer = UserPrivacySettingSerializer(
            get_user_privacy(request.user),
            data=request.data,
            partial=True,
        )
        if privacy_serializer.is_valid():
            update_user_privacy(request.user, privacy_serializer.validated_data)

    return success_response(
        UserSerializer(user).data
    )


@extend_schema(
    tags=["Users & Contacts"],
    summary="Get or update privacy settings",
    description="GET: Retrieves current user privacy settings.\nPATCH/PUT: Updates group_add_permission (everyone/contacts/nobody) and allow_direct_add (boolean).",
    methods=["GET"],
    responses={200: UserPrivacySettingSerializer},
)
@extend_schema(
    tags=["Users & Contacts"],
    summary="Update privacy settings",
    description="Updates privacy preferences.",
    methods=["PATCH", "PUT"],
    request=UserPrivacySettingSerializer,
    responses={200: UserPrivacySettingSerializer, 400: OpenApiResponse(description="Validation error.")},
)
@api_view(["GET", "PATCH", "PUT"])
@permission_classes([IsAuthenticated])
def user_privacy_view(request):
    privacy = get_user_privacy(request.user)
    if request.method == "GET":
        return success_response(UserPrivacySettingSerializer(privacy).data)

    serializer = UserPrivacySettingSerializer(privacy, data=request.data, partial=True)
    if not serializer.is_valid():
        return error_response(
            "VALIDATION_ERROR",
            "Invalid privacy settings data.",
            status.HTTP_400_BAD_REQUEST,
            serializer.errors,
        )

    updated_privacy = update_user_privacy(request.user, serializer.validated_data)
    return success_response(UserPrivacySettingSerializer(updated_privacy).data)


@extend_schema(
    tags=["Users & Contacts"],
    summary="Search users",
    description="Searches users by username, name, email, or public ID.",
    parameters=[
        OpenApiParameter(name="q", description="Search query term", required=False, type=str),
        OpenApiParameter(name="limit", description="Max number of users to return", required=False, type=int),
    ],
    responses={200: PublicUserProfileSerializer(many=True)},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def search_users_view(request):
    query = request.query_params.get("q", "")
    limit = request.query_params.get("limit", 20)
    users_list = search_users(query, current_user=request.user, limit=limit)
    return success_response(
        PublicUserProfileSerializer(users_list, many=True).data
    )


@extend_schema(
    tags=["Users & Contacts"],
    summary="List direct message contacts",
    description="Returns users with whom the authenticated user has exchanged direct messages.",
    parameters=[
        OpenApiParameter(name="q", description="Filter contacts by search query", required=False, type=str),
        OpenApiParameter(name="limit", description="Max number of contacts to return", required=False, type=int),
    ],
    responses={200: PublicUserProfileSerializer(many=True)},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_contacts_view(request):
    query = request.query_params.get("q", "")
    limit = request.query_params.get("limit", 50)
    contacts_list = list_user_contacts(request.user, query=query, limit=limit)
    return success_response(
        PublicUserProfileSerializer(contacts_list, many=True).data
    )


@extend_schema(
    tags=["Users & Contacts"],
    summary="Get user profile by ID",
    description="Retrieves public profile of a user by public ID.",
    responses={
        200: PublicUserProfileSerializer,
        404: OpenApiResponse(description="User not found."),
    },
)
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
            "Requested user not found.",
            status.HTTP_404_NOT_FOUND,
        )

    return success_response(
        PublicUserProfileSerializer(user).data
    )