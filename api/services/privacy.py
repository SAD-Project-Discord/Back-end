from django.db.models import Q

from api.models import Message, UserPrivacySetting


def get_user_privacy(user):
    privacy, _ = UserPrivacySetting.objects.get_or_create(user=user)
    return privacy


def update_user_privacy(user, data):
    privacy = get_user_privacy(user)
    if "group_add_permission" in data:
        privacy.group_add_permission = data["group_add_permission"]
    if "allow_direct_add" in data:
        privacy.allow_direct_add = data["allow_direct_add"]
    privacy.save()
    return privacy


def are_users_contacts(user1, user2):
    if not user1 or not user2 or user1.id == user2.id:
        return True
    return Message.objects.filter(
        message_type=Message.MessageType.DIRECT,
        deleted_at__isnull=True,
    ).filter(
        (Q(user=user1, receiver=user2) | Q(user=user2, receiver=user1))
    ).exists()


def can_invite_user_to_group(target_user, inviter=None):
    privacy = get_user_privacy(target_user)

    if privacy.group_add_permission == UserPrivacySetting.GroupAddPermission.NOBODY:
        return False

    if privacy.group_add_permission == UserPrivacySetting.GroupAddPermission.CONTACTS:
        if inviter is None:
            return False
        return are_users_contacts(target_user, inviter)

    return True


def can_add_user_to_group(target_user, inviter=None):
    privacy = get_user_privacy(target_user)

    if not privacy.allow_direct_add:
        return False

    return can_invite_user_to_group(target_user, inviter=inviter)
