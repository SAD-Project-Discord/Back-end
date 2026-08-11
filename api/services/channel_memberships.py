from django.db import IntegrityError, transaction

from api.models import (
    AccessPermission,
    Channel,
    ChannelMembership,
    User,
)
from api.services.access_control import (
    has_channel_permission,
)


class ChannelMembershipServiceError(Exception):
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


def _get_channel_or_404(channel_id):
    try:
        return Channel.objects.active().get(
            public_id=channel_id
        )
    except Channel.DoesNotExist as exc:
        raise ChannelMembershipServiceError(
            "NOT_FOUND",
            "کانال مورد نظر یافت نشد.",
            404,
        ) from exc


def _get_user_or_404(user_id):
    try:
        return User.objects.get(
            public_id=user_id,
            deleted_at__isnull=True,
        )
    except User.DoesNotExist as exc:
        raise ChannelMembershipServiceError(
            "NOT_FOUND",
            "کاربر مورد نظر یافت نشد.",
            404,
        ) from exc


def _get_membership_or_404(
    channel,
    user,
):
    try:
        return (
            ChannelMembership.objects
            .select_related(
                "channel",
                "user",
            )
            .prefetch_related("custom_roles")
            .get(
                channel=channel,
                user=user,
            )
        )
    except ChannelMembership.DoesNotExist as exc:
        raise ChannelMembershipServiceError(
            "NOT_FOUND",
            "کاربر عضو این کانال نیست.",
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
        raise ChannelMembershipServiceError(
            "FORBIDDEN",
            "شما عضو این کانال نیستید.",
            403,
        )


def _require_manage_members(
    channel,
    user,
):
    if not has_channel_permission(
        channel,
        user,
        AccessPermission.MANAGE_CHANNEL_MEMBERS,
    ):
        raise ChannelMembershipServiceError(
            "FORBIDDEN",
            "شما اجازه مدیریت اعضای این کانال را ندارید.",
            403,
        )


def list_channel_members(
    channel_id,
    requester,
):
    channel = _get_channel_or_404(channel_id)

    _require_channel_member(
        channel,
        requester,
    )

    return (
        ChannelMembership.objects
        .filter(channel=channel)
        .select_related("user")
        .prefetch_related("custom_roles")
        .order_by("joined_at")
    )


@transaction.atomic
def add_channel_member(
    channel_id,
    requester,
    user_id,
):
    channel = _get_channel_or_404(channel_id)

    _require_manage_members(
        channel,
        requester,
    )

    user = _get_user_or_404(user_id)

    if ChannelMembership.objects.filter(
        channel=channel,
        user=user,
    ).exists():
        raise ChannelMembershipServiceError(
            "CONFLICT",
            "این کاربر در حال حاضر عضو کانال است.",
            409,
        )

    try:
        return ChannelMembership.objects.create(
            channel=channel,
            user=user,
            role=ChannelMembership.Role.MEMBER,
        )
    except IntegrityError as exc:
        raise ChannelMembershipServiceError(
            "CONFLICT",
            "این کاربر در حال حاضر عضو کانال است.",
            409,
        ) from exc


@transaction.atomic
def update_channel_member_role(
    channel_id,
    member_user_id,
    requester,
    role,
):
    channel = _get_channel_or_404(channel_id)

    requester_membership = (
        ChannelMembership.objects
        .select_for_update()
        .filter(
            channel=channel,
            user=requester,
        )
        .first()
    )

    if (
        requester_membership is None
        or requester_membership.role
        != ChannelMembership.Role.OWNER
    ):
        raise ChannelMembershipServiceError(
            "FORBIDDEN",
            "فقط مالک کانال می‌تواند نقش مدیریتی اعضا را تغییر دهد.",
            403,
        )

    member_user = _get_user_or_404(
        member_user_id
    )

    membership = (
        ChannelMembership.objects
        .select_for_update()
        .filter(
            channel=channel,
            user=member_user,
        )
        .first()
    )

    if membership is None:
        raise ChannelMembershipServiceError(
            "NOT_FOUND",
            "کاربر عضو این کانال نیست.",
            404,
        )

    if (
        membership.role
        == ChannelMembership.Role.OWNER
    ):
        raise ChannelMembershipServiceError(
            "FORBIDDEN",
            "نقش مالک کانال قابل تغییر نیست.",
            403,
        )

    membership.role = role
    membership.save(
        update_fields=["role"]
    )

    return membership


@transaction.atomic
def remove_channel_member(
    channel_id,
    member_user_id,
    requester,
):
    channel = _get_channel_or_404(channel_id)

    requester_membership = (
        ChannelMembership.objects
        .select_for_update()
        .filter(
            channel=channel,
            user=requester,
        )
        .first()
    )

    if requester_membership is None:
        raise ChannelMembershipServiceError(
            "FORBIDDEN",
            "شما عضو این کانال نیستید.",
            403,
        )

    _require_manage_members(
        channel,
        requester,
    )

    member_user = _get_user_or_404(
        member_user_id
    )

    target_membership = (
        ChannelMembership.objects
        .select_for_update()
        .filter(
            channel=channel,
            user=member_user,
        )
        .first()
    )

    if target_membership is None:
        raise ChannelMembershipServiceError(
            "NOT_FOUND",
            "کاربر عضو این کانال نیست.",
            404,
        )

    if (
        target_membership.role
        == ChannelMembership.Role.OWNER
    ):
        raise ChannelMembershipServiceError(
            "FORBIDDEN",
            "مالک کانال را نمی‌توان حذف کرد.",
            403,
        )

    requester_is_owner = (
        requester_membership.role
        == ChannelMembership.Role.OWNER
    )

    target_is_admin = (
        target_membership.role
        == ChannelMembership.Role.ADMIN
    )

    if target_is_admin and not requester_is_owner:
        raise ChannelMembershipServiceError(
            "FORBIDDEN",
            "فقط مالک کانال می‌تواند مدیر را حذف کند.",
            403,
        )

    target_membership.delete()

    from api.constants import channel_room_name
    from api.tasks import broadcast_message_event_task
    broadcast_message_event_task.delay(
        "channel.member_removed",
        channel_room_name(channel.public_id),
        {
            "channel_id": channel.public_id,
            "user_id": member_user.public_id,
            "removed_by": requester.public_id,
        },
    )


@transaction.atomic
def leave_channel(
    channel_id,
    user,
):
    channel = _get_channel_or_404(channel_id)

    membership = (
        ChannelMembership.objects
        .select_for_update()
        .filter(
            channel=channel,
            user=user,
        )
        .first()
    )

    if membership is None:
        raise ChannelMembershipServiceError(
            "NOT_FOUND",
            "شما عضو این کانال نیستید.",
            404,
        )

    if (
        membership.role
        == ChannelMembership.Role.OWNER
    ):
        raise ChannelMembershipServiceError(
            "CONFLICT",
            "مالک کانال نمی‌تواند کانال را ترک کند.",
            409,
        )

    membership.delete()