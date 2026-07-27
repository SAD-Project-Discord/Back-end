from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Channel, ChannelMembership, Group, GroupMembership, Message, User


class PerChatSearchTestCase(APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            email="chatuser1@example.com", username="chatuser1", name="Chat One", password="Password123!"
        )
        self.user2 = User.objects.create_user(
            email="chatuser2@example.com", username="chatuser2", name="Chat Two", password="Password123!"
        )
        self.user3 = User.objects.create_user(
            email="chatuser3@example.com", username="chatuser3", name="Chat Three", password="Password123!"
        )

        # Direct messages
        self.dm1 = Message.objects.create(
            user=self.user1,
            receiver=self.user2,
            message_type=Message.MessageType.DIRECT,
            content="Direct keyword alpha test",
        )
        self.dm2 = Message.objects.create(
            user=self.user1,
            receiver=self.user2,
            message_type=Message.MessageType.DIRECT,
            content="Direct keyword beta test",
        )

        # Group setup
        self.group = Group.objects.create(name="Chat Group", creator=self.user1)
        GroupMembership.objects.create(group=self.group, user=self.user1, role=GroupMembership.Role.OWNER)

        self.grp_msg = Message.objects.create(
            user=self.user1,
            group_id=self.group.public_id,
            message_type=Message.MessageType.GROUP,
            content="Group keyword alpha message",
        )

        # Channel setup
        self.channel = Channel.objects.create(name="Chat Channel", creator=self.user1)
        ChannelMembership.objects.create(channel=self.channel, user=self.user1, role=ChannelMembership.Role.OWNER)

        self.chn_msg = Message.objects.create(
            user=self.user1,
            channel_id=self.channel.public_id,
            message_type=Message.MessageType.CHANNEL,
            content="Channel keyword alpha topic message",
        )

    def test_search_direct_messages_success(self):
        self.client.force_authenticate(user=self.user1)
        url = reverse("messages-direct-search", kwargs={"user_id": self.user2.public_id})
        response = self.client.get(url, {"q": "alpha"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        results = response.data["data"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], self.dm1.public_id)

    def test_search_group_messages_success_and_forbidden_for_non_member(self):
        # User1 is member -> Success
        self.client.force_authenticate(user=self.user1)
        url = reverse("messages-groups-search", kwargs={"group_id": self.group.public_id})
        response = self.client.get(url, {"q": "alpha"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]), 1)

        # User3 is non-member -> Forbidden 403
        self.client.force_authenticate(user=self.user3)
        response_forbidden = self.client.get(url, {"q": "alpha"})
        self.assertEqual(response_forbidden.status_code, status.HTTP_403_FORBIDDEN)

    def test_search_channel_messages_success(self):
        self.client.force_authenticate(user=self.user1)
        url = reverse("messages-channels-search", kwargs={"channel_id": self.channel.public_id})
        response = self.client.get(url, {"q": "topic"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]), 1)
        self.assertEqual(response.data["data"][0]["id"], self.chn_msg.public_id)
