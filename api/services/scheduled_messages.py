from django.utils import timezone

from api.models import Message, ScheduledMessage
from api.services.messages import (
    MessageServiceError,
    _determine_message_type,
    _get_user_or_404,
    _resolve_reply,
    create_message,
)


def create_scheduled_message(sender, data):
    scheduled_at = data.get("scheduled_at")
    if not scheduled_at or scheduled_at <= timezone.now():
        raise MessageServiceError("VALIDATION_ERROR", "زمان ارسال پیام باید در آینده باشد.", 400)

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

    scheduled_msg = ScheduledMessage.objects.create(
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
        scheduled_at=scheduled_at,
        status=ScheduledMessage.Status.PENDING,
    )
    return scheduled_msg


def list_scheduled_messages(user):
    return ScheduledMessage.objects.filter(
        user=user,
        status=ScheduledMessage.Status.PENDING,
    ).order_by("scheduled_at")


def cancel_scheduled_message(user, scheduled_message_id):
    try:
        scheduled_msg = ScheduledMessage.objects.get(
            public_id=scheduled_message_id,
            user=user,
            status=ScheduledMessage.Status.PENDING,
        )
    except ScheduledMessage.DoesNotExist as exc:
        raise MessageServiceError("NOT_FOUND", "پیام زمان‌بندی‌شده یافت نشد یا قابل لغو نیست.", 404) from exc

    scheduled_msg.status = ScheduledMessage.Status.CANCELED
    scheduled_msg.save(update_fields=["status", "updated_at"])
    return scheduled_msg


def process_due_scheduled_messages():
    now = timezone.now()
    due_messages = ScheduledMessage.objects.filter(
        status=ScheduledMessage.Status.PENDING,
        scheduled_at__lte=now,
    )
    processed_count = 0
    for sch_msg in due_messages:
        try:
            message_data = {
                "content": sch_msg.content,
                "file_url": sch_msg.file_url,
                "media_ids": [item.get("id") for item in (sch_msg.media or []) if isinstance(item, dict) and "id" in item],
            }
            if sch_msg.receiver:
                message_data["receiver_id"] = sch_msg.receiver.public_id
            if sch_msg.group_id:
                message_data["group_id"] = sch_msg.group_id
            if sch_msg.channel_id:
                message_data["channel_id"] = sch_msg.channel_id
            if sch_msg.topic_id:
                message_data["topic_id"] = sch_msg.topic_id
            if sch_msg.reply_to:
                message_data["reply_to_id"] = sch_msg.reply_to.public_id

            real_msg = create_message(sch_msg.user, message_data)
            sch_msg.sent_message = real_msg
            sch_msg.status = ScheduledMessage.Status.SENT
            sch_msg.save(update_fields=["sent_message", "status", "updated_at"])
            processed_count += 1
        except Exception:
            sch_msg.status = ScheduledMessage.Status.FAILED
            sch_msg.save(update_fields=["status", "updated_at"])

    return processed_count
