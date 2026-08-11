from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from api.serializers import (
    AddGroupMemberSerializer,
    CreateGroupInvitationSerializer,
    CreateGroupSerializer,
    GroupInvitationSerializer,
    GroupMembershipSerializer,
    GroupSerializer,
    RespondGroupInvitationSerializer,
    UpdateGroupSerializer,
)
from api.services.groups import (
    GroupServiceError,
    add_group_member,
    create_group,
    create_group_invitation,
    delete_group,
    get_group,
    join_group,
    leave_group,
    list_group_members,
    list_public_groups,
    list_received_invitations,
    list_user_groups,
    remove_group_member,
    respond_to_group_invitation,
    update_group,
)


@extend_schema(
    tags=["Groups"],
    summary="List public groups",
    description="Returns list of public groups matching optional query parameter `q`.",
    responses={200: GroupSerializer(many=True)},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def group_public_list(request):
    query = request.query_params.get("q")
    groups = list_public_groups(query=query, requester=request.user)
    return success_response(GroupSerializer(groups, many=True).data)
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
    tags=["Groups"],
    summary="List groups",
    description="Returns list of groups that the authenticated user is a member of.",
    methods=["GET"],
    responses={200: GroupSerializer(many=True)},
)
@extend_schema(
    tags=["Groups"],
    summary="Create a new group",
    description="Creates a new group with the authenticated user as owner.",
    methods=["POST"],
    request=CreateGroupSerializer,
    responses={
        201: GroupSerializer,
        400: OpenApiResponse(description="Validation error."),
    },
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
            "Invalid request data.",
            status.HTTP_400_BAD_REQUEST,
            serializer.errors,
        )

    try:
        group = create_group(
            request.user,
            serializer.validated_data,
        )
    except GroupServiceError as exc:
        return _handle_service_error(exc)

    return success_response(
        GroupSerializer(group).data,
        status.HTTP_201_CREATED,
    )


@extend_schema(
    tags=["Groups"],
    summary="Get group details",
    description="Returns detailed information about a specific group.",
    methods=["GET"],
    responses={200: GroupSerializer, 404: OpenApiResponse(description="Group not found.")},
)
@extend_schema(
    tags=["Groups"],
    summary="Update group",
    description="Updates group details (name, description, avatar_url). Requires MANAGE_GROUP permission.",
    methods=["PATCH"],
    request=UpdateGroupSerializer,
    responses={200: GroupSerializer, 400: OpenApiResponse(description="Validation error."), 403: OpenApiResponse(description="Forbidden.")},
)
@extend_schema(
    tags=["Groups"],
    summary="Delete group",
    description="Soft-deletes a group. Only the group owner can perform this action.",
    methods=["DELETE"],
    responses={204: OpenApiResponse(description="Group deleted successfully."), 403: OpenApiResponse(description="Forbidden.")},
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
                "Invalid request data.",
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


@extend_schema(
    tags=["Groups"],
    summary="Create group invitation",
    description="Sends a group invitation to a target user. Requires MANAGE_INVITATIONS permission and respects target user's privacy settings.",
    request=CreateGroupInvitationSerializer,
    responses={
        201: GroupInvitationSerializer,
        400: OpenApiResponse(description="Validation error."),
        403: OpenApiResponse(description="User's privacy settings do not allow invitations."),
        409: OpenApiResponse(description="User is already a member or active invitation exists."),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def group_invitation_create(request, group_id):
    serializer = CreateGroupInvitationSerializer(
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


@extend_schema(
    tags=["Groups"],
    summary="List received group invitations",
    description="Lists all pending group invitations received by the authenticated user.",
    responses={200: GroupInvitationSerializer(many=True)},
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


@extend_schema(
    tags=["Groups"],
    summary="Respond to group invitation",
    description="Accepts or rejects a pending group invitation (`action`: `accept` or `reject`).",
    request=RespondGroupInvitationSerializer,
    responses={
        200: GroupInvitationSerializer,
        400: OpenApiResponse(description="Action must be 'accept' or 'reject'."),
        404: OpenApiResponse(description="Invitation not found."),
    },
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
            "Action must be accept or reject.",
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


@extend_schema(
    tags=["Groups"],
    summary="List members or directly add member to group",
    description="GET: Returns list of members in the specified group.\nPOST: Directly adds a user to the group by `user_id` or `username` (requires MANAGE_MEMBERS permission).",
    methods=["GET"],
    responses={200: GroupMembershipSerializer(many=True)},
)
@extend_schema(
    tags=["Groups"],
    summary="Add member directly to group",
    description="Directly adds a member to group by `user_id` or `username` (requires MANAGE_MEMBERS permission and target user privacy approval).",
    methods=["POST"],
    request=AddGroupMemberSerializer,
    responses={
        201: GroupMembershipSerializer,
        400: OpenApiResponse(description="Invalid user_id/username data."),
        403: OpenApiResponse(description="Forbidden or blocked by privacy setting."),
        409: OpenApiResponse(description="User is already a member of the group."),
    },
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def group_member_list(request, group_id):
    if request.method == "GET":
        try:
            memberships = list_group_members(
                group_id,
                request.user,
            )
        except GroupServiceError as exc:
            return _handle_service_error(exc)

        return success_response(
            GroupMembershipSerializer(
                memberships,
                many=True,
            ).data
        )

    serializer = AddGroupMemberSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response(
            "VALIDATION_ERROR",
            "Invalid member data.",
            status.HTTP_400_BAD_REQUEST,
            serializer.errors,
        )

    try:
        membership = add_group_member(
            group_id,
            request.user,
            user_id=serializer.validated_data.get("user_id"),
            username=serializer.validated_data.get("username"),
        )
    except GroupServiceError as exc:
        return _handle_service_error(exc)

    return success_response(
        GroupMembershipSerializer(membership).data,
        status.HTTP_201_CREATED,
    )


@extend_schema(
    tags=["Groups"],
    summary="Remove member from group",
    description="Removes a specified member from group. Requires MANAGE_MEMBERS permission or higher role than target member.",
    responses={
        204: OpenApiResponse(description="Member removed successfully."),
        403: OpenApiResponse(description="Forbidden."),
        404: OpenApiResponse(description="Member or group not found."),
    },
)
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def group_member_remove(
    request,
    group_id,
    user_id,
):
    try:
        remove_group_member(
            group_id,
            request.user,
            user_id,
        )
    except GroupServiceError as exc:
        return _handle_service_error(exc)

    return no_content_response()


@extend_schema(
    tags=["Groups"],
    summary="Leave group",
    description="Removes the authenticated user from the specified group. Group owner cannot leave without transferring ownership.",
    responses={
        204: OpenApiResponse(description="Left group successfully."),
        400: OpenApiResponse(description="Group owner cannot leave without transferring ownership."),
    },
)
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def group_leave(request, group_id):
    try:
        leave_group(
            group_id,
            request.user,
        )
    except GroupServiceError as exc:
        return _handle_service_error(exc)

    return no_content_response()


@extend_schema(
    tags=["Groups"],
    summary="Join public group",
    description="Joins a public group (`is_private=False`). Private groups require an invitation to join.",
    responses={
        200: GroupSerializer,
        403: OpenApiResponse(description="Cannot join a private group without an invitation."),
        404: OpenApiResponse(description="Group not found."),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def group_join(request, group_id):
    try:
        group, _ = join_group(group_id, request.user)
    except GroupServiceError as exc:
        return _handle_service_error(exc)

    return success_response(GroupSerializer(group).data)