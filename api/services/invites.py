from django.utils import timezone

from api.models import (
    AccessPermission,
    Channel,
    ChannelMembership,
    Group,
    GroupMembership,
    InviteLink,
)
from api.services.access_control import (
    has_channel_permission,
    has_group_permission,
)


class InviteServiceError(Exception):
    def __init__(self, code, message, status_code=400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def get_or_create_group_invite_link(group_id, requester):
    try:
        group = Group.objects.active().get(public_id=group_id)
    except Group.DoesNotExist as exc:
        raise InviteServiceError("NOT_FOUND", "Group not found.", 404) from exc

    if not has_group_permission(group, requester, AccessPermission.MANAGE_MEMBERS):
        raise InviteServiceError("FORBIDDEN", "You do not have permission to manage invites for this group.", 403)

    link = InviteLink.objects.filter(
        target_type=InviteLink.TargetType.GROUP,
        group=group,
        is_active=True,
    ).first()

    if not link:
        link = InviteLink.objects.create(
            target_type=InviteLink.TargetType.GROUP,
            group=group,
            creator=requester,
        )

    return link


def revoke_group_invite_link(group_id, requester):
    try:
        group = Group.objects.active().get(public_id=group_id)
    except Group.DoesNotExist as exc:
        raise InviteServiceError("NOT_FOUND", "Group not found.", 404) from exc

    if not has_group_permission(group, requester, AccessPermission.MANAGE_MEMBERS):
        raise InviteServiceError("FORBIDDEN", "You do not have permission to manage invites for this group.", 403)

    InviteLink.objects.filter(
        target_type=InviteLink.TargetType.GROUP,
        group=group,
        is_active=True,
    ).update(is_active=False)


def get_or_create_channel_invite_link(channel_id, requester):
    try:
        channel = Channel.objects.active().get(public_id=channel_id)
    except Channel.DoesNotExist as exc:
        raise InviteServiceError("NOT_FOUND", "Channel not found.", 404) from exc

    if not has_channel_permission(channel, requester, AccessPermission.MANAGE_CHANNEL_MEMBERS):
        raise InviteServiceError("FORBIDDEN", "You do not have permission to manage invites for this channel.", 403)

    link = InviteLink.objects.filter(
        target_type=InviteLink.TargetType.CHANNEL,
        channel=channel,
        is_active=True,
    ).first()

    if not link:
        link = InviteLink.objects.create(
            target_type=InviteLink.TargetType.CHANNEL,
            channel=channel,
            creator=requester,
        )

    return link


def revoke_channel_invite_link(channel_id, requester):
    try:
        channel = Channel.objects.active().get(public_id=channel_id)
    except Channel.DoesNotExist as exc:
        raise InviteServiceError("NOT_FOUND", "Channel not found.", 404) from exc

    if not has_channel_permission(channel, requester, AccessPermission.MANAGE_CHANNEL_MEMBERS):
        raise InviteServiceError("FORBIDDEN", "You do not have permission to manage invites for this channel.", 403)

    InviteLink.objects.filter(
        target_type=InviteLink.TargetType.CHANNEL,
        channel=channel,
        is_active=True,
    ).update(is_active=False)


def _get_active_invite_link(token):
    try:
        link = InviteLink.objects.select_related("group", "channel").get(public_id=token, is_active=True)
    except InviteLink.DoesNotExist as exc:
        raise InviteServiceError("INVITE_NOT_FOUND", "This invite link is invalid or has expired.", 404) from exc

    if link.expires_at and link.expires_at < timezone.now():
        link.is_active = False
        link.save(update_fields=["is_active"])
        raise InviteServiceError("INVITE_NOT_FOUND", "This invite link is invalid or has expired.", 404)

    target = link.group or link.channel
    if not target or getattr(target, "deleted_at", None) is not None:
        raise InviteServiceError("INVITE_NOT_FOUND", "This invite link is invalid or has expired.", 404)

    return link


def preview_invite_link(token, requester):
    link = _get_active_invite_link(token)
    target = link.group or link.channel

    is_member = False
    if requester and requester.is_authenticated:
        if link.target_type == InviteLink.TargetType.GROUP:
            is_member = GroupMembership.objects.filter(group=link.group, user=requester).exists()
        else:
            is_member = ChannelMembership.objects.filter(channel=link.channel, user=requester).exists()

    return {
        "token": link.public_id,
        "target_type": link.target_type,
        "target_id": target.public_id,
        "target_name": target.name,
        "target_description": target.description or "",
        "member_count": target.memberships.count(),
        "is_member": is_member,
    }


def join_by_invite_link(token, requester):
    if not requester or not requester.is_authenticated:
        raise InviteServiceError("UNAUTHORIZED", "Authentication required to join.", 401)

    link = _get_active_invite_link(token)

    if link.target_type == InviteLink.TargetType.GROUP:
        if not GroupMembership.objects.filter(group=link.group, user=requester).exists():
            GroupMembership.objects.create(
                group=link.group,
                user=requester,
                role=GroupMembership.Role.MEMBER,
            )
    elif link.target_type == InviteLink.TargetType.CHANNEL:
        if not ChannelMembership.objects.filter(channel=link.channel, user=requester).exists():
            ChannelMembership.objects.create(
                channel=link.channel,
                user=requester,
                role=ChannelMembership.Role.MEMBER,
            )

    return preview_invite_link(token, requester)
