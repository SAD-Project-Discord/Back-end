from django.db import transaction

from api.models import (
    AccessPermission,
    Channel,
    ChannelMembership,
    Topic,
)
from api.services.access_control import (
    has_channel_permission,
)


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


def _require_channel_member(
    channel,
    user,
):
    if not ChannelMembership.objects.filter(
        channel=channel,
        user=user,
    ).exists():
        raise ChannelServiceError(
            "FORBIDDEN",
            "شما عضو این کانال نیستید.",
            403,
        )


def _require_channel_permission(
    channel,
    user,
    permission,
    message,
):
    if not has_channel_permission(
        channel,
        user,
        permission,
    ):
        raise ChannelServiceError(
            "FORBIDDEN",
            message,
            403,
        )


def _require_channel_owner(
    channel,
    user,
):
    is_owner = ChannelMembership.objects.filter(
        channel=channel,
        user=user,
        role=ChannelMembership.Role.OWNER,
    ).exists()

    if not is_owner:
        raise ChannelServiceError(
            "FORBIDDEN",
            "فقط مالک کانال اجازه حذف آن را دارد.",
            403,
        )


@transaction.atomic
def create_channel(creator, data):
    channel = Channel.objects.create(
        name=data["name"].strip(),
        description=data.get(
            "description",
            "",
        ).strip(),
        is_private=data.get("is_private", True),
        creator=creator,
    )

    ChannelMembership.objects.create(
        channel=channel,
        user=creator,
        role=ChannelMembership.Role.OWNER,
    )

    return channel


def list_channels(user):
    return (
        Channel.objects.active()
        .filter(
            memberships__user=user,
        )
        .select_related("creator")
        .distinct()
        .order_by("-created_at")
    )


def get_channel(
    channel_id,
    requester,
):
    channel = _get_channel_or_404(
        channel_id
    )

    is_member = ChannelMembership.objects.filter(
        channel=channel,
        user=requester,
    ).exists()

    if not is_member and channel.is_private:
        raise ChannelServiceError(
            "FORBIDDEN",
            "You are not a member of this private channel.",
            403,
        )

    return channel


@transaction.atomic
def update_channel(
    channel_id,
    requester,
    data,
):
    channel = _get_channel_or_404(channel_id)

    _require_channel_permission(
        channel,
        requester,
        AccessPermission.MANAGE_CHANNEL,
        "شما اجازه ویرایش این کانال را ندارید.",
    )

    update_fields = []

    if "name" in data:
        channel.name = data["name"].strip()
        update_fields.append("name")

    if "description" in data:
        channel.description = data[
            "description"
        ].strip()
        update_fields.append("description")

    if "is_private" in data:
        channel.is_private = data["is_private"]
        update_fields.append("is_private")

    update_fields.append("updated_at")

    channel.save(
        update_fields=update_fields
    )

    return channel


@transaction.atomic
def delete_channel(
    channel_id,
    requester,
):
    channel = _get_channel_or_404(channel_id)

    _require_channel_owner(
        channel,
        requester,
    )

    channel.soft_delete()

    return channel


@transaction.atomic
def create_topic(
    channel_id,
    creator,
    data,
):
    channel = _get_channel_or_404(channel_id)
    _require_channel_permission(
        channel,
        creator,
        AccessPermission.MANAGE_TOPICS,
        "شما اجازه مدیریت موضوعات این کانال را ندارید.",
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


def list_channel_topics(
    channel_id,
    requester,
):
    channel = _get_channel_or_404(
        channel_id
    )

    _require_channel_member(
        channel,
        requester,
    )

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
    requester,
):
    channel = _get_channel_or_404(
        channel_id
    )

    _require_channel_member(
        channel,
        requester,
    )

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
    _require_channel_permission(
        channel,
        requester,
        AccessPermission.MANAGE_TOPICS,
        "شما اجازه مدیریت موضوعات این کانال را ندارید.",
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
    _require_channel_permission(
        channel,
        requester,
        AccessPermission.MANAGE_TOPICS,
        "شما اجازه مدیریت موضوعات این کانال را ندارید.",
    )

    topic = _get_topic_or_404(
        channel,
        topic_id,
    )

    topic.soft_delete()

    return topic