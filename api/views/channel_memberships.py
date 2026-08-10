from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated

from api.serializers import (
    AddChannelMemberSerializer,
    ChannelMembershipSerializer,
    UpdateChannelMemberRoleSerializer,
)
from api.services.channel_memberships import (
    ChannelMembershipServiceError,
    add_channel_member,
    leave_channel,
    list_channel_members,
    remove_channel_member,
    update_channel_member_role,
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


@extend_schema(
    tags=["Channel Memberships"],
    summary="List members in channel",
    description="Returns list of members in the specified channel.",
    methods=["GET"],
    responses={200: ChannelMembershipSerializer(many=True)},
)
@extend_schema(
    tags=["Channel Memberships"],
    summary="Add member to channel",
    description="Adds a user to a channel (requires MANAGE_MEMBERS permission).",
    methods=["POST"],
    request=AddChannelMemberSerializer,
    responses={
        201: ChannelMembershipSerializer,
        400: OpenApiResponse(description="Validation error."),
        403: OpenApiResponse(description="Forbidden."),
        409: OpenApiResponse(description="User is already a channel member."),
    },
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def channel_member_list_create(
    request,
    channel_id,
):
    if request.method == "GET":
        try:
            memberships = list_channel_members(
                channel_id,
                request.user,
            )
        except ChannelMembershipServiceError as exc:
            return _handle_service_error(exc)

        return success_response(
            ChannelMembershipSerializer(
                memberships,
                many=True,
            ).data
        )

    serializer = AddChannelMemberSerializer(
        data=request.data
    )

    if not serializer.is_valid():
        return error_response(
            "VALIDATION_ERROR",
            "Invalid request data.",
            status.HTTP_400_BAD_REQUEST,
            serializer.errors,
        )

    try:
        membership = add_channel_member(
            channel_id,
            request.user,
            serializer.validated_data["user_id"],
        )
    except ChannelMembershipServiceError as exc:
        return _handle_service_error(exc)

    return success_response(
        ChannelMembershipSerializer(
            membership
        ).data,
        status.HTTP_201_CREATED,
    )


@extend_schema(
    tags=["Channel Memberships"],
    summary="Update channel member role",
    description="Updates role of a channel member (`admin` or `member`). Requires MANAGE_MEMBERS permission.",
    methods=["PATCH"],
    request=UpdateChannelMemberRoleSerializer,
    responses={200: ChannelMembershipSerializer, 400: OpenApiResponse(description="Validation error."), 403: OpenApiResponse(description="Forbidden.")},
)
@extend_schema(
    tags=["Channel Memberships"],
    summary="Remove member from channel",
    description="Removes a member from a channel.",
    methods=["DELETE"],
    responses={204: OpenApiResponse(description="Member removed successfully."), 403: OpenApiResponse(description="Forbidden.")},
)
@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def channel_member_detail(
    request,
    channel_id,
    user_id,
):
    if request.method == "PATCH":
        serializer = (
            UpdateChannelMemberRoleSerializer(
                data=request.data
            )
        )

        if not serializer.is_valid():
            return error_response(
                "VALIDATION_ERROR",
                "Invalid request data.",
                status.HTTP_400_BAD_REQUEST,
                serializer.errors,
            )

        try:
            membership = (
                update_channel_member_role(
                    channel_id,
                    user_id,
                    request.user,
                    serializer.validated_data[
                        "role"
                    ],
                )
            )
        except ChannelMembershipServiceError as exc:
            return _handle_service_error(exc)

        return success_response(
            ChannelMembershipSerializer(
                membership
            ).data
        )

    try:
        remove_channel_member(
            channel_id,
            user_id,
            request.user,
        )
    except ChannelMembershipServiceError as exc:
        return _handle_service_error(exc)

    return no_content_response()


@extend_schema(
    tags=["Channel Memberships"],
    summary="Leave channel",
    description="Removes the authenticated user from the channel.",
    responses={204: OpenApiResponse(description="Left channel successfully.")},
)
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def channel_leave(
    request,
    channel_id,
):
    try:
        leave_channel(
            channel_id,
            request.user,
        )
    except ChannelMembershipServiceError as exc:
        return _handle_service_error(exc)

    return no_content_response()