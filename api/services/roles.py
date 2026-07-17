from django.db import IntegrityError, transaction

from api.models import (
    AccessPermission,
    AccessRole,
    Group,
    GroupMembership,
    User,
)
from api.services.access_control import (
    has_group_permission,
)


class RoleServiceError(Exception):
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


def _get_group_or_404(group_id):
    try:
        return Group.objects.active().get(
            public_id=group_id
        )
    except Group.DoesNotExist as exc:
        raise RoleServiceError(
            "NOT_FOUND",
            "گروه مورد نظر یافت نشد.",
            404,
        ) from exc


def _get_role_or_404(group, role_id):
    try:
        return (
            AccessRole.objects.active()
            .get(
                public_id=role_id,
                group=group,
            )
        )
    except AccessRole.DoesNotExist as exc:
        raise RoleServiceError(
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
        raise RoleServiceError(
            "NOT_FOUND",
            "کاربر مورد نظر یافت نشد.",
            404,
        ) from exc


def _get_membership_or_404(group, user):
    try:
        return GroupMembership.objects.get(
            group=group,
            user=user,
        )
    except GroupMembership.DoesNotExist as exc:
        raise RoleServiceError(
            "NOT_FOUND",
            "کاربر عضو این گروه نیست.",
            404,
        ) from exc


def _require_group_member(group, user):
    if not GroupMembership.objects.filter(
        group=group,
        user=user,
    ).exists():
        raise RoleServiceError(
            "FORBIDDEN",
            "شما عضو این گروه نیستید.",
            403,
        )


def _require_manage_roles(group, user):
    if not has_group_permission(
        group,
        user,
        AccessPermission.MANAGE_ROLES,
    ):
        raise RoleServiceError(
            "FORBIDDEN",
            "شما اجازه مدیریت نقش‌های این گروه را ندارید.",
            403,
        )


def list_group_roles(group_id, requester):
    group = _get_group_or_404(group_id)
    _require_group_member(group, requester)

    return (
        AccessRole.objects.active()
        .filter(group=group)
        .select_related(
            "group",
            "created_by",
        )
        .order_by("created_at")
    )


@transaction.atomic
def create_group_role(
    group_id,
    requester,
    data,
):
    group = _get_group_or_404(group_id)
    _require_manage_roles(group, requester)

    name = data["name"].strip()

    duplicate_exists = (
        AccessRole.objects.active()
        .filter(
            group=group,
            name__iexact=name,
        )
        .exists()
    )

    if duplicate_exists:
        raise RoleServiceError(
            "CONFLICT",
            "نقشی با این نام در گروه وجود دارد.",
            409,
        )

    try:
        return AccessRole.objects.create(
            group=group,
            name=name,
            permissions=list(
                data.get("permissions", [])
            ),
            created_by=requester,
        )
    except IntegrityError as exc:
        raise RoleServiceError(
            "CONFLICT",
            "نقشی با این نام در گروه وجود دارد.",
            409,
        ) from exc


@transaction.atomic
def update_group_role(
    group_id,
    role_id,
    requester,
    data,
):
    group = _get_group_or_404(group_id)
    _require_manage_roles(group, requester)

    role = _get_role_or_404(
        group,
        role_id,
    )

    update_fields = []

    if "name" in data:
        name = data["name"].strip()

        duplicate_exists = (
            AccessRole.objects.active()
            .filter(
                group=group,
                name__iexact=name,
            )
            .exclude(pk=role.pk)
            .exists()
        )

        if duplicate_exists:
            raise RoleServiceError(
                "CONFLICT",
                "نقشی با این نام در گروه وجود دارد.",
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
def delete_group_role(
    group_id,
    role_id,
    requester,
):
    group = _get_group_or_404(group_id)
    _require_manage_roles(group, requester)

    role = _get_role_or_404(
        group,
        role_id,
    )

    role.group_memberships.clear()
    role.soft_delete()

    return role


@transaction.atomic
def assign_group_role(
    group_id,
    member_user_id,
    role_id,
    requester,
):
    group = _get_group_or_404(group_id)
    _require_manage_roles(group, requester)

    role = _get_role_or_404(
        group,
        role_id,
    )

    member_user = _get_user_or_404(
        member_user_id
    )

    membership = _get_membership_or_404(
        group,
        member_user,
    )

    membership.custom_roles.add(role)

    return membership


@transaction.atomic
def remove_assigned_group_role(
    group_id,
    member_user_id,
    role_id,
    requester,
):
    group = _get_group_or_404(group_id)
    _require_manage_roles(group, requester)

    role = _get_role_or_404(
        group,
        role_id,
    )

    member_user = _get_user_or_404(
        member_user_id
    )

    membership = _get_membership_or_404(
        group,
        member_user,
    )

    if not membership.custom_roles.filter(
        pk=role.pk
    ).exists():
        raise RoleServiceError(
            "NOT_FOUND",
            "این نقش به عضو مورد نظر اختصاص داده نشده است.",
            404,
        )

    membership.custom_roles.remove(role)

    return membership