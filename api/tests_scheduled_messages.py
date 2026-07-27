from datetime import timedelta
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Message, ScheduledMessage, User
from api.services.scheduled_messages import process_due_scheduled_messages


class ScheduledMessagesTestCase(APITestCase):
    def setUp(self):
        self.sender = User.objects.create_user(
            email="sender@example.com", username="sender", name="Sender User", password="Password123!"
        )
        self.receiver = User.objects.create_user(
            email="receiver@example.com", username="receiver", name="Receiver User", password="Password123!"
        )
        self.client.force_authenticate(user=self.sender)

    def test_create_scheduled_message_success(self):
        future_time = timezone.now() + timedelta(hours=2)
        url = reverse("scheduled-messages-list-create")
        payload = {
            "receiver_id": self.receiver.public_id,
            "content": "Hello scheduled future message",
            "scheduled_at": future_time.isoformat(),
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])
        data = response.data["data"]
        self.assertEqual(data["content"], "Hello scheduled future message")
        self.assertEqual(data["status"], "pending")

        # Verify DB entry
        sch_msg = ScheduledMessage.objects.get(public_id=data["id"])
        self.assertEqual(sch_msg.status, ScheduledMessage.Status.PENDING)

    def test_create_scheduled_message_in_past_fails(self):
        past_time = timezone.now() - timedelta(minutes=10)
        url = reverse("scheduled-messages-list-create")
        payload = {
            "receiver_id": self.receiver.public_id,
            "content": "Past message",
            "scheduled_at": past_time.isoformat(),
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")

    def test_list_and_cancel_scheduled_messages(self):
        future_time = timezone.now() + timedelta(hours=1)
        sch_msg = ScheduledMessage.objects.create(
            user=self.sender,
            message_type=Message.MessageType.DIRECT,
            receiver=self.receiver,
            content="Message to be canceled",
            scheduled_at=future_time,
        )

        url_list = reverse("scheduled-messages-list-create")
        response_list = self.client.get(url_list)
        self.assertEqual(response_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response_list.data["data"]), 1)

        url_cancel = reverse("scheduled-message-detail", kwargs={"scheduled_id": sch_msg.public_id})
        response_cancel = self.client.delete(url_cancel)
        self.assertEqual(response_cancel.status_code, status.HTTP_204_NO_CONTENT)

        sch_msg.refresh_from_db()
        self.assertEqual(sch_msg.status, ScheduledMessage.Status.CANCELED)

    def test_process_due_scheduled_messages_worker(self):
        # Create a message scheduled 1 minute ago (due)
        past_time = timezone.now() - timedelta(minutes=1)

        # Manually create due scheduled message in DB
        sch_msg = ScheduledMessage.objects.create(
            user=self.sender,
            message_type=Message.MessageType.DIRECT,
            receiver=self.receiver,
            content="Automated scheduled message content",
            scheduled_at=past_time,
            status=ScheduledMessage.Status.PENDING,
        )

        processed = process_due_scheduled_messages()
        self.assertEqual(processed, 1)

        sch_msg.refresh_from_db()
        self.assertEqual(sch_msg.status, ScheduledMessage.Status.SENT)
        self.assertIsNotNone(sch_msg.sent_message)
        self.assertEqual(sch_msg.sent_message.content, "Automated scheduled message content")
