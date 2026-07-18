from rest_framework import status
from rest_framework.decorators import (
    api_view,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated

from api.serializers import (
    AccessRoleSerializer,
    AssignAccessRoleSerializer,
    ChannelMembershipSerializer,
    CreateAccessRoleSerializer,
    UpdateAccessRoleSerializer,
)
from api.services.channel_roles import (
    ChannelRoleServiceError,
    assign_channel_role,
    create_channel_role,
    delete_channel_role,
    list_channel_roles,
    remove_assigned_channel_role,
    update_channel_role,
)
from api.utils.responses import (
    error_response,
    no_content_response,
    success_response,
)


def _handle_service_error(exc):
    return error_response(
        exc.code,
        exc.message,
        exc.status_code,
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def channel_role_list_create(
    request,
    channel_id,
):
    if request.method == "GET":
        try:
            roles = list_channel_roles(
                channel_id,
                request.user,
            )
        except ChannelRoleServiceError as exc:
            return _handle_service_error(exc)

        return success_response(
            AccessRoleSerializer(
                roles,
                many=True,
            ).data
        )

    serializer = CreateAccessRoleSerializer(
        data=request.data
    )

    if not serializer.is_valid():
        return error_response(
            "VALIDATION_ERROR",
            "اطلاعات ارسالی نامعتبر است.",
            status.HTTP_400_BAD_REQUEST,
            serializer.errors,
        )

    try:
        role = create_channel_role(
            channel_id,
            request.user,
            serializer.validated_data,
        )
    except ChannelRoleServiceError as exc:
        return _handle_service_error(exc)

    return success_response(
        AccessRoleSerializer(role).data,
        status.HTTP_201_CREATED,
    )


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def channel_role_detail(
    request,
    channel_id,
    role_id,
):
    if request.method == "PATCH":
        serializer = UpdateAccessRoleSerializer(
            data=request.data
        )

        if not serializer.is_valid():
            return error_response(
                "VALIDATION_ERROR",
                "اطلاعات ارسالی نامعتبر است.",
                status.HTTP_400_BAD_REQUEST,
                serializer.errors,
            )

        try:
            role = update_channel_role(
                channel_id,
                role_id,
                request.user,
                serializer.validated_data,
            )
        except ChannelRoleServiceError as exc:
            return _handle_service_error(exc)

        return success_response(
            AccessRoleSerializer(role).data
        )

    try:
        delete_channel_role(
            channel_id,
            role_id,
            request.user,
        )
    except ChannelRoleServiceError as exc:
        return _handle_service_error(exc)

    return no_content_response()


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def channel_member_role_assign(
    request,
    channel_id,
    user_id,
):
    serializer = AssignAccessRoleSerializer(
        data=request.data
    )

    if not serializer.is_valid():
        return error_response(
            "VALIDATION_ERROR",
            "اطلاعات ارسالی نامعتبر است.",
            status.HTTP_400_BAD_REQUEST,
            serializer.errors,
        )

    try:
        membership = assign_channel_role(
            channel_id,
            user_id,
            serializer.validated_data["role_id"],
            request.user,
        )
    except ChannelRoleServiceError as exc:
        return _handle_service_error(exc)

    return success_response(
        ChannelMembershipSerializer(
            membership
        ).data
    )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def channel_member_role_remove(
    request,
    channel_id,
    user_id,
    role_id,
):
    try:
        membership = (
            remove_assigned_channel_role(
                channel_id,
                user_id,
                role_id,
                request.user,
            )
        )
    except ChannelRoleServiceError as exc:
        return _handle_service_error(exc)

    return success_response(
        ChannelMembershipSerializer(
            membership
        ).data
    )