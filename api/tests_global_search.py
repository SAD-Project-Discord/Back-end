from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Channel, ChannelMembership, Group, GroupMembership, Message, User


class GlobalSearchTestCase(APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            email="user1@example.com", username="user1", name="User One", password="Password123!"
        )
        self.user2 = User.objects.create_user(
            email="user2@example.com", username="user2", name="User Two", password="Password123!"
        )
        self.user3 = User.objects.create_user(
            email="user3@example.com", username="user3", name="User Three", password="Password123!"
        )

        # Setup group for user1 & user2
        self.group = Group.objects.create(name="Shared Group", creator=self.user1)
        GroupMembership.objects.create(group=self.group, user=self.user1, role=GroupMembership.Role.OWNER)
        GroupMembership.objects.create(group=self.group, user=self.user2, role=GroupMembership.Role.MEMBER)

        # Setup private group for user3 only
        self.private_group = Group.objects.create(name="Private Group", creator=self.user3)
        GroupMembership.objects.create(group=self.private_group, user=self.user3, role=GroupMembership.Role.OWNER)

        # Setup channel for user1
        self.channel = Channel.objects.create(name="Public Channel", creator=self.user1)
        ChannelMembership.objects.create(channel=self.channel, user=self.user1, role=ChannelMembership.Role.OWNER)

        # Create Direct Message between user1 and user2
        self.dm1 = Message.objects.create(
            user=self.user1,
            receiver=self.user2,
            message_type=Message.MessageType.DIRECT,
            content="Hello secret keyword from user1 to user2",
        )

        # Create Direct Message between user2 and user3
        self.dm2 = Message.objects.create(
            user=self.user2,
            receiver=self.user3,
            message_type=Message.MessageType.DIRECT,
            content="Hello secret keyword between user2 and user3",
        )

        # Create Group Message in shared group
        self.grp_msg = Message.objects.create(
            user=self.user2,
            group_id=self.group.public_id,
            message_type=Message.MessageType.GROUP,
            content="Group secret keyword message",
        )

        # Create Group Message in private group
        self.priv_grp_msg = Message.objects.create(
            user=self.user3,
            group_id=self.private_group.public_id,
            message_type=Message.MessageType.GROUP,
            content="Private group secret keyword message",
        )

        # Create Channel Message
        self.chn_msg = Message.objects.create(
            user=self.user1,
            channel_id=self.channel.public_id,
            message_type=Message.MessageType.CHANNEL,
            content="Channel secret keyword message",
        )

    def test_global_search_success_for_authorized_user(self):
        self.client.force_authenticate(user=self.user1)
        url = reverse("messages-global-search")
        response = self.client.get(url, {"q": "secret"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        results = response.data["data"]
        returned_ids = [msg["id"] for msg in results]

        self.assertIn(self.dm1.public_id, returned_ids)
        self.assertIn(self.grp_msg.public_id, returned_ids)
        self.assertIn(self.chn_msg.public_id, returned_ids)

        # User1 should NOT see user3's private group or DM between user2 and user3
        self.assertNotIn(self.dm2.public_id, returned_ids)
        self.assertNotIn(self.priv_grp_msg.public_id, returned_ids)

    def test_global_search_filter_by_message_type(self):
        self.client.force_authenticate(user=self.user1)
        url = reverse("messages-global-search")
        response = self.client.get(url, {"q": "secret", "message_type": "group"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["data"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], self.grp_msg.public_id)

    def test_global_search_filter_by_from_user(self):
        self.client.force_authenticate(user=self.user1)
        url = reverse("messages-global-search")
        response = self.client.get(url, {"q": "secret", "from_user": self.user2.public_id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["data"]
        returned_ids = [msg["id"] for msg in results]
        self.assertIn(self.grp_msg.public_id, returned_ids)
        self.assertNotIn(self.dm1.public_id, returned_ids)

    def test_global_search_empty_query_fails(self):
        self.client.force_authenticate(user=self.user1)
        url = reverse("messages-global-search")
        response = self.client.get(url, {"q": ""})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
