from api.models import UserContact, UserPrivacySetting


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


def is_saved_contact(owner, target_user):
    if not owner or not target_user:
        return False
    if owner.id == target_user.id:
        return True
    return UserContact.objects.filter(owner=owner, contact=target_user).exists()


def are_users_contacts(user1, user2):
    if not user1 or not user2 or user1.id == user2.id:
        return True
    return UserContact.objects.filter(owner=user1, contact=user2).exists() or UserContact.objects.filter(owner=user2, contact=user1).exists()


def can_invite_user_to_group(target_user, inviter=None):
    privacy = get_user_privacy(target_user)

    if privacy.group_add_permission == UserPrivacySetting.GroupAddPermission.NOBODY:
        return False

    if privacy.group_add_permission == UserPrivacySetting.GroupAddPermission.CONTACTS:
        if inviter is None:
            return False
        return UserContact.objects.filter(owner=target_user, contact=inviter).exists()

    return True


def can_add_user_to_group(target_user, inviter=None):
    privacy = get_user_privacy(target_user)

    if not privacy.allow_direct_add:
        return False

    return can_invite_user_to_group(target_user, inviter=inviter)
