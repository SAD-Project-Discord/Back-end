from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


@shared_task(name="api.broadcast_message_event")
def broadcast_message_event_task(event_type, room, payload):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    try:
        async_to_sync(channel_layer.group_send)(
            room,
            {
                "type": "chat.event",
                "event": event_type,
                "data": payload,
            },
        )
    except Exception:
        pass


@shared_task(name="api.process_scheduled_messages")
def process_scheduled_messages_task():
    from api.services.scheduled_messages import process_due_scheduled_messages
    return process_due_scheduled_messages()
