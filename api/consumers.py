from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

from api.constants import channel_room_name, direct_room_name, group_room_name, user_room_name
from api.services.messages import MessageServiceError, broadcast_typing, create_message


class MessageConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get("user", AnonymousUser())
        self.subscribed_rooms = set()

        if not self.user.is_authenticated:
            await self.close(code=4401)
            return

        self.personal_room = user_room_name(self.user.public_id)
        await self.channel_layer.group_add(self.personal_room, self.channel_name)
        await self.accept()
        await self.send_json(
            {
                "event": "connected",
                "data": {"user_id": self.user.public_id},
            }
        )

    async def disconnect(self, close_code):
        for room in self.subscribed_rooms:
            await self.channel_layer.group_discard(room, self.channel_name)
        if hasattr(self, "personal_room"):
            await self.channel_layer.group_discard(self.personal_room, self.channel_name)

    async def receive_json(self, content, **kwargs):
        action = content.get("action")
        if action == "subscribe":
            await self._handle_subscribe(content)
        elif action == "unsubscribe":
            await self._handle_unsubscribe(content)
        elif action == "send":
            await self._handle_send(content)
        elif action == "typing":
            await self._handle_typing(content)
        else:
            await self._send_error("UNKNOWN_ACTION", "عملیات ناشناخته است.")

    async def chat_event(self, event):
        await self.send_json({"event": event["event"], "data": event["data"]})

    async def _handle_subscribe(self, content):
        room = self._resolve_room(content.get("room", {}))
        if not room:
            await self._send_error("VALIDATION_ERROR", "اتاق نامعتبر است.")
            return

        await self.channel_layer.group_add(room, self.channel_name)
        self.subscribed_rooms.add(room)
        await self.send_json({"event": "subscribed", "data": {"room": room}})

    async def _handle_unsubscribe(self, content):
        room = self._resolve_room(content.get("room", {}))
        if room and room in self.subscribed_rooms:
            await self.channel_layer.group_discard(room, self.channel_name)
            self.subscribed_rooms.discard(room)
            await self.send_json({"event": "unsubscribed", "data": {"room": room}})

    async def _handle_send(self, content):
        room = content.get("room", {})
        payload = {
            "content": content.get("content", ""),
            "reply_to_id": content.get("reply_to_id"),
            "media_ids": content.get("media_ids", []),
            "file_url": content.get("file_url", ""),
        }
        room_type = room.get("type")

        if room_type == "direct":
            payload["receiver_id"] = room.get("target_id")
        elif room_type == "group":
            payload["group_id"] = room.get("target_id")
        elif room_type == "channel":
            payload["channel_id"] = room.get("target_id")
            payload["topic_id"] = room.get("topic_id", "")
        else:
            await self._send_error("VALIDATION_ERROR", "اتاق نامعتبر است.")
            return

        try:
            message = await database_sync_to_async(create_message)(self.user, payload)
        except MessageServiceError as exc:
            await self._send_error(exc.code, exc.message)
            return

        await self.send_json(
            {
                "event": "message.sent",
                "data": {
                    "id": message.public_id,
                    "room": message.get_room_name(),
                },
            }
        )

    async def _handle_typing(self, content):
        room = self._resolve_room(content.get("room", {}))
        if not room:
            await self._send_error("VALIDATION_ERROR", "اتاق نامعتبر است.")
            return

        is_typing = bool(content.get("is_typing", True))
        await database_sync_to_async(broadcast_typing)(self.user, room, is_typing)

    def _resolve_room(self, room):
        room_type = room.get("type")
        target_id = room.get("target_id")
        if not room_type or not target_id:
            return None

        if room_type == "direct":
            return direct_room_name(self.user.public_id, target_id)
        if room_type == "group":
            return group_room_name(target_id)
        if room_type == "channel":
            return channel_room_name(target_id, room.get("topic_id") or None)
        return None

    async def _send_error(self, code, message):
        await self.send_json({"event": "error", "data": {"code": code, "message": message}})
