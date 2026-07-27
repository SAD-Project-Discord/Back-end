from django.db import models
from django.utils.dateparse import parse_datetime

from api.constants import user_room_name
from api.models import ChannelMembership, GroupMembership, Message, User
from api.serializers import message_to_dict
from api.tasks import broadcast_message_event_task


class MessageServiceError(Exception):
    def __init__(self, code, message, status_code=400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _get_user_or_404(public_id):
    try:
        return User.objects.get(public_id=public_id, deleted_at__isnull=True)
    except User.DoesNotExist as exc:
        raise MessageServiceError("NOT_FOUND", "منبع مورد نظر یافت نشد.", 404) from exc


def _get_message_or_404(public_id):
    try:
        return Message.objects.active().get(public_id=public_id)
    except Message.DoesNotExist as exc:
        raise MessageServiceError("NOT_FOUND", "منبع مورد نظر یافت نشد.", 404) from exc


def _resolve_reply(reply_to_id):
    if not reply_to_id:
        return None
    return _get_message_or_404(reply_to_id)


def _determine_message_type(data):
    if data.get("receiver_id"):
        return Message.MessageType.DIRECT
    if data.get("group_id"):
        return Message.MessageType.GROUP
    if data.get("channel_id"):
        return Message.MessageType.CHANNEL
    raise MessageServiceError(
        "VALIDATION_ERROR",
        "یکی از receiver_id، group_id یا channel_id الزامی است.",
        400,
    )


def create_message(sender, data):
    message_type = _determine_message_type(data)
    content = (data.get("content") or "").strip()
    if not content and not data.get("media_ids"):
        raise MessageServiceError("VALIDATION_ERROR", "متن پیام نمی‌تواند خالی باشد.", 400)

    reply_to = _resolve_reply(data.get("reply_to_id"))
    receiver = None
    group_id = ""
    channel_id = ""
    topic_id = data.get("topic_id") or ""

    if message_type == Message.MessageType.DIRECT:
        receiver = _get_user_or_404(data["receiver_id"])
        if receiver.public_id == sender.public_id:
            raise MessageServiceError("VALIDATION_ERROR", "ارسال پیام به خودتان مجاز نیست.", 400)
    elif message_type == Message.MessageType.GROUP:
        group_id = data["group_id"]
    else:
        channel_id = data["channel_id"]

    media = [{"id": media_id} for media_id in data.get("media_ids", [])]

    message = Message.objects.create(
        user=sender,
        message_type=message_type,
        receiver=receiver,
        group_id=group_id,
        channel_id=channel_id,
        topic_id=topic_id,
        reply_to=reply_to,
        content=content,
        file_url=data.get("file_url", ""),
        media=media,
    )

    payload = message_to_dict(message)
    rooms = {message.get_room_name(), user_room_name(sender.public_id)}
    if receiver:
        rooms.add(user_room_name(receiver.public_id))

    for room in rooms:
        broadcast_message_event_task.delay("message.new", room, payload)

    return message


def list_direct_messages(current_user, other_user_id, limit=50, before=None):
    other_user = _get_user_or_404(other_user_id)
    queryset = Message.objects.for_direct(current_user, other_user)
    return _paginate_messages(queryset, limit, before)


def list_group_messages(group_id, limit=50, before=None):
    queryset = Message.objects.for_group(group_id)
    return _paginate_messages(queryset, limit, before)


def list_channel_messages(channel_id, topic_id=None, limit=50, before=None):
    queryset = Message.objects.for_channel(channel_id, topic_id)
    return _paginate_messages(queryset, limit, before)


def get_message(public_id, requester=None):
    message = _get_message_or_404(public_id)

    if (
        requester is not None
        and message.message_type == Message.MessageType.DIRECT
        and requester.id not in {
            message.user_id,
            message.receiver_id,
        }
    ):
        raise MessageServiceError(
            "FORBIDDEN",
            "شما اجازه مشاهده این پیام خصوصی را ندارید.",
            403,
        )

    return message


def update_message(message, editor, content):
    if message.user_id != editor.id:
        raise MessageServiceError(
            "FORBIDDEN",
            "شما اجازه ویرایش این پیام را ندارید.",
            403,
        )

    normalized_content = content.strip()

    if not normalized_content:
        raise MessageServiceError(
            "VALIDATION_ERROR",
            "متن پیام نمی‌تواند خالی باشد.",
            400,
        )

    message.content = normalized_content
    message.is_edited = True
    message.save(
        update_fields=[
            "content",
            "is_edited",
            "updated_at",
        ]
    )

    payload = message_to_dict(message)

    broadcast_message_event_task.delay(
        "message.updated",
        message.get_room_name(),
        payload,
    )

    return message


def delete_message(message, requester):
    if message.user_id != requester.id:
        raise MessageServiceError("FORBIDDEN", "شما اجازه حذف این پیام را ندارید.", 403)

    message.soft_delete()
    payload = {"id": message.public_id, "room": message.get_room_name()}
    broadcast_message_event_task.delay("message.deleted", message.get_room_name(), payload)
    return message


def search_messages(current_user, query, limit=20):
    queryset = Message.objects.active().filter(content__icontains=query)
    queryset = queryset.filter(
        models.Q(user=current_user)
        | models.Q(receiver=current_user)
        | models.Q(message_type=Message.MessageType.GROUP)
        | models.Q(message_type=Message.MessageType.CHANNEL)
    )
    messages, has_more = _paginate_messages(queryset, limit)
    return messages, has_more, {"page": 1, "limit": limit, "total": len(messages), "total_pages": 1}


def global_search_messages(
    current_user,
    query,
    message_type=None,
    from_user_id=None,
    date_from=None,
    date_to=None,
    limit=20,
    before=None,
):
    if not query or not query.strip():
        raise MessageServiceError("VALIDATION_ERROR", "عبارت جستجو نمی‌تواند خالی باشد.", 400)

    query = query.strip()
    queryset = Message.objects.active().filter(content__icontains=query)

    user_group_ids = list(
        GroupMembership.objects.filter(
            user=current_user,
            group__deleted_at__isnull=True,
        ).values_list("group__public_id", flat=True)
    )

    user_channel_ids = list(
        ChannelMembership.objects.filter(
            user=current_user,
            channel__deleted_at__isnull=True,
        ).values_list("channel__public_id", flat=True)
    )

    access_condition = (
        (
            models.Q(message_type=Message.MessageType.DIRECT)
            & (models.Q(user=current_user) | models.Q(receiver=current_user))
        )
        | (
            models.Q(message_type=Message.MessageType.GROUP)
            & models.Q(group_id__in=user_group_ids)
        )
        | (
            models.Q(message_type=Message.MessageType.CHANNEL)
            & models.Q(channel_id__in=user_channel_ids)
        )
    )
    queryset = queryset.filter(access_condition)

    if message_type:
        if message_type not in Message.MessageType.values:
            raise MessageServiceError("VALIDATION_ERROR", "نوع پیام نامعتبر است.", 400)
        queryset = queryset.filter(message_type=message_type)

    if from_user_id:
        try:
            sender = User.objects.get(public_id=from_user_id, deleted_at__isnull=True)
            queryset = queryset.filter(user=sender)
        except User.DoesNotExist:
            queryset = queryset.none()

    if date_from:
        dt_from = parse_datetime(date_from)
        if dt_from:
            queryset = queryset.filter(created_at__gte=dt_from)

    if date_to:
        dt_to = parse_datetime(date_to)
        if dt_to:
            queryset = queryset.filter(created_at__lte=dt_to)

    messages_list, has_more = _paginate_messages(queryset, limit, before)
    meta = {
        "limit": int(limit),
        "has_more": has_more,
        "total": len(messages_list),
        "query": query,
    }
    return messages_list, has_more, meta


def _paginate_messages(queryset, limit, before=None):
    limit = min(max(int(limit), 1), 100)
    queryset = queryset.order_by("-created_at")
    if before:
        try:
            pivot = Message.objects.get(public_id=before)
            queryset = queryset.filter(created_at__lt=pivot.created_at)
        except Message.DoesNotExist:
            pass

    items = list(queryset[: limit + 1])
    has_more = len(items) > limit
    if has_more:
        items = items[:limit]
    items.reverse()
    return items, has_more


def broadcast_typing(user, room_name, is_typing):
    broadcast_message_event_task.delay(
        "typing",
        room_name,
        {"user_id": user.public_id, "is_typing": is_typing, "room": room_name},
    )


def search_direct_messages(current_user, other_user_id, query, limit=20, before=None):
    if not query or not query.strip():
        raise MessageServiceError("VALIDATION_ERROR", "عبارت جستجو نمی‌تواند خالی باشد.", 400)
    other_user = _get_user_or_404(other_user_id)
    queryset = Message.objects.for_direct(current_user, other_user).filter(content__icontains=query.strip())
    messages_list, has_more = _paginate_messages(queryset, limit, before)
    return messages_list, has_more


def search_group_messages(current_user, group_id, query, limit=20, before=None):
    if not query or not query.strip():
        raise MessageServiceError("VALIDATION_ERROR", "عبارت جستجو نمی‌تواند خالی باشد.", 400)

    if not GroupMembership.objects.filter(group__public_id=group_id, group__deleted_at__isnull=True, user=current_user).exists():
        raise MessageServiceError("FORBIDDEN", "شما عضو این گروه نیستید.", 403)

    queryset = Message.objects.for_group(group_id).filter(content__icontains=query.strip())
    messages_list, has_more = _paginate_messages(queryset, limit, before)
    return messages_list, has_more


def search_channel_messages(current_user, channel_id, topic_id=None, query=None, limit=20, before=None):
    if not query or not query.strip():
        raise MessageServiceError("VALIDATION_ERROR", "عبارت جستجو نمی‌تواند خالی باشد.", 400)

    if not ChannelMembership.objects.filter(channel__public_id=channel_id, channel__deleted_at__isnull=True, user=current_user).exists():
        raise MessageServiceError("FORBIDDEN", "شما عضو این کانال نیستید.", 403)

    queryset = Message.objects.for_channel(channel_id, topic_id).filter(content__icontains=query.strip())
    messages_list, has_more = _paginate_messages(queryset, limit, before)
    return messages_list, has_more
