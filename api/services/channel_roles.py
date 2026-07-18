from django.db import IntegrityError, transaction

from api.models import (
    AccessPermission,
    AccessRole,
    Channel,
    ChannelMembership,
    User,
)
from api.services.access_control import (
    has_channel_permission,
)


class ChannelRoleServiceError(Exception):
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
        raise ChannelRoleServiceError(
            "NOT_FOUND",
            "کانال مورد نظر یافت نشد.",
            404,
        ) from exc


def _get_role_or_404(
    channel,
    role_id,
):
    try:
        return (
            AccessRole.objects.active()
            .get(
                public_id=role_id,
                channel=channel,
            )
        )
    except AccessRole.DoesNotExist as exc:
        raise ChannelRoleServiceError(
            "NOT_FOUND",
            "نقش مورد نظر یافت نشد.",
            404,
        ) from exc


def _get_user_or_404(user_id):
    try:
        return User.objects.get(
            public_id=user_id,
            deleted_at__isnull=True,
        )
    except User.DoesNotExist as exc:
        raise ChannelRoleServiceError(
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
            .prefetch_related("custom_roles")
            .get(
                channel=channel,
                user=user,
            )
        )
    except ChannelMembership.DoesNotExist as exc:
        raise ChannelRoleServiceError(
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
        raise ChannelRoleServiceError(
            "FORBIDDEN",
            "شما عضو این کانال نیستید.",
            403,
        )


def _require_manage_roles(
    channel,
    user,
):
    if not has_channel_permission(
        channel,
        user,
        AccessPermission.MANAGE_ROLES,
    ):
        raise ChannelRoleServiceError(
            "FORBIDDEN",
            "شما اجازه مدیریت نقش‌های این کانال را ندارید.",
            403,
        )


def list_channel_roles(
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
        AccessRole.objects.active()
        .filter(channel=channel)
        .select_related(
            "channel",
            "created_by",
        )
        .order_by("created_at")
    )


@transaction.atomic
def create_channel_role(
    channel_id,
    requester,
    data,
):
    channel = _get_channel_or_404(
        channel_id
    )

    _require_manage_roles(
        channel,
        requester,
    )

    name = data["name"].strip()

    duplicate_exists = (
        AccessRole.objects.active()
        .filter(
            channel=channel,
            name__iexact=name,
        )
        .exists()
    )

    if duplicate_exists:
        raise ChannelRoleServiceError(
            "CONFLICT",
            "نقشی با این نام در کانال وجود دارد.",
            409,
        )

    try:
        return AccessRole.objects.create(
            channel=channel,
            name=name,
            permissions=list(
                data.get("permissions", [])
            ),
            created_by=requester,
        )
    except IntegrityError as exc:
        raise ChannelRoleServiceError(
            "CONFLICT",
            "نقشی با این نام در کانال وجود دارد.",
            409,
        ) from exc


@transaction.atomic
def update_channel_role(
    channel_id,
    role_id,
    requester,
    data,
):
    channel = _get_channel_or_404(
        channel_id
    )

    _require_manage_roles(
        channel,
        requester,
    )

    role = _get_role_or_404(
        channel,
        role_id,
    )

    update_fields = []

    if "name" in data:
        name = data["name"].strip()

        duplicate_exists = (
            AccessRole.objects.active()
            .filter(
                channel=channel,
                name__iexact=name,
            )
            .exclude(pk=role.pk)
            .exists()
        )

        if duplicate_exists:
            raise ChannelRoleServiceError(
                "CONFLICT",
                "نقشی با این نام در کانال وجود دارد.",
                409,
            )

        role.name = name
        update_fields.append("name")

    if "permissions" in data:
        role.permissions = list(
            data["permissions"]
        )
        update_fields.append("permissions")

    update_fields.append("updated_at")

    role.save(
        update_fields=update_fields
    )

    return role


@transaction.atomic
def delete_channel_role(
    channel_id,
    role_id,
    requester,
):
    channel = _get_channel_or_404(
        channel_id
    )

    _require_manage_roles(
        channel,
        requester,
    )

    role = _get_role_or_404(
        channel,
        role_id,
    )

    role.channel_memberships.clear()
    role.soft_delete()

    return role


@transaction.atomic
def assign_channel_role(
    channel_id,
    member_user_id,
    role_id,
    requester,
):
    channel = _get_channel_or_404(
        channel_id
    )

    _require_manage_roles(
        channel,
        requester,
    )

    role = _get_role_or_404(
        channel,
        role_id,
    )

    member_user = _get_user_or_404(
        member_user_id
    )

    membership = _get_membership_or_404(
        channel,
        member_user,
    )

    membership.custom_roles.add(role)

    return membership


@transaction.atomic
def remove_assigned_channel_role(
    channel_id,
    member_user_id,
    role_id,
    requester,
):
    channel = _get_channel_or_404(
        channel_id
    )

    _require_manage_roles(
        channel,
        requester,
    )

    role = _get_role_or_404(
        channel,
        role_id,
    )

    member_user = _get_user_or_404(
        member_user_id
    )

    membership = _get_membership_or_404(
        channel,
        member_user,
    )

    if not membership.custom_roles.filter(
        pk=role.pk
    ).exists():
        raise ChannelRoleServiceError(
            "NOT_FOUND",
            "این نقش به عضو مورد نظر اختصاص داده نشده است.",
            404,
        )

    membership.custom_roles.remove(role)

    return membership