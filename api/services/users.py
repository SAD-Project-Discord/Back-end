import base64
from datetime import datetime
from django.db.models import Q

from api.constants import user_room_name
from api.models import User, UserContact
from api.tasks import broadcast_message_event_task


class UserServiceError(Exception):
    def __init__(self, code, message, status_code=400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _encode_cursor(created_at, cnt_public_id):
    ts = created_at.isoformat()
    raw = f"{ts}|{cnt_public_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor_str):
    try:
        raw = base64.urlsafe_b64decode(cursor_str.encode()).decode()
        ts, cnt_id = raw.split("|", 1)
        dt = datetime.fromisoformat(ts)
        return dt, cnt_id
    except Exception:
        return None, None


def search_users(query, current_user=None, limit=20):
    query = (query or "").strip()
    if not query:
        return []

    try:
        limit = min(max(int(limit), 1), 100)
    except (ValueError, TypeError):
        limit = 20

    qs = User.objects.filter(deleted_at__isnull=True).filter(
        Q(username__icontains=query)
        | Q(name__icontains=query)
        | Q(email__icontains=query)
        | Q(public_id=query)
    )

    return list(qs.order_by("username")[:limit])


def add_contact(owner, target_user_id):
    if not target_user_id:
        raise UserServiceError("VALIDATION_ERROR", "user_id is required.", 400)

    try:
        target_user = User.objects.get(
            Q(public_id=target_user_id) | Q(id=str(target_user_id) if str(target_user_id).isdigit() else -1),
            deleted_at__isnull=True,
        )
    except User.DoesNotExist as exc:
        raise UserServiceError("NOT_FOUND", "User not found.", 404) from exc

    if target_user.pk == owner.pk or target_user.public_id == owner.public_id:
        raise UserServiceError("VALIDATION_ERROR", "You cannot add yourself as a contact.", 400)

    contact_obj, created = UserContact.objects.get_or_create(
        owner=owner,
        contact=target_user,
    )

    target_user.is_contact_override = True

    from api.serializers import PublicUserProfileSerializer
    profile_data = PublicUserProfileSerializer(target_user).data

    broadcast_message_event_task.delay(
        "contact.added",
        user_room_name(owner.public_id),
        {
            "user_id": target_user.public_id,
            "contact": profile_data,
        },
    )

    return target_user


def remove_contact(owner, target_user_id):
    if not target_user_id:
        return True

    contact_qs = UserContact.objects.filter(owner=owner).filter(
        Q(contact__public_id=target_user_id) | Q(contact__id=str(target_user_id) if str(target_user_id).isdigit() else -1)
    ).select_related("contact")

    contact_obj = contact_qs.first()
    if contact_obj:
        removed_public_id = contact_obj.contact.public_id
        contact_obj.delete()

        broadcast_message_event_task.delay(
            "contact.removed",
            user_room_name(owner.public_id),
            {"user_id": removed_public_id},
        )

    return True


def list_user_contacts(owner, query=None, cursor=None, limit=50):
    try:
        limit = min(max(int(limit), 1), 100)
    except (ValueError, TypeError):
        limit = 50

    contacts_qs = UserContact.objects.filter(
        owner=owner,
        contact__deleted_at__isnull=True,
    ).select_related("contact")

    query = (query or "").strip()
    if query:
        contacts_qs = contacts_qs.filter(
            Q(contact__username__icontains=query)
            | Q(contact__name__icontains=query)
            | Q(contact__email__icontains=query)
        )

    if cursor:
        dt, cnt_id = _decode_cursor(cursor)
        if dt and cnt_id:
            contacts_qs = contacts_qs.filter(
                Q(created_at__lt=dt) | Q(created_at=dt, public_id__lt=cnt_id)
            )

    contacts_qs = contacts_qs.order_by("-created_at", "-public_id")
    items = list(contacts_qs[: limit + 1])

    has_more = len(items) > limit
    if has_more:
        next_item = items[limit - 1]
        next_cursor = _encode_cursor(next_item.created_at, next_item.public_id)
        items = items[:limit]
    else:
        next_cursor = None

    users = []
    for item in items:
        user = item.contact
        user.is_contact_override = True
        users.append(user)

    meta = {
        "next_cursor": next_cursor,
        "has_more": has_more,
    }

    return users, meta
