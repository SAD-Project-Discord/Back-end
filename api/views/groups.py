from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from api.serializers import (
    CreateGroupInvitationSerializer,
    CreateGroupSerializer,
    GroupInvitationSerializer,
    GroupSerializer,
    RespondGroupInvitationSerializer,
    UpdateGroupSerializer,
)
from api.services.groups import (
    GroupServiceError,
    create_group,
    create_group_invitation,
    delete_group,
    get_group,
    list_received_invitations,
    list_user_groups,
    respond_to_group_invitation,
    update_group,
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
def group_list_create(request):
    if request.method == "GET":
        groups = list_user_groups(request.user)

        return success_response(
            GroupSerializer(
                groups,
                many=True,
            ).data
        )

    serializer = CreateGroupSerializer(
        data=request.data
    )

    if not serializer.is_valid():
        return error_response(
            "VALIDATION_ERROR",
            "اطلاعات ارسالی نامعتبر است.",
            status.HTTP_400_BAD_REQUEST,
            serializer.errors,
        )

    group = create_group(
        request.user,
        serializer.validated_data,
    )

    return success_response(
        GroupSerializer(group).data,
        status.HTTP_201_CREATED,
    )


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def group_detail(request, group_id):
    if request.method == "GET":
        try:
            group = get_group(
                group_id,
                request.user,
            )
        except GroupServiceError as exc:
            return _handle_service_error(exc)

        return success_response(
            GroupSerializer(group).data
        )

    if request.method == "PATCH":
        serializer = UpdateGroupSerializer(
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
            group = update_group(
                group_id,
                request.user,
                serializer.validated_data,
            )
        except GroupServiceError as exc:
            return _handle_service_error(exc)

        return success_response(
            GroupSerializer(group).data
        )

    try:
        delete_group(
            group_id,
            request.user,
        )
    except GroupServiceError as exc:
        return _handle_service_error(exc)

    return no_content_response()


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def group_invitation_create(request, group_id):
    serializer = CreateGroupInvitationSerializer(
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
        invitation = create_group_invitation(
            group_id,
            request.user,
            serializer.validated_data["invitee_id"],
        )
    except GroupServiceError as exc:
        return _handle_service_error(exc)

    return success_response(
        GroupInvitationSerializer(invitation).data,
        status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def received_group_invitations(request):
    invitations = list_received_invitations(
        request.user
    )

    return success_response(
        GroupInvitationSerializer(
            invitations,
            many=True,
        ).data
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def group_invitation_respond(
    request,
    invitation_id,
):
    serializer = RespondGroupInvitationSerializer(
        data=request.data
    )

    if not serializer.is_valid():
        return error_response(
            "VALIDATION_ERROR",
            "عملیات باید accept یا reject باشد.",
            status.HTTP_400_BAD_REQUEST,
            serializer.errors,
        )

    try:
        invitation = respond_to_group_invitation(
            invitation_id,
            request.user,
            serializer.validated_data["action"],
        )
    except GroupServiceError as exc:
        return _handle_service_error(exc)

    return success_response(
        GroupInvitationSerializer(invitation).data
    )