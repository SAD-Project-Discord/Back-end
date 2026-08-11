from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Channel, ChannelMembership, Group, GroupMembership, GroupInvitation, InviteLink

User = get_user_model()


class BackendRequirementsTestCase(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="req_owner",
            email="req_owner@example.com",
            password="password123",
            name="Req Owner",
        )
        self.member = User.objects.create_user(
            username="req_member",
            email="req_member@example.com",
            password="password123",
            name="Req Member",
        )
        self.stranger = User.objects.create_user(
            username="req_stranger",
            email="req_stranger@example.com",
            password="password123",
            name="Req Stranger",
        )

        self.public_group = Group.objects.create(
            name="Public Group",
            description="Everyone welcome",
            is_private=False,
            creator=self.owner,
        )
        GroupMembership.objects.create(group=self.public_group, user=self.owner, role=GroupMembership.Role.OWNER)

        self.private_group = Group.objects.create(
            name="Private Group",
            description="Invite only",
            is_private=True,
            creator=self.owner,
        )
        GroupMembership.objects.create(group=self.private_group, user=self.owner, role=GroupMembership.Role.OWNER)
        GroupMembership.objects.create(group=self.private_group, user=self.member, role=GroupMembership.Role.MEMBER)

        self.channel = Channel.objects.create(
            name="Private Channel",
            description="Secret channel",
            is_private=True,
            creator=self.owner,
        )
        ChannelMembership.objects.create(channel=self.channel, user=self.owner, role=ChannelMembership.Role.OWNER)
        ChannelMembership.objects.create(channel=self.channel, user=self.member, role=ChannelMembership.Role.MEMBER)

    @patch("api.tasks.broadcast_message_event_task.delay")
    def test_group_member_removed_broadcast(self, mock_delay):
        self.client.force_authenticate(user=self.owner)
        url = f"/api/v1/groups/{self.private_group.public_id}/members/{self.member.public_id}"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        mock_delay.assert_called_once_with(
            "group.member_removed",
            f"group_{self.private_group.public_id}",
            {
                "group_id": self.private_group.public_id,
                "user_id": self.member.public_id,
                "removed_by": self.owner.public_id,
            },
        )

    @patch("api.tasks.broadcast_message_event_task.delay")
    def test_channel_member_removed_broadcast(self, mock_delay):
        self.client.force_authenticate(user=self.owner)
        url = f"/api/v1/channels/{self.channel.public_id}/members/{self.member.public_id}"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        mock_delay.assert_called_once_with(
            "channel.member_removed",
            f"channel_{self.channel.public_id}",
            {
                "channel_id": self.channel.public_id,
                "user_id": self.member.public_id,
                "removed_by": self.owner.public_id,
            },
        )

    @patch("api.tasks.broadcast_message_event_task.delay")
    def test_group_invitation_received_broadcast(self, mock_delay):
        self.client.force_authenticate(user=self.owner)
        url = f"/api/v1/groups/{self.private_group.public_id}/invitations"
        response = self.client.post(url, {"invitee_id": self.stranger.public_id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertTrue(mock_delay.called)
        args, _ = mock_delay.call_args
        self.assertEqual(args[0], "group.invitation.received")
        self.assertEqual(args[1], f"user_{self.stranger.public_id}")
        self.assertEqual(args[2]["invitee_id"], self.stranger.public_id)

    def test_list_public_groups(self):
        self.client.force_authenticate(user=self.stranger)
        response = self.client.get("/api/v1/groups/public?q=Public")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]), 1)
        self.assertEqual(response.data["data"][0]["id"], self.public_group.public_id)
        self.assertFalse(response.data["data"][0]["is_private"])

    def test_channel_privacy_and_update(self):
        self.client.force_authenticate(user=self.owner)
        # Create channel with is_private=False
        create_res = self.client.post("/api/v1/channels/", {"name": "Public Channel", "is_private": False}, format="json")
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        pub_chan_id = create_res.data["data"]["id"]
        self.assertFalse(create_res.data["data"]["is_private"])

        # Stranger can access public channel details
        self.client.force_authenticate(user=self.stranger)
        get_res = self.client.get(f"/api/v1/channels/{pub_chan_id}")
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)

        # Stranger cannot access private channel details
        get_priv_res = self.client.get(f"/api/v1/channels/{self.channel.public_id}")
        self.assertEqual(get_priv_res.status_code, status.HTTP_403_FORBIDDEN)

        # Owner can update channel privacy
        self.client.force_authenticate(user=self.owner)
        patch_res = self.client.patch(f"/api/v1/channels/{pub_chan_id}", {"is_private": True}, format="json")
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertTrue(patch_res.data["data"]["is_private"])

    def test_shareable_invite_links_flow(self):
        # Group invite link get-or-create
        self.client.force_authenticate(user=self.owner)
        res_link = self.client.post(f"/api/v1/groups/{self.private_group.public_id}/invite-link")
        self.assertEqual(res_link.status_code, status.HTTP_200_OK)
        token = res_link.data["data"]["token"]
        self.assertTrue(token.startswith("inv_"))

        # Re-calling returns idempotent same link
        res_link2 = self.client.post(f"/api/v1/groups/{self.private_group.public_id}/invite-link")
        self.assertEqual(res_link2.data["data"]["token"], token)

        # Preview invite link as stranger
        self.client.force_authenticate(user=self.stranger)
        res_preview = self.client.get(f"/api/v1/invites/{token}")
        self.assertEqual(res_preview.status_code, status.HTTP_200_OK)
        self.assertEqual(res_preview.data["data"]["target_type"], "group")
        self.assertEqual(res_preview.data["data"]["target_name"], "Private Group")
        self.assertFalse(res_preview.data["data"]["is_member"])

        # Join via invite link
        res_join = self.client.post(f"/api/v1/invites/{token}/join")
        self.assertEqual(res_join.status_code, status.HTTP_200_OK)
        self.assertTrue(res_join.data["data"]["is_member"])
        self.assertTrue(GroupMembership.objects.filter(group=self.private_group, user=self.stranger).exists())

        # Channel invite link flow
        self.client.force_authenticate(user=self.owner)
        res_chan_link = self.client.post(f"/api/v1/channels/{self.channel.public_id}/invite-link")
        self.assertEqual(res_chan_link.status_code, status.HTTP_200_OK)
        chan_token = res_chan_link.data["data"]["token"]

        self.client.force_authenticate(user=self.stranger)
        res_chan_join = self.client.post(f"/api/v1/invites/{chan_token}/join")
        self.assertEqual(res_chan_join.status_code, status.HTTP_200_OK)
        self.assertTrue(ChannelMembership.objects.filter(channel=self.channel, user=self.stranger).exists())
