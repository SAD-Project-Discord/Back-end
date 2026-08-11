from django.db import IntegrityError, transaction
from django.utils import timezone

from api.models import (
    AccessPermission,
    Group,
    GroupInvitation,
    GroupMembership,
    User,
)

from api.services.access_control import (
    has_group_permission,
)


class GroupServiceError(Exception):
    def __init__(self, code, message, status_code=400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _get_group_or_404(public_id):
    try:
        return Group.objects.active().get(public_id=public_id)
    except Group.DoesNotExist as exc:
        raise GroupServiceError(
            "NOT_FOUND",
            "Group not found.",
            404,
        ) from exc


def _get_user_or_404(public_id):
    try:
        return User.objects.get(
            public_id=public_id,
            deleted_at__isnull=True,
        )
    except User.DoesNotExist as exc:
        raise GroupServiceError(
            "NOT_FOUND",
            "User not found.",
            404,
        ) from exc


def _require_group_permission(
    group,
    user,
    permission,
    message,
):
    if not has_group_permission(
        group,
        user,
        permission,
    ):
        raise GroupServiceError(
            "FORBIDDEN",
            message,
            403,
        )


@transaction.atomic
def create_group(creator, data):
    group = Group.objects.create(
        name=data["name"].strip(),
        description=data.get("description", "").strip(),
        is_private=data.get("is_private", True),
        creator=creator,
    )

    GroupMembership.objects.create(
        group=group,
        user=creator,
        role=GroupMembership.Role.OWNER,
    )

    member_ids = data.get("member_ids") or []
    for uid_or_username in member_ids:
        if not uid_or_username:
            continue
        add_group_member(
            group.public_id,
            creator,
            user_id=uid_or_username if uid_or_username.startswith("usr_") else None,
            username=uid_or_username if not uid_or_username.startswith("usr_") else None,
        )

    return group


def get_group(public_id, requester):
    group = _get_group_or_404(public_id)

    is_member = GroupMembership.objects.filter(
        group=group,
        user=requester,
    ).exists()

    if not is_member and group.is_private:
        raise GroupServiceError(
            "FORBIDDEN",
            "You are not a member of this private group.",
            403,
        )

    return group


@transaction.atomic
def join_group(group_id, user):
    group = _get_group_or_404(group_id)

    if GroupMembership.objects.filter(group=group, user=user).exists():
        return group, False

    if group.is_private:
        raise GroupServiceError(
            "FORBIDDEN",
            "Cannot join a private group without an invitation.",
            403,
        )

    GroupMembership.objects.create(
        group=group,
        user=user,
        role=GroupMembership.Role.MEMBER,
    )
    return group, True


@transaction.atomic
def update_group(group_id, requester, data):
    group = _get_group_or_404(group_id)

    _require_group_permission(
        group,
        requester,
        AccessPermission.MANAGE_GROUP,
        "شما اجازه ویرایش این گروه را ندارید.",
    )

    update_fields = []

    if "name" in data:
        group.name = data["name"].strip()
        update_fields.append("name")

    if "description" in data:
        group.description = data["description"].strip()
        update_fields.append("description")

    update_fields.append("updated_at")

    group.save(
        update_fields=update_fields
    )

    return group


@transaction.atomic
def delete_group(group_id, requester):
    group = _get_group_or_404(group_id)

    is_owner = GroupMembership.objects.filter(
        group=group,
        user=requester,
        role=GroupMembership.Role.OWNER,
    ).exists()

    if not is_owner:
        raise GroupServiceError(
            "FORBIDDEN",
            "فقط مالک گروه اجازه حذف آن را دارد.",
            403,
        )

    group.soft_delete()

    GroupInvitation.objects.filter(
        group=group,
        status=GroupInvitation.Status.PENDING,
    ).update(
        status=GroupInvitation.Status.CANCELED,
        responded_at=timezone.now(),
    )

    return group


def list_user_groups(user):
    return (
        Group.objects.active()
        .filter(memberships__user=user)
        .select_related("creator")
        .prefetch_related("memberships__user")
        .distinct()
    )


def list_group_members(group_id, requester):
    group = _get_group_or_404(group_id)

    is_member = GroupMembership.objects.filter(
        group=group,
        user=requester,
    ).exists()

    if not is_member:
        raise GroupServiceError(
            "FORBIDDEN",
            "شما عضو این گروه نیستید.",
            403,
        )

    return (
        GroupMembership.objects.filter(
            group=group,
        )
        .select_related("user")
        .prefetch_related("custom_roles")
        .order_by("joined_at")
    )


@transaction.atomic
def add_group_member(group_id, requester, user_id=None, username=None):
    group = _get_group_or_404(group_id)

    _require_group_permission(
        group,
        requester,
        AccessPermission.MANAGE_MEMBERS,
        "You do not have permission to add members to this group.",
    )

    if user_id:
        target_user = _get_user_or_404(user_id)
    elif username:
        try:
            target_user = User.objects.get(username__iexact=username, deleted_at__isnull=True)
        except User.DoesNotExist as exc:
            raise GroupServiceError(
                "NOT_FOUND",
                "User not found.",
                404,
            ) from exc
    else:
        raise GroupServiceError(
            "VALIDATION_ERROR",
            "Either user_id or username must be provided.",
            400,
        )

    if GroupMembership.objects.filter(group=group, user=target_user).exists():
        raise GroupServiceError(
            "CONFLICT",
            "User is already a member of this group.",
            409,
        )

    from api.services.privacy import can_add_user_to_group
    if not can_add_user_to_group(target_user, inviter=requester):
        raise GroupServiceError(
            "FORBIDDEN",
            "User's privacy settings do not allow direct addition to groups.",
            403,
        )

    membership = GroupMembership.objects.create(
        group=group,
        user=target_user,
        role=GroupMembership.Role.MEMBER,
    )

    return membership


@transaction.atomic
def remove_group_member(
    group_id,
    requester,
    member_user_id,
):
    group = _get_group_or_404(group_id)

    requester_membership = (
        GroupMembership.objects.select_for_update()
        .filter(
            group=group,
            user=requester,
        )
        .first()
    )

    if requester_membership is None:
        raise GroupServiceError(
            "FORBIDDEN",
            "شما عضو این گروه نیستید.",
            403,
        )

    if not has_group_permission(
        group,
        requester,
        AccessPermission.MANAGE_MEMBERS,
    ):
        raise GroupServiceError(
            "FORBIDDEN",
            "شما اجازه حذف اعضای این گروه را ندارید.",
            403,
        )

    target_user = _get_user_or_404(
        member_user_id
    )

    target_membership = (
        GroupMembership.objects.select_for_update()
        .filter(
            group=group,
            user=target_user,
        )
        .first()
    )

    if target_membership is None:
        raise GroupServiceError(
            "NOT_FOUND",
            "عضو مورد نظر در این گروه یافت نشد.",
            404,
        )

    if (
        target_membership.role
        == GroupMembership.Role.OWNER
    ):
        raise GroupServiceError(
            "FORBIDDEN",
            "مالک گروه را نمی‌توان حذف کرد.",
            403,
        )

    requester_is_owner = (
        requester_membership.role
        == GroupMembership.Role.OWNER
    )

    target_is_admin = (
        target_membership.role
        == GroupMembership.Role.ADMIN
    )

    if target_is_admin and not requester_is_owner:
        raise GroupServiceError(
            "FORBIDDEN",
            "فقط مالک گروه می‌تواند مدیر را حذف کند.",
            403,
        )

    target_membership.delete()


@transaction.atomic
def leave_group(group_id, user):
    group = _get_group_or_404(group_id)

    membership = (
        GroupMembership.objects.select_for_update()
        .filter(
            group=group,
            user=user,
        )
        .first()
    )

    if membership is None:
        raise GroupServiceError(
            "NOT_FOUND",
            "شما عضو این گروه نیستید.",
            404,
        )

    if (
        membership.role
        == GroupMembership.Role.OWNER
    ):
        raise GroupServiceError(
            "CONFLICT",
            "مالک گروه نمی‌تواند گروه را ترک کند.",
            409,
        )

    membership.delete()


def create_group_invitation(group_id, inviter, invitee_id):
    group = _get_group_or_404(group_id)
    _require_group_permission(
        group,
        inviter,
        AccessPermission.MANAGE_INVITATIONS,
        "You do not have permission to manage invitations for this group.",
    )

    invitee = _get_user_or_404(invitee_id)

    from api.services.privacy import can_invite_user_to_group
    if not can_invite_user_to_group(invitee, inviter=inviter):
        raise GroupServiceError(
            "FORBIDDEN",
            "User's privacy settings do not allow group invitations from this user.",
            403,
        )

    if GroupMembership.objects.filter(
        group=group,
        user=invitee,
    ).exists():
        raise GroupServiceError(
            "CONFLICT",
            "User is already a member of this group.",
            409,
        )

    if GroupInvitation.objects.filter(
        group=group,
        invitee=invitee,
        status=GroupInvitation.Status.PENDING,
    ).exists():
        raise GroupServiceError(
            "CONFLICT",
            "An active invitation has already been sent to this user.",
            409,
        )

    try:
        return GroupInvitation.objects.create(
            group=group,
            inviter=inviter,
            invitee=invitee,
        )
    except IntegrityError as exc:
        raise GroupServiceError(
            "CONFLICT",
            "برای این کاربر قبلاً دعوت‌نامه فعال ارسال شده است.",
            409,
        ) from exc


def list_received_invitations(user):
    return (
        GroupInvitation.objects.filter(
            invitee=user,
            status=GroupInvitation.Status.PENDING,
            group__deleted_at__isnull=True,
        )
        .select_related(
            "group",
            "inviter",
            "invitee",
        )
        .order_by("-created_at")
    )


@transaction.atomic
def respond_to_group_invitation(invitation_id, invitee, action):
    try:
        invitation = (
            GroupInvitation.objects.select_for_update()
            .select_related("group")
            .get(
                public_id=invitation_id,
                invitee=invitee,
            )
        )
    except GroupInvitation.DoesNotExist as exc:
        raise GroupServiceError(
            "NOT_FOUND",
            "دعوت‌نامه مورد نظر یافت نشد.",
            404,
        ) from exc

    if invitation.status != GroupInvitation.Status.PENDING:
        raise GroupServiceError(
            "CONFLICT",
            "این دعوت‌نامه قبلاً پاسخ داده شده است.",
            409,
        )

    if invitation.group.deleted_at is not None:
        raise GroupServiceError(
            "NOT_FOUND",
            "گروه مورد نظر دیگر در دسترس نیست.",
            404,
        )

    if action == "accept":
        GroupMembership.objects.get_or_create(
            group=invitation.group,
            user=invitee,
            defaults={
                "role": GroupMembership.Role.MEMBER,
            },
        )
        invitation.status = GroupInvitation.Status.ACCEPTED

    elif action == "reject":
        invitation.status = GroupInvitation.Status.REJECTED

    else:
        raise GroupServiceError(
            "VALIDATION_ERROR",
            "عملیات باید accept یا reject باشد.",
            400,
        )

    invitation.responded_at = timezone.now()
    invitation.save(
        update_fields=[
            "status",
            "responded_at",
        ]
    )

    return invitation