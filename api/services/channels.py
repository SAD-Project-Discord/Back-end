from django.db import transaction

from api.models import Channel, Topic


class ChannelServiceError(Exception):
    def __init__(
        self,
        code,
        message,
        status_code=400,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _get_channel_or_404(public_id):
    try:
        return (
            Channel.objects.active()
            .select_related("creator")
            .get(public_id=public_id)
        )
    except Channel.DoesNotExist as exc:
        raise ChannelServiceError(
            "NOT_FOUND",
            "کانال مورد نظر یافت نشد.",
            404,
        ) from exc


def _get_topic_or_404(channel, topic_id):
    try:
        return (
            Topic.objects.active()
            .select_related(
                "channel",
                "creator",
            )
            .get(
                public_id=topic_id,
                channel=channel,
            )
        )
    except Topic.DoesNotExist as exc:
        raise ChannelServiceError(
            "NOT_FOUND",
            "موضوع مورد نظر یافت نشد.",
            404,
        ) from exc


def _require_channel_creator(channel, user):
    if channel.creator_id != user.id:
        raise ChannelServiceError(
            "FORBIDDEN",
            "فقط سازنده کانال اجازه انجام این عملیات را دارد.",
            403,
        )


@transaction.atomic
def create_channel(creator, data):
    return Channel.objects.create(
        name=data["name"].strip(),
        description=data.get(
            "description",
            "",
        ).strip(),
        creator=creator,
    )


def list_channels():
    return (
        Channel.objects.active()
        .select_related("creator")
        .order_by("-created_at")
    )


def get_channel(channel_id):
    return _get_channel_or_404(channel_id)


@transaction.atomic
def create_topic(
    channel_id,
    creator,
    data,
):
    channel = _get_channel_or_404(channel_id)
    _require_channel_creator(
        channel,
        creator,
    )

    name = data["name"].strip()

    duplicate_exists = Topic.objects.active().filter(
        channel=channel,
        name__iexact=name,
    ).exists()

    if duplicate_exists:
        raise ChannelServiceError(
            "CONFLICT",
            "موضوعی با این نام در کانال وجود دارد.",
            409,
        )

    return Topic.objects.create(
        channel=channel,
        name=name,
        description=data.get(
            "description",
            "",
        ).strip(),
        creator=creator,
    )


def list_channel_topics(channel_id):
    channel = _get_channel_or_404(channel_id)

    return (
        Topic.objects.active()
        .filter(channel=channel)
        .select_related(
            "channel",
            "creator",
        )
        .order_by("created_at")
    )


def get_channel_topic(
    channel_id,
    topic_id,
):
    channel = _get_channel_or_404(channel_id)

    return _get_topic_or_404(
        channel,
        topic_id,
    )


@transaction.atomic
def update_topic(
    channel_id,
    topic_id,
    requester,
    data,
):
    channel = _get_channel_or_404(channel_id)
    _require_channel_creator(
        channel,
        requester,
    )

    topic = _get_topic_or_404(
        channel,
        topic_id,
    )

    update_fields = []

    if "name" in data:
        name = data["name"].strip()

        duplicate_exists = (
            Topic.objects.active()
            .filter(
                channel=channel,
                name__iexact=name,
            )
            .exclude(pk=topic.pk)
            .exists()
        )

        if duplicate_exists:
            raise ChannelServiceError(
                "CONFLICT",
                "موضوعی با این نام در کانال وجود دارد.",
                409,
            )

        topic.name = name
        update_fields.append("name")

    if "description" in data:
        topic.description = data[
            "description"
        ].strip()
        update_fields.append("description")

    update_fields.append("updated_at")

    topic.save(
        update_fields=update_fields
    )

    return topic


@transaction.atomic
def delete_topic(
    channel_id,
    topic_id,
    requester,
):
    channel = _get_channel_or_404(channel_id)
    _require_channel_creator(
        channel,
        requester,
    )

    topic = _get_topic_or_404(
        channel,
        topic_id,
    )

    topic.soft_delete()

    return topic