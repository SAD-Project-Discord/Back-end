from django.db import IntegrityError, transaction
from django.utils import timezone

from api.models import Group, GroupInvitation, GroupMembership, User


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
            "گروه مورد نظر یافت نشد.",
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
            "کاربر مورد نظر یافت نشد.",
            404,
        ) from exc


def _require_group_admin(group, user):
    membership = GroupMembership.objects.filter(
        group=group,
        user=user,
    ).first()

    allowed_roles = {
        GroupMembership.Role.OWNER,
        GroupMembership.Role.ADMIN,
    }

    if membership is None or membership.role not in allowed_roles:
        raise GroupServiceError(
            "FORBIDDEN",
            "شما اجازه مدیریت دعوت‌های این گروه را ندارید.",
            403,
        )

    return membership


@transaction.atomic
def create_group(creator, data):
    group = Group.objects.create(
        name=data["name"].strip(),
        description=data.get("description", "").strip(),
        creator=creator,
    )

    GroupMembership.objects.create(
        group=group,
        user=creator,
        role=GroupMembership.Role.OWNER,
    )

    return group


def get_group(public_id, requester):
    group = _get_group_or_404(public_id)

    if not GroupMembership.objects.filter(
        group=group,
        user=requester,
    ).exists():
        raise GroupServiceError(
            "FORBIDDEN",
            "شما عضو این گروه نیستید.",
            403,
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


def create_group_invitation(group_id, inviter, invitee_id):
    group = _get_group_or_404(group_id)
    _require_group_admin(group, inviter)

    invitee = _get_user_or_404(invitee_id)

    if GroupMembership.objects.filter(
        group=group,
        user=invitee,
    ).exists():
        raise GroupServiceError(
            "CONFLICT",
            "این کاربر در حال حاضر عضو گروه است.",
            409,
        )

    if GroupInvitation.objects.filter(
        group=group,
        invitee=invitee,
        status=GroupInvitation.Status.PENDING,
    ).exists():
        raise GroupServiceError(
            "CONFLICT",
            "برای این کاربر قبلاً دعوت‌نامه فعال ارسال شده است.",
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