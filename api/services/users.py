from django.db.models import Q

from api.models import Message, User


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


def list_user_contacts(user, query=None, limit=50):
    query = (query or "").strip()
    try:
        limit = min(max(int(limit), 1), 100)
    except (ValueError, TypeError):
        limit = 50

    sent_receiver_ids = Message.objects.filter(
        user=user,
        message_type=Message.MessageType.DIRECT,
        deleted_at__isnull=True,
    ).values_list("receiver_id", flat=True)

    received_sender_ids = Message.objects.filter(
        receiver=user,
        message_type=Message.MessageType.DIRECT,
        deleted_at__isnull=True,
    ).values_list("user_id", flat=True)

    contact_user_ids = set(sent_receiver_ids).union(set(received_sender_ids))
    contact_user_ids.discard(user.id)

    contacts_qs = User.objects.filter(
        id__in=contact_user_ids,
        deleted_at__isnull=True,
    )

    if query:
        contacts_qs = contacts_qs.filter(
            Q(username__icontains=query)
            | Q(name__icontains=query)
            | Q(email__icontains=query)
        )

    return list(contacts_qs.order_by("username")[:limit])
