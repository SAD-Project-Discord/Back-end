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


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def sticker_packs_list(request):
    packs = list_sticker_packs()
    return success_response(StickerPackSerializer(packs, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def sticker_pack_detail(request, pack_id):
    try:
        pack = get_sticker_pack(pack_id)
    except MessageServiceError as exc:
        return _handle_service_error(exc)
    return success_response(StickerPackSerializer(pack).data)


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


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def remove_reaction_view(request, message_id, reaction_id):
    try:
        remove_message_reaction(request.user, message_id, reaction_id)
    except MessageServiceError as exc:
        return _handle_service_error(exc)

    return no_content_response()
