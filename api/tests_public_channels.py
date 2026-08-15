from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model

from api.models import Channel, ChannelMembership

User = get_user_model()


class PublicChannelDiscoveryTestCase(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="chan_owner",
            email="chan_owner@example.com",
            password="password123",
            name="Chan Owner",
        )
        self.user = User.objects.create_user(
            username="chan_user",
            email="chan_user@example.com",
            password="password123",
            name="Chan User",
        )

        self.public_channel1 = Channel.objects.create(
            name="General Discussion",
            description="Public discussion channel",
            is_private=False,
            creator=self.owner,
        )
        ChannelMembership.objects.create(channel=self.public_channel1, user=self.owner, role=ChannelMembership.Role.OWNER)

        self.public_channel2 = Channel.objects.create(
            name="Tech Talk",
            description="Everything about tech",
            is_private=False,
            creator=self.owner,
        )
        ChannelMembership.objects.create(channel=self.public_channel2, user=self.owner, role=ChannelMembership.Role.OWNER)

        self.private_channel = Channel.objects.create(
            name="Secret VIP",
            description="Private channel",
            is_private=True,
            creator=self.owner,
        )
        ChannelMembership.objects.create(channel=self.private_channel, user=self.owner, role=ChannelMembership.Role.OWNER)

    def test_list_public_channels_and_search(self):
        self.client.force_authenticate(user=self.user)

        # List all public channels
        res = self.client.get("/api/v1/channels/public/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["data"]), 2)

        # Search by query
        res_search = self.client.get("/api/v1/channels/public/?q=Tech")
        self.assertEqual(res_search.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_search.data["data"]), 1)
        self.assertEqual(res_search.data["data"][0]["id"], self.public_channel2.public_id)

    def test_list_public_channels_excludes_joined(self):
        # Join public_channel1
        ChannelMembership.objects.create(channel=self.public_channel1, user=self.user, role=ChannelMembership.Role.MEMBER)
        self.client.force_authenticate(user=self.user)

        res = self.client.get("/api/v1/channels/public/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["data"]), 1)
        self.assertEqual(res.data["data"][0]["id"], self.public_channel2.public_id)

    def test_join_public_channel_success(self):
        self.client.force_authenticate(user=self.user)
        url = f"/api/v1/channels/{self.public_channel1.public_id}/join"
        res = self.client.post(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["data"]["id"], self.public_channel1.public_id)

        self.assertTrue(ChannelMembership.objects.filter(channel=self.public_channel1, user=self.user).exists())

    def test_join_private_channel_fails(self):
        self.client.force_authenticate(user=self.user)
        url = f"/api/v1/channels/{self.private_channel.public_id}/join"
        res = self.client.post(url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(ChannelMembership.objects.filter(channel=self.private_channel, user=self.user).exists())

    def test_join_nonexistent_channel_fails(self):
        self.client.force_authenticate(user=self.user)
        url = "/api/v1/channels/chn_nonexistent999/join"
        res = self.client.post(url)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
