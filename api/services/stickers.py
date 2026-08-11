from api.models import MessageReaction, Sticker, StickerPack
from api.services.messages import MessageServiceError, get_message


OFFICIAL_STICKER_PACKS = [
    {
        "public_id": "spk_pepe_express",
        "name": "Pepe Expressions",
        "description": "Popular Pepe meme reaction stickers",
        "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f600.png",
        "stickers": [
            {"public_id": "stk_pepe_happy", "emoji_alias": "pepe_happy", "image_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f600.png"},
            {"public_id": "stk_pepe_cool", "emoji_alias": "pepe_cool", "image_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f60e.png"},
            {"public_id": "stk_pepe_heart", "emoji_alias": "pepe_heart", "image_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f60d.png"},
            {"public_id": "stk_pepe_think", "emoji_alias": "pepe_think", "image_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f914.png"},
            {"public_id": "stk_pepe_party", "emoji_alias": "pepe_party", "image_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f973.png"},
            {"public_id": "stk_pepe_mindblown", "emoji_alias": "pepe_mindblown", "image_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f92f.png"},
        ],
    },
    {
        "public_id": "spk_cute_cats",
        "name": "Cute Cats",
        "description": "Adorable cat stickers for every mood",
        "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f63a.png",
        "stickers": [
            {"public_id": "stk_cat_smile", "emoji_alias": "cat_smile", "image_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f63a.png"},
            {"public_id": "stk_cat_heart", "emoji_alias": "cat_heart", "image_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f63d.png"},
            {"public_id": "stk_cat_laugh", "emoji_alias": "cat_laugh", "image_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f638.png"},
            {"public_id": "stk_cat_kiss", "emoji_alias": "cat_kiss", "image_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f63b.png"},
            {"public_id": "stk_cat_surprised", "emoji_alias": "cat_surprised", "image_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f63c.png"},
        ],
    },
    {
        "public_id": "spk_discord_classics",
        "name": "Discord Reactions",
        "description": "Essential Discord chat reactions",
        "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f525.png",
        "stickers": [
            {"public_id": "stk_fire", "emoji_alias": "fire", "image_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f525.png"},
            {"public_id": "stk_rocket", "emoji_alias": "rocket", "image_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f680.png"},
            {"public_id": "stk_sparkles", "emoji_alias": "sparkles", "image_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/2728.png"},
            {"public_id": "stk_thumbsup", "emoji_alias": "thumbsup", "image_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f44d.png"},
            {"public_id": "stk_clap", "emoji_alias": "clap", "image_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f44f.png"},
        ],
    },
]


def seed_official_sticker_packs():
    for pack_data in OFFICIAL_STICKER_PACKS:
        pack, _ = StickerPack.objects.get_or_create(
            public_id=pack_data["public_id"],
            defaults={
                "name": pack_data["name"],
                "description": pack_data["description"],
                "icon_url": pack_data["icon_url"],
                "is_official": True,
            },
        )
        for stk_data in pack_data["stickers"]:
            Sticker.objects.get_or_create(
                public_id=stk_data["public_id"],
                pack=pack,
                defaults={
                    "emoji_alias": stk_data["emoji_alias"],
                    "image_url": stk_data["image_url"],
                },
            )


def list_sticker_packs():
    if not StickerPack.objects.exists():
        seed_official_sticker_packs()
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
