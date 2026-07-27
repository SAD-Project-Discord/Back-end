from api.models import MessageReaction, Sticker, StickerPack
from api.services.messages import MessageServiceError, get_message


def list_sticker_packs():
    return StickerPack.objects.all().prefetch_related("stickers")


def get_sticker_pack(pack_id):
    try:
        return StickerPack.objects.prefetch_related("stickers").get(public_id=pack_id)
    except StickerPack.DoesNotExist as exc:
        raise MessageServiceError("NOT_FOUND", "پک استیکر یافت نشد.", 404) from exc


def add_message_reaction(user, message_id, emoji=None, sticker_id=None):
    if not emoji and not sticker_id:
        raise MessageServiceError("VALIDATION_ERROR", "ارسال ایموجی یا استیکر الزامی است.", 400)

    message = get_message(message_id, requester=user)
    sticker = None

    if sticker_id:
        try:
            sticker = Sticker.objects.get(public_id=sticker_id)
        except Sticker.DoesNotExist as exc:
            raise MessageServiceError("NOT_FOUND", "استیکر مورد نظر یافت نشد.", 404) from exc

    reaction, created = MessageReaction.objects.get_or_create(
        message=message,
        user=user,
        emoji=emoji or "",
        sticker=sticker,
    )
    return reaction


def remove_message_reaction(user, message_id, reaction_id):
    message = get_message(message_id, requester=user)
    try:
        reaction = MessageReaction.objects.get(
            public_id=reaction_id,
            message=message,
            user=user,
        )
    except MessageReaction.DoesNotExist as exc:
        raise MessageServiceError("NOT_FOUND", "واکنش مورد نظر یافت نشد.", 404) from exc

    reaction.delete()
    return True
