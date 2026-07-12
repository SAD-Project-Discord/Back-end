from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Message, User


class UserProfileTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="sara@example.com",
            username="sara",
            name="Sara",
            password="StrongPassword123",
        )

        self.other_user = User.objects.create_user(
            email="ali@example.com",
            username="ali",
            name="Ali",
            password="StrongPassword123",
        )

    def test_authenticated_user_can_view_own_profile(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            reverse("users-me")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertTrue(response.data["success"])
        self.assertEqual(
            response.data["data"]["id"],
            self.user.public_id,
        )
        self.assertEqual(
            response.data["data"]["email"],
            self.user.email,
        )

    def test_authenticated_user_can_update_own_profile(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            reverse("users-me"),
            {
                "name": "Sara Ahmadi",
                "bio": "Backend developer",
                "avatar_url": "https://example.com/avatar.jpg",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.user.refresh_from_db()

        self.assertEqual(
            self.user.name,
            "Sara Ahmadi",
        )
        self.assertEqual(
            self.user.bio,
            "Backend developer",
        )
        self.assertEqual(
            self.user.profile_picture,
            "https://example.com/avatar.jpg",
        )

    def test_user_can_view_another_users_public_profile(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            reverse(
                "users-detail",
                kwargs={
                    "user_id": self.other_user.public_id,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.data["data"]["username"],
            self.other_user.username,
        )
        self.assertNotIn(
            "email",
            response.data["data"],
        )

    def test_user_cannot_use_duplicate_username(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            reverse("users-me"),
            {
                "username": self.other_user.username,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            response.data["error"]["code"],
            "VALIDATION_ERROR",
        )

    def test_unknown_user_returns_not_found(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            reverse(
                "users-detail",
                kwargs={
                    "user_id": "usr_does_not_exist",
                },
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_unauthenticated_user_cannot_view_profiles(self):
        response = self.client.get(
            reverse("users-me")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )


class MessageEditDeleteTests(APITestCase):
    def setUp(self):
        self.sender = User.objects.create_user(
            email="sender@example.com",
            username="sender",
            name="Sender",
            password="StrongPassword123",
        )

        self.receiver = User.objects.create_user(
            email="receiver@example.com",
            username="receiver",
            name="Receiver",
            password="StrongPassword123",
        )

        self.other_user = User.objects.create_user(
            email="other@example.com",
            username="other",
            name="Other User",
            password="StrongPassword123",
        )

        self.message = Message.objects.create(
            user=self.sender,
            receiver=self.receiver,
            message_type=Message.MessageType.DIRECT,
            content="Original message",
        )

        self.message_url = reverse(
            "message-detail",
            kwargs={
                "message_id": self.message.public_id,
            },
        )

        self.broadcast_patcher = patch(
            "api.services.messages."
            "broadcast_message_event_task.delay"
        )
        self.mock_broadcast = self.broadcast_patcher.start()
        self.addCleanup(self.broadcast_patcher.stop)

    def test_sender_can_edit_own_message(self):
        self.client.force_authenticate(user=self.sender)

        response = self.client.patch(
            self.message_url,
            {
                "content": "  Edited message  ",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.message.refresh_from_db()

        self.assertEqual(
            self.message.content,
            "Edited message",
        )
        self.assertTrue(self.message.is_edited)

        self.mock_broadcast.assert_called_once()

        event_name = self.mock_broadcast.call_args.args[0]

        self.assertEqual(
            event_name,
            "message.updated",
        )

    def test_non_sender_cannot_edit_message(self):
        self.client.force_authenticate(
            user=self.receiver
        )

        response = self.client.patch(
            self.message_url,
            {
                "content": "Unauthorized edit",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.assertEqual(
            response.data["error"]["code"],
            "FORBIDDEN",
        )

        self.message.refresh_from_db()

        self.assertEqual(
            self.message.content,
            "Original message",
        )
        self.assertFalse(self.message.is_edited)
        self.mock_broadcast.assert_not_called()

    def test_message_cannot_be_edited_to_empty_content(self):
        self.client.force_authenticate(
            user=self.sender
        )

        response = self.client.patch(
            self.message_url,
            {
                "content": "   ",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.message.refresh_from_db()

        self.assertEqual(
            self.message.content,
            "Original message",
        )
        self.assertFalse(self.message.is_edited)
        self.mock_broadcast.assert_not_called()

    def test_sender_can_delete_own_message(self):
        self.client.force_authenticate(
            user=self.sender
        )

        response = self.client.delete(
            self.message_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.message.refresh_from_db()

        self.assertIsNotNone(
            self.message.deleted_at
        )

        self.assertFalse(
            Message.objects.active().filter(
                pk=self.message.pk
            ).exists()
        )

        self.mock_broadcast.assert_called_once()

        event_name = self.mock_broadcast.call_args.args[0]

        self.assertEqual(
            event_name,
            "message.deleted",
        )

    def test_non_sender_cannot_delete_message(self):
        self.client.force_authenticate(
            user=self.other_user
        )

        response = self.client.delete(
            self.message_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.assertEqual(
            response.data["error"]["code"],
            "FORBIDDEN",
        )

        self.message.refresh_from_db()

        self.assertIsNone(
            self.message.deleted_at
        )

        self.assertTrue(
            Message.objects.active().filter(
                pk=self.message.pk
            ).exists()
        )

        self.mock_broadcast.assert_not_called()

    def test_deleted_message_is_not_accessible(self):
        self.message.soft_delete()

        self.client.force_authenticate(
            user=self.sender
        )

        response = self.client.get(
            self.message_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        self.assertEqual(
            response.data["error"]["code"],
            "NOT_FOUND",
        )

    def test_unauthenticated_user_cannot_edit_message(self):
        response = self.client.patch(
            self.message_url,
            {
                "content": "Edited message",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_unauthenticated_user_cannot_delete_message(self):
        response = self.client.delete(
            self.message_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )