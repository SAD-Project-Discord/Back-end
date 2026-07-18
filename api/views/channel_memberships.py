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
            "اطلاعات ارسالی نامعتبر است.",
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
                "اطلاعات ارسالی نامعتبر است.",
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