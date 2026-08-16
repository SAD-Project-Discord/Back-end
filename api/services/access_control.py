from api.models import (
    AccessPermission,
    ChannelMembership,
    GroupMembership,
)


BUILTIN_GROUP_ROLE_PERMISSIONS = {
    GroupMembership.Role.OWNER: set(
        AccessPermission.values
    ),
    GroupMembership.Role.ADMIN: {
        AccessPermission.MANAGE_GROUP,
        AccessPermission.MANAGE_MEMBERS,
        AccessPermission.MANAGE_INVITATIONS,
        AccessPermission.SEND_MESSAGES,
        AccessPermission.DELETE_MESSAGES,
    },
    GroupMembership.Role.MEMBER: {
        AccessPermission.SEND_MESSAGES,
    },
}


BUILTIN_CHANNEL_ROLE_PERMISSIONS = {
    ChannelMembership.Role.OWNER: set(
        AccessPermission.values
    ),
    ChannelMembership.Role.ADMIN: set(
        AccessPermission.values
    ),
    ChannelMembership.Role.MEMBER: {
        AccessPermission.SEND_MESSAGES,
    },
}


def get_group_membership(group, user):
    return (
        GroupMembership.objects
        .filter(
            group=group,
            user=user,
        )
        .prefetch_related("custom_roles")
        .first()
    )


def get_effective_group_permissions(group, user):
    membership = get_group_membership(
        group,
        user,
    )

    if membership is None:
        return set()

    permissions = set(
        BUILTIN_GROUP_ROLE_PERMISSIONS.get(
            membership.role,
            set(),
        )
    )

    custom_roles = membership.custom_roles.filter(
        group=group,
        deleted_at__isnull=True,
    )

    for role in custom_roles:
        permissions.update(
            role.permissions
        )

    return permissions


def has_group_permission(
    group,
    user,
    permission,
):
    permissions = get_effective_group_permissions(
        group,
        user,
    )

    return permission in permissions


def get_channel_membership(channel, user):
    return (
        ChannelMembership.objects
        .filter(
            channel=channel,
            user=user,
        )
        .prefetch_related("custom_roles")
        .first()
    )


def get_effective_channel_permissions(
    channel,
    user,
):
    if getattr(channel, "creator_id", None) == user.id:
        return set(AccessPermission.values)

    membership = get_channel_membership(
        channel,
        user,
    )

    if membership is None:
        return set()

    if membership.role in {
        ChannelMembership.Role.OWNER,
        ChannelMembership.Role.ADMIN,
    }:
        return set(AccessPermission.values)

    permissions = set(
        BUILTIN_CHANNEL_ROLE_PERMISSIONS.get(
            membership.role,
            set(),
        )
    )

    custom_roles = membership.custom_roles.filter(
        channel=channel,
        deleted_at__isnull=True,
    )

    for role in custom_roles:
        permissions.update(
            role.permissions
        )

    return permissions


def has_channel_permission(
    channel,
    user,
    permission,
):
    permissions = (
        get_effective_channel_permissions(
            channel,
            user,
        )
    )

    return permission in permissions