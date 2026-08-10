from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from api.serializers import MessageReactionSerializer, StickerPackSerializer
from api.services.messages import MessageServiceError
from api.services.stickers import (
    add_message_reaction,
    get_sticker_pack,
    list_sticker_packs,
    remove_message_reaction,
)
from api.utils.responses import error_response, no_content_response, success_response


def _handle_service_error(exc):
    return error_response(exc.code, exc.message, exc.status_code)


@extend_schema(
    tags=["Stickers"],
    summary="List available sticker packs",
    description="Returns all available sticker packs and their stickers.",
    responses={200: StickerPackSerializer(many=True)},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def sticker_packs_list(request):
    packs = list_sticker_packs()
    return success_response(StickerPackSerializer(packs, many=True).data)


@extend_schema(
    tags=["Stickers"],
    summary="Get sticker pack details",
    description="Retrieves a specific sticker pack by ID.",
    responses={
        200: StickerPackSerializer,
        404: OpenApiResponse(description="Sticker pack not found."),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def sticker_pack_detail(request, pack_id):
    try:
        pack = get_sticker_pack(pack_id)
    except MessageServiceError as exc:
        return _handle_service_error(exc)
    return success_response(StickerPackSerializer(pack).data)


@extend_schema(
    tags=["Messages"],
    summary="Add reaction to message",
    description="Adds an emoji or sticker reaction to a message.",
    request=MessageReactionSerializer,
    responses={
        201: MessageReactionSerializer,
        400: OpenApiResponse(description="Emoji or sticker_id is required."),
        404: OpenApiResponse(description="Message not found."),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_reaction_view(request, message_id):
    emoji = request.data.get("emoji")
    sticker_id = request.data.get("sticker_id")
    try:
        reaction = add_message_reaction(request.user, message_id, emoji=emoji, sticker_id=sticker_id)
    except MessageServiceError as exc:
        return _handle_service_error(exc)

    return success_response(MessageReactionSerializer(reaction).data, status.HTTP_201_CREATED)


@extend_schema(
    tags=["Messages"],
    summary="Remove reaction from message",
    description="Removes a specific reaction from a message.",
    responses={
        204: OpenApiResponse(description="Reaction removed successfully."),
        404: OpenApiResponse(description="Reaction not found."),
    },
)
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def remove_reaction_view(request, message_id, reaction_id):
    try:
        remove_message_reaction(request.user, message_id, reaction_id)
    except MessageServiceError as exc:
        return _handle_service_error(exc)

    return no_content_response()
