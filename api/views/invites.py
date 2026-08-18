from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from api.serializers import InviteLinkPreviewSerializer, InviteLinkSerializer
from api.services.invites import (
    InviteServiceError,
    get_or_create_channel_invite_link,
    get_or_create_group_invite_link,
    join_by_invite_link,
    preview_invite_link,
    revoke_channel_invite_link,
    revoke_group_invite_link,
)
from api.utils.responses import error_response, no_content_response, success_response


def _handle_service_error(exc):
    return error_response(
        exc.code,
        exc.message,
        exc.status_code,
    )


@extend_schema(
    tags=["Groups"],
    summary="Get or create group invite link",
    description="Returns an active shareable invite link for the group, creating one if it does not exist.",
    responses={
        200: InviteLinkSerializer,
        403: OpenApiResponse(description="Forbidden."),
        404: OpenApiResponse(description="Group not found."),
    },
)
@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
def group_invite_link(request, group_id):
    if request.method == "DELETE":
        try:
            revoke_group_invite_link(group_id, request.user)
        except InviteServiceError as exc:
            return _handle_service_error(exc)
        return no_content_response()

    try:
        link = get_or_create_group_invite_link(group_id, request.user)
    except InviteServiceError as exc:
        return _handle_service_error(exc)

    return success_response(InviteLinkSerializer(link, context={"request": request}).data)


@extend_schema(
    tags=["Channels"],
    summary="Get or create channel invite link",
    description="Returns an active shareable invite link for the channel, creating one if it does not exist.",
    responses={
        200: InviteLinkSerializer,
        403: OpenApiResponse(description="Forbidden."),
        404: OpenApiResponse(description="Channel not found."),
    },
)
@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
def channel_invite_link(request, channel_id):
    if request.method == "DELETE":
        try:
            revoke_channel_invite_link(channel_id, request.user)
        except InviteServiceError as exc:
            return _handle_service_error(exc)
        return no_content_response()

    try:
        link = get_or_create_channel_invite_link(channel_id, request.user)
    except InviteServiceError as exc:
        return _handle_service_error(exc)

    return success_response(InviteLinkSerializer(link, context={"request": request}).data)


@extend_schema(
    tags=["Invites"],
    summary="Preview invite link",
    description="Previews a group/channel invite link before joining.",
    responses={
        200: InviteLinkPreviewSerializer,
        404: OpenApiResponse(description="Invite link invalid or expired."),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def invite_link_preview(request, token):
    try:
        data = preview_invite_link(token, request.user)
    except InviteServiceError as exc:
        return _handle_service_error(exc)

    return success_response(InviteLinkPreviewSerializer(data).data)


@extend_schema(
    tags=["Invites"],
    summary="Join via invite link",
    description="Joins the authenticated user to the group/channel referenced by the invite token.",
    responses={
        200: InviteLinkPreviewSerializer,
        404: OpenApiResponse(description="Invite link invalid or expired."),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def invite_link_join(request, token):
    try:
        data = join_by_invite_link(token, request.user)
    except InviteServiceError as exc:
        return _handle_service_error(exc)

    return success_response(InviteLinkPreviewSerializer(data).data)
