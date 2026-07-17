from api.models import (
    AccessPermission,
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