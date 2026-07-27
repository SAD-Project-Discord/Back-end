from api.models import UserPrivacySetting


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


def can_add_user_to_group(target_user, inviter=None):
    privacy = get_user_privacy(target_user)
    if (
        privacy.group_add_permission == UserPrivacySetting.GroupAddPermission.NOBODY
        or not privacy.allow_direct_add
    ):
        return False
    return True
