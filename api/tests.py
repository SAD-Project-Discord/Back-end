from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import (
    AccessPermission,
    AccessRole,
    Channel,
    ChannelMembership,
    Group,
    GroupInvitation,
    GroupMembership,
    MediaAttachment,
    Message,
    Topic,
    User,
)


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


class PrivateChatTests(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(
            email="user-a@example.com",
            username="user_a",
            name="User A",
            password="StrongPassword123",
        )

        self.user_b = User.objects.create_user(
            email="user-b@example.com",
            username="user_b",
            name="User B",
            password="StrongPassword123",
        )

        self.user_c = User.objects.create_user(
            email="user-c@example.com",
            username="user_c",
            name="User C",
            password="StrongPassword123",
        )

        self.broadcast_patcher = patch(
            "api.services.messages."
            "broadcast_message_event_task.delay"
        )
        self.mock_broadcast = self.broadcast_patcher.start()
        self.addCleanup(self.broadcast_patcher.stop)

    def test_user_can_send_direct_message(self):
        self.client.force_authenticate(user=self.user_a)

        response = self.client.post(
            reverse("messages"),
            {
                "receiver_id": self.user_b.public_id,
                "content": "Hello User B",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        message = Message.objects.get(
            public_id=response.data["data"]["id"]
        )

        self.assertEqual(
            message.message_type,
            Message.MessageType.DIRECT,
        )
        self.assertEqual(message.user, self.user_a)
        self.assertEqual(message.receiver, self.user_b)
        self.assertEqual(message.content, "Hello User B")

    def test_direct_history_contains_both_directions(self):
        message_a = Message.objects.create(
            user=self.user_a,
            receiver=self.user_b,
            message_type=Message.MessageType.DIRECT,
            content="Message from A",
        )

        message_b = Message.objects.create(
            user=self.user_b,
            receiver=self.user_a,
            message_type=Message.MessageType.DIRECT,
            content="Message from B",
        )

        unrelated_message = Message.objects.create(
            user=self.user_a,
            receiver=self.user_c,
            message_type=Message.MessageType.DIRECT,
            content="Message for C",
        )

        self.client.force_authenticate(user=self.user_a)

        response = self.client.get(
            reverse(
                "messages-direct",
                kwargs={
                    "user_id": self.user_b.public_id,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        message_ids = {
            item["id"]
            for item in response.data["data"]
        }

        self.assertIn(
            message_a.public_id,
            message_ids,
        )
        self.assertIn(
            message_b.public_id,
            message_ids,
        )
        self.assertNotIn(
            unrelated_message.public_id,
            message_ids,
        )

    def test_sender_can_view_direct_message_detail(self):
        message = Message.objects.create(
            user=self.user_a,
            receiver=self.user_b,
            message_type=Message.MessageType.DIRECT,
            content="Private message",
        )

        self.client.force_authenticate(user=self.user_a)

        response = self.client.get(
            reverse(
                "message-detail",
                kwargs={
                    "message_id": message.public_id,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_receiver_can_view_direct_message_detail(self):
        message = Message.objects.create(
            user=self.user_a,
            receiver=self.user_b,
            message_type=Message.MessageType.DIRECT,
            content="Private message",
        )

        self.client.force_authenticate(user=self.user_b)

        response = self.client.get(
            reverse(
                "message-detail",
                kwargs={
                    "message_id": message.public_id,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_third_user_cannot_view_direct_message_detail(self):
        message = Message.objects.create(
            user=self.user_a,
            receiver=self.user_b,
            message_type=Message.MessageType.DIRECT,
            content="Private message",
        )

        self.client.force_authenticate(user=self.user_c)

        response = self.client.get(
            reverse(
                "message-detail",
                kwargs={
                    "message_id": message.public_id,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.assertEqual(
            response.data["error"]["code"],
            "FORBIDDEN",
        )

    def test_user_cannot_send_direct_message_to_self(self):
        self.client.force_authenticate(user=self.user_a)

        response = self.client.post(
            reverse("messages"),
            {
                "receiver_id": self.user_a.public_id,
                "content": "Message to myself",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            Message.objects.filter(
                message_type=Message.MessageType.DIRECT,
                user=self.user_a,
                receiver=self.user_a,
            ).count(),
            0,
        )

    def test_deleted_message_is_not_in_direct_history(self):
        deleted_message = Message.objects.create(
            user=self.user_a,
            receiver=self.user_b,
            message_type=Message.MessageType.DIRECT,
            content="Deleted message",
        )
        deleted_message.soft_delete()

        active_message = Message.objects.create(
            user=self.user_b,
            receiver=self.user_a,
            message_type=Message.MessageType.DIRECT,
            content="Active message",
        )

        self.client.force_authenticate(user=self.user_a)

        response = self.client.get(
            reverse(
                "messages-direct",
                kwargs={
                    "user_id": self.user_b.public_id,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        message_ids = {
            item["id"]
            for item in response.data["data"]
        }

        self.assertNotIn(
            deleted_message.public_id,
            message_ids,
        )
        self.assertIn(
            active_message.public_id,
            message_ids,
        )

    def test_unauthenticated_user_cannot_view_direct_history(self):
        response = self.client.get(
            reverse(
                "messages-direct",
                kwargs={
                    "user_id": self.user_b.public_id,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )


class GroupCreationInvitationTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com",
            username="group_owner",
            name="Group Owner",
            password="StrongPassword123",
        )

        self.invitee = User.objects.create_user(
            email="invitee@example.com",
            username="group_invitee",
            name="Group Invitee",
            password="StrongPassword123",
        )

        self.other_user = User.objects.create_user(
            email="other-group@example.com",
            username="group_other",
            name="Other User",
            password="StrongPassword123",
        )

    def create_group(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            reverse("groups"),
            {
                "name": "Backend Team",
                "description": "Project backend group",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        return Group.objects.get(
            public_id=response.data["data"]["id"]
        )

    def create_invitation(self, group):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            reverse(
                "group-invitation-create",
                kwargs={
                    "group_id": group.public_id,
                },
            ),
            {
                "invitee_id": self.invitee.public_id,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        return GroupInvitation.objects.get(
            public_id=response.data["data"]["id"]
        )

    def test_authenticated_user_can_create_group(self):
        group = self.create_group()

        self.assertEqual(
            group.name,
            "Backend Team",
        )
        self.assertEqual(
            group.creator,
            self.owner,
        )

        membership = GroupMembership.objects.get(
            group=group,
            user=self.owner,
        )

        self.assertEqual(
            membership.role,
            GroupMembership.Role.OWNER,
        )

    def test_group_creator_is_visible_in_group_list(self):
        group = self.create_group()

        self.client.force_authenticate(user=self.owner)

        response = self.client.get(
            reverse("groups")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        group_ids = {
            item["id"]
            for item in response.data["data"]
        }

        self.assertIn(
            group.public_id,
            group_ids,
        )

    def test_owner_can_invite_user(self):
        group = self.create_group()
        invitation = self.create_invitation(group)

        self.assertEqual(
            invitation.group,
            group,
        )
        self.assertEqual(
            invitation.inviter,
            self.owner,
        )
        self.assertEqual(
            invitation.invitee,
            self.invitee,
        )
        self.assertEqual(
            invitation.status,
            GroupInvitation.Status.PENDING,
        )

    def test_regular_user_cannot_invite_to_group(self):
        group = self.create_group()

        GroupMembership.objects.create(
            group=group,
            user=self.other_user,
            role=GroupMembership.Role.MEMBER,
        )

        self.client.force_authenticate(
            user=self.other_user
        )

        response = self.client.post(
            reverse(
                "group-invitation-create",
                kwargs={
                    "group_id": group.public_id,
                },
            ),
            {
                "invitee_id": self.invitee.public_id,
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

    def test_duplicate_pending_invitation_is_rejected(self):
        group = self.create_group()
        self.create_invitation(group)

        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            reverse(
                "group-invitation-create",
                kwargs={
                    "group_id": group.public_id,
                },
            ),
            {
                "invitee_id": self.invitee.public_id,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
        )

        self.assertEqual(
            GroupInvitation.objects.filter(
                group=group,
                invitee=self.invitee,
                status=GroupInvitation.Status.PENDING,
            ).count(),
            1,
        )

    def test_invitee_can_view_received_invitation(self):
        group = self.create_group()
        invitation = self.create_invitation(group)

        self.client.force_authenticate(
            user=self.invitee
        )

        response = self.client.get(
            reverse("group-invitations")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        invitation_ids = {
            item["id"]
            for item in response.data["data"]
        }

        self.assertIn(
            invitation.public_id,
            invitation_ids,
        )

    def test_invitee_can_accept_invitation(self):
        group = self.create_group()
        invitation = self.create_invitation(group)

        self.client.force_authenticate(
            user=self.invitee
        )

        response = self.client.post(
            reverse(
                "group-invitation-respond",
                kwargs={
                    "invitation_id": invitation.public_id,
                },
            ),
            {
                "action": "accept",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        invitation.refresh_from_db()

        self.assertEqual(
            invitation.status,
            GroupInvitation.Status.ACCEPTED,
        )
        self.assertIsNotNone(
            invitation.responded_at
        )

        membership = GroupMembership.objects.get(
            group=group,
            user=self.invitee,
        )

        self.assertEqual(
            membership.role,
            GroupMembership.Role.MEMBER,
        )

    def test_invitee_can_reject_invitation(self):
        group = self.create_group()
        invitation = self.create_invitation(group)

        self.client.force_authenticate(
            user=self.invitee
        )

        response = self.client.post(
            reverse(
                "group-invitation-respond",
                kwargs={
                    "invitation_id": invitation.public_id,
                },
            ),
            {
                "action": "reject",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        invitation.refresh_from_db()

        self.assertEqual(
            invitation.status,
            GroupInvitation.Status.REJECTED,
        )

        self.assertFalse(
            GroupMembership.objects.filter(
                group=group,
                user=self.invitee,
            ).exists()
        )

    def test_another_user_cannot_respond_to_invitation(self):
        group = self.create_group()
        invitation = self.create_invitation(group)

        self.client.force_authenticate(
            user=self.other_user
        )

        response = self.client.post(
            reverse(
                "group-invitation-respond",
                kwargs={
                    "invitation_id": invitation.public_id,
                },
            ),
            {
                "action": "accept",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        invitation.refresh_from_db()

        self.assertEqual(
            invitation.status,
            GroupInvitation.Status.PENDING,
        )

    def test_non_member_cannot_view_group_detail(self):
        group = self.create_group()

        self.client.force_authenticate(
            user=self.other_user
        )

        response = self.client.get(
            reverse(
                "group-detail",
                kwargs={
                    "group_id": group.public_id,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_unauthenticated_user_cannot_create_group(self):
        self.client.force_authenticate(user=None)

        response = self.client.post(
            reverse("groups"),
            {
                "name": "Unauthorized Group",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )


class GroupEditDeleteTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="edit-owner@example.com",
            username="edit_group_owner",
            name="Edit Group Owner",
            password="StrongPassword123",
        )

        self.admin = User.objects.create_user(
            email="edit-admin@example.com",
            username="edit_group_admin",
            name="Edit Group Admin",
            password="StrongPassword123",
        )

        self.member = User.objects.create_user(
            email="edit-member@example.com",
            username="edit_group_member",
            name="Edit Group Member",
            password="StrongPassword123",
        )

        self.outsider = User.objects.create_user(
            email="edit-outsider@example.com",
            username="edit_group_outsider",
            name="Edit Group Outsider",
            password="StrongPassword123",
        )

        self.group = Group.objects.create(
            name="Original Group",
            description="Original description",
            creator=self.owner,
        )

        GroupMembership.objects.create(
            group=self.group,
            user=self.owner,
            role=GroupMembership.Role.OWNER,
        )

        GroupMembership.objects.create(
            group=self.group,
            user=self.admin,
            role=GroupMembership.Role.ADMIN,
        )

        GroupMembership.objects.create(
            group=self.group,
            user=self.member,
            role=GroupMembership.Role.MEMBER,
        )

        self.group_url = reverse(
            "group-detail",
            kwargs={
                "group_id": self.group.public_id,
            },
        )

    def test_owner_can_edit_group(self):
        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.patch(
            self.group_url,
            {
                "name": "Updated Group",
                "description": "Updated description",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.group.refresh_from_db()

        self.assertEqual(
            self.group.name,
            "Updated Group",
        )
        self.assertEqual(
            self.group.description,
            "Updated description",
        )

    def test_admin_can_edit_group(self):
        self.client.force_authenticate(
            user=self.admin
        )

        response = self.client.patch(
            self.group_url,
            {
                "description": "Changed by admin",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.group.refresh_from_db()

        self.assertEqual(
            self.group.description,
            "Changed by admin",
        )

    def test_member_cannot_edit_group(self):
        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.patch(
            self.group_url,
            {
                "name": "Unauthorized Name",
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

        self.group.refresh_from_db()

        self.assertEqual(
            self.group.name,
            "Original Group",
        )

    def test_empty_update_payload_is_rejected(self):
        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.patch(
            self.group_url,
            {},
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

    def test_owner_can_soft_delete_group(self):
        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.delete(
            self.group_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.group.refresh_from_db()

        self.assertIsNotNone(
            self.group.deleted_at
        )

        self.assertFalse(
            Group.objects.active().filter(
                pk=self.group.pk
            ).exists()
        )

    def test_admin_cannot_delete_group(self):
        self.client.force_authenticate(
            user=self.admin
        )

        response = self.client.delete(
            self.group_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.assertEqual(
            response.data["error"]["code"],
            "FORBIDDEN",
        )

        self.group.refresh_from_db()

        self.assertIsNone(
            self.group.deleted_at
        )

    def test_delete_group_cancels_pending_invitations(self):
        invitation = GroupInvitation.objects.create(
            group=self.group,
            inviter=self.owner,
            invitee=self.outsider,
        )

        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.delete(
            self.group_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        invitation.refresh_from_db()

        self.assertEqual(
            invitation.status,
            GroupInvitation.Status.CANCELED,
        )

        self.assertIsNotNone(
            invitation.responded_at
        )

    def test_deleted_group_is_not_accessible(self):
        self.group.soft_delete()

        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.get(
            self.group_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        self.assertEqual(
            response.data["error"]["code"],
            "NOT_FOUND",
        )

    def test_deleted_group_is_not_in_group_list(self):
        self.group.soft_delete()

        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.get(
            reverse("groups")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        group_ids = {
            item["id"]
            for item in response.data["data"]
        }

        self.assertNotIn(
            self.group.public_id,
            group_ids,
        )

    def test_outsider_cannot_edit_group(self):
        self.client.force_authenticate(
            user=self.outsider
        )

        response = self.client.patch(
            self.group_url,
            {
                "name": "Outsider Update",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_unauthenticated_user_cannot_modify_group(self):
        edit_response = self.client.patch(
            self.group_url,
            {
                "name": "Unauthorized",
            },
            format="json",
        )

        delete_response = self.client.delete(
            self.group_url
        )

        self.assertEqual(
            edit_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self.assertEqual(
            delete_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )


class GroupMembershipManagementTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="membership-owner@example.com",
            username="membership_owner",
            name="Membership Owner",
            password="StrongPassword123",
        )

        self.admin = User.objects.create_user(
            email="membership-admin@example.com",
            username="membership_admin",
            name="Membership Admin",
            password="StrongPassword123",
        )

        self.second_admin = User.objects.create_user(
            email="membership-admin-2@example.com",
            username="membership_admin_2",
            name="Second Admin",
            password="StrongPassword123",
        )

        self.member = User.objects.create_user(
            email="membership-member@example.com",
            username="membership_member",
            name="Membership Member",
            password="StrongPassword123",
        )

        self.second_member = User.objects.create_user(
            email="membership-member-2@example.com",
            username="membership_member_2",
            name="Second Member",
            password="StrongPassword123",
        )

        self.outsider = User.objects.create_user(
            email="membership-outsider@example.com",
            username="membership_outsider",
            name="Membership Outsider",
            password="StrongPassword123",
        )

        self.group = Group.objects.create(
            name="Membership Test Group",
            description="Group membership tests",
            creator=self.owner,
        )

        GroupMembership.objects.create(
            group=self.group,
            user=self.owner,
            role=GroupMembership.Role.OWNER,
        )

        GroupMembership.objects.create(
            group=self.group,
            user=self.admin,
            role=GroupMembership.Role.ADMIN,
        )

        GroupMembership.objects.create(
            group=self.group,
            user=self.second_admin,
            role=GroupMembership.Role.ADMIN,
        )

        GroupMembership.objects.create(
            group=self.group,
            user=self.member,
            role=GroupMembership.Role.MEMBER,
        )

        GroupMembership.objects.create(
            group=self.group,
            user=self.second_member,
            role=GroupMembership.Role.MEMBER,
        )

        self.members_url = reverse(
            "group-members",
            kwargs={
                "group_id": self.group.public_id,
            },
        )

        self.leave_url = reverse(
            "group-leave",
            kwargs={
                "group_id": self.group.public_id,
            },
        )

    def remove_url(self, user):
        return reverse(
            "group-member-remove",
            kwargs={
                "group_id": self.group.public_id,
                "user_id": user.public_id,
            },
        )

    def test_group_member_can_view_member_list(self):
        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.get(
            self.members_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        member_ids = {
            item["user_id"]
            for item in response.data["data"]
        }

        self.assertEqual(
            member_ids,
            {
                self.owner.public_id,
                self.admin.public_id,
                self.second_admin.public_id,
                self.member.public_id,
                self.second_member.public_id,
            },
        )

    def test_outsider_cannot_view_member_list(self):
        self.client.force_authenticate(
            user=self.outsider
        )

        response = self.client.get(
            self.members_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.assertEqual(
            response.data["error"]["code"],
            "FORBIDDEN",
        )

    def test_owner_can_remove_admin(self):
        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.delete(
            self.remove_url(self.admin)
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.assertFalse(
            GroupMembership.objects.filter(
                group=self.group,
                user=self.admin,
            ).exists()
        )

    def test_owner_can_remove_regular_member(self):
        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.delete(
            self.remove_url(self.member)
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.assertFalse(
            GroupMembership.objects.filter(
                group=self.group,
                user=self.member,
            ).exists()
        )

    def test_admin_can_remove_regular_member(self):
        self.client.force_authenticate(
            user=self.admin
        )

        response = self.client.delete(
            self.remove_url(self.member)
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.assertFalse(
            GroupMembership.objects.filter(
                group=self.group,
                user=self.member,
            ).exists()
        )

    def test_admin_cannot_remove_another_admin(self):
        self.client.force_authenticate(
            user=self.admin
        )

        response = self.client.delete(
            self.remove_url(self.second_admin)
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.assertTrue(
            GroupMembership.objects.filter(
                group=self.group,
                user=self.second_admin,
            ).exists()
        )

    def test_member_cannot_remove_another_member(self):
        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.delete(
            self.remove_url(self.second_member)
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.assertTrue(
            GroupMembership.objects.filter(
                group=self.group,
                user=self.second_member,
            ).exists()
        )

    def test_owner_cannot_be_removed(self):
        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.delete(
            self.remove_url(self.owner)
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.assertTrue(
            GroupMembership.objects.filter(
                group=self.group,
                user=self.owner,
                role=GroupMembership.Role.OWNER,
            ).exists()
        )

    def test_regular_member_can_leave_group(self):
        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.delete(
            self.leave_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.assertFalse(
            GroupMembership.objects.filter(
                group=self.group,
                user=self.member,
            ).exists()
        )

    def test_admin_can_leave_group(self):
        self.client.force_authenticate(
            user=self.admin
        )

        response = self.client.delete(
            self.leave_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.assertFalse(
            GroupMembership.objects.filter(
                group=self.group,
                user=self.admin,
            ).exists()
        )

    def test_owner_cannot_leave_group(self):
        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.delete(
            self.leave_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
        )

        self.assertEqual(
            response.data["error"]["code"],
            "CONFLICT",
        )

        self.assertTrue(
            GroupMembership.objects.filter(
                group=self.group,
                user=self.owner,
            ).exists()
        )

    def test_outsider_cannot_leave_group(self):
        self.client.force_authenticate(
            user=self.outsider
        )

        response = self.client.delete(
            self.leave_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_unauthenticated_user_cannot_manage_members(self):
        list_response = self.client.get(
            self.members_url
        )

        remove_response = self.client.delete(
            self.remove_url(self.member)
        )

        leave_response = self.client.delete(
            self.leave_url
        )

        self.assertEqual(
            list_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self.assertEqual(
            remove_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self.assertEqual(
            leave_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )


class ChannelCreationTopicManagementTests(APITestCase):
    def setUp(self):
        self.creator = User.objects.create_user(
            email="channel-creator@example.com",
            username="channel_creator",
            name="Channel Creator",
            password="StrongPassword123",
        )

        self.other_user = User.objects.create_user(
            email="channel-other@example.com",
            username="channel_other",
            name="Other User",
            password="StrongPassword123",
        )

        self.channel = Channel.objects.create(
            name="Development Channel",
            description="Development discussions",
            creator=self.creator,
        )

        ChannelMembership.objects.create(
            channel=self.channel,
            user=self.creator,
            role=ChannelMembership.Role.OWNER,
        )

        ChannelMembership.objects.create(
            channel=self.channel,
            user=self.other_user,
            role=ChannelMembership.Role.MEMBER,
        )

        self.channels_url = reverse("channels")

        self.channel_detail_url = reverse(
            "channel-detail",
            kwargs={
                "channel_id": self.channel.public_id,
            },
        )

        self.topics_url = reverse(
            "channel-topics",
            kwargs={
                "channel_id": self.channel.public_id,
            },
        )

    def topic_detail_url(self, topic):
        return reverse(
            "channel-topic-detail",
            kwargs={
                "channel_id": self.channel.public_id,
                "topic_id": topic.public_id,
            },
        )

    def test_authenticated_user_can_create_channel(self):
        self.client.force_authenticate(
            user=self.other_user
        )

        response = self.client.post(
            self.channels_url,
            {
                "name": "New Channel",
                "description": "New channel description",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        channel = Channel.objects.get(
            public_id=response.data["data"]["id"]
        )

        self.assertEqual(
            channel.name,
            "New Channel",
        )
        self.assertEqual(
            channel.creator,
            self.other_user,
        )

    def test_authenticated_user_can_list_channels(self):
        self.client.force_authenticate(
            user=self.other_user
        )

        response = self.client.get(
            self.channels_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        channel_ids = {
            item["id"]
            for item in response.data["data"]
        }

        self.assertIn(
            self.channel.public_id,
            channel_ids,
        )

    def test_authenticated_user_can_view_channel_detail(self):
        self.client.force_authenticate(
            user=self.other_user
        )

        response = self.client.get(
            self.channel_detail_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["data"]["id"],
            self.channel.public_id,
        )

    def test_channel_creator_can_create_topic(self):
        self.client.force_authenticate(
            user=self.creator
        )

        response = self.client.post(
            self.topics_url,
            {
                "name": "Backend",
                "description": "Backend discussions",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        topic = Topic.objects.get(
            public_id=response.data["data"]["id"]
        )

        self.assertEqual(
            topic.channel,
            self.channel,
        )
        self.assertEqual(
            topic.creator,
            self.creator,
        )
        self.assertEqual(
            topic.name,
            "Backend",
        )

    def test_non_creator_cannot_create_topic(self):
        self.client.force_authenticate(
            user=self.other_user
        )

        response = self.client.post(
            self.topics_url,
            {
                "name": "Unauthorized Topic",
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

    def test_duplicate_topic_name_is_rejected(self):
        Topic.objects.create(
            channel=self.channel,
            name="Backend",
            creator=self.creator,
        )

        self.client.force_authenticate(
            user=self.creator
        )

        response = self.client.post(
            self.topics_url,
            {
                "name": "backend",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
        )

        self.assertEqual(
            Topic.objects.filter(
                channel=self.channel,
                name__iexact="backend",
                deleted_at__isnull=True,
            ).count(),
            1,
        )

    def test_authenticated_user_can_list_channel_topics(self):
        topic = Topic.objects.create(
            channel=self.channel,
            name="Frontend",
            creator=self.creator,
        )

        self.client.force_authenticate(
            user=self.other_user
        )

        response = self.client.get(
            self.topics_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        topic_ids = {
            item["id"]
            for item in response.data["data"]
        }

        self.assertIn(
            topic.public_id,
            topic_ids,
        )

    def test_creator_can_update_topic(self):
        topic = Topic.objects.create(
            channel=self.channel,
            name="Old Topic",
            description="Old description",
            creator=self.creator,
        )

        self.client.force_authenticate(
            user=self.creator
        )

        response = self.client.patch(
            self.topic_detail_url(topic),
            {
                "name": "Updated Topic",
                "description": "Updated description",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        topic.refresh_from_db()

        self.assertEqual(
            topic.name,
            "Updated Topic",
        )
        self.assertEqual(
            topic.description,
            "Updated description",
        )

    def test_non_creator_cannot_update_topic(self):
        topic = Topic.objects.create(
            channel=self.channel,
            name="Protected Topic",
            creator=self.creator,
        )

        self.client.force_authenticate(
            user=self.other_user
        )

        response = self.client.patch(
            self.topic_detail_url(topic),
            {
                "name": "Unauthorized Update",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        topic.refresh_from_db()

        self.assertEqual(
            topic.name,
            "Protected Topic",
        )

    def test_creator_can_soft_delete_topic(self):
        topic = Topic.objects.create(
            channel=self.channel,
            name="Temporary Topic",
            creator=self.creator,
        )

        self.client.force_authenticate(
            user=self.creator
        )

        response = self.client.delete(
            self.topic_detail_url(topic)
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        topic.refresh_from_db()

        self.assertIsNotNone(
            topic.deleted_at
        )

        self.assertFalse(
            Topic.objects.active().filter(
                pk=topic.pk
            ).exists()
        )

    def test_deleted_topic_is_not_in_topic_list(self):
        topic = Topic.objects.create(
            channel=self.channel,
            name="Deleted Topic",
            creator=self.creator,
        )
        topic.soft_delete()

        self.client.force_authenticate(
            user=self.creator
        )

        response = self.client.get(
            self.topics_url
        )

        topic_ids = {
            item["id"]
            for item in response.data["data"]
        }

        self.assertNotIn(
            topic.public_id,
            topic_ids,
        )

    def test_topic_must_belong_to_requested_channel(self):
        other_channel = Channel.objects.create(
            name="Other Channel",
            creator=self.other_user,
        )

        topic = Topic.objects.create(
            channel=other_channel,
            name="Other Topic",
            creator=self.other_user,
        )

        self.client.force_authenticate(
            user=self.creator
        )

        response = self.client.get(
            reverse(
                "channel-topic-detail",
                kwargs={
                    "channel_id": self.channel.public_id,
                    "topic_id": topic.public_id,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_unauthenticated_user_cannot_create_channel_or_topic(self):
        channel_response = self.client.post(
            self.channels_url,
            {
                "name": "Unauthorized Channel",
            },
            format="json",
        )

        topic_response = self.client.post(
            self.topics_url,
            {
                "name": "Unauthorized Topic",
            },
            format="json",
        )

        self.assertEqual(
            channel_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self.assertEqual(
            topic_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )


class RoleCustomizationAccessControlTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="role-owner@example.com",
            username="role_owner",
            name="Role Owner",
            password="StrongPassword123",
        )

        self.member = User.objects.create_user(
            email="role-member@example.com",
            username="role_member",
            name="Role Member",
            password="StrongPassword123",
        )

        self.second_member = User.objects.create_user(
            email="role-member-2@example.com",
            username="role_member_2",
            name="Second Role Member",
            password="StrongPassword123",
        )

        self.outsider = User.objects.create_user(
            email="role-outsider@example.com",
            username="role_outsider",
            name="Role Outsider",
            password="StrongPassword123",
        )

        self.invitee = User.objects.create_user(
            email="role-invitee@example.com",
            username="role_invitee",
            name="Role Invitee",
            password="StrongPassword123",
        )

        self.group = Group.objects.create(
            name="Role Test Group",
            description="Role customization tests",
            creator=self.owner,
        )

        self.owner_membership = (
            GroupMembership.objects.create(
                group=self.group,
                user=self.owner,
                role=GroupMembership.Role.OWNER,
            )
        )

        self.member_membership = (
            GroupMembership.objects.create(
                group=self.group,
                user=self.member,
                role=GroupMembership.Role.MEMBER,
            )
        )

        self.second_member_membership = (
            GroupMembership.objects.create(
                group=self.group,
                user=self.second_member,
                role=GroupMembership.Role.MEMBER,
            )
        )

        self.other_group = Group.objects.create(
            name="Other Role Group",
            creator=self.outsider,
        )

        GroupMembership.objects.create(
            group=self.other_group,
            user=self.outsider,
            role=GroupMembership.Role.OWNER,
        )

        self.roles_url = reverse(
            "group-roles",
            kwargs={
                "group_id": self.group.public_id,
            },
        )

        self.group_detail_url = reverse(
            "group-detail",
            kwargs={
                "group_id": self.group.public_id,
            },
        )

        self.invitation_url = reverse(
            "group-invitation-create",
            kwargs={
                "group_id": self.group.public_id,
            },
        )

    def role_detail_url(self, role):
        return reverse(
            "group-role-detail",
            kwargs={
                "group_id": self.group.public_id,
                "role_id": role.public_id,
            },
        )

    def assign_role_url(self, user):
        return reverse(
            "group-member-role-assign",
            kwargs={
                "group_id": self.group.public_id,
                "user_id": user.public_id,
            },
        )

    def remove_role_url(self, user, role):
        return reverse(
            "group-member-role-remove",
            kwargs={
                "group_id": self.group.public_id,
                "user_id": user.public_id,
                "role_id": role.public_id,
            },
        )

    def remove_member_url(self, user):
        return reverse(
            "group-member-remove",
            kwargs={
                "group_id": self.group.public_id,
                "user_id": user.public_id,
            },
        )

    def create_role(
        self,
        name="Moderator",
        permissions=None,
    ):
        if permissions is None:
            permissions = []

        return AccessRole.objects.create(
            group=self.group,
            name=name,
            permissions=permissions,
            created_by=self.owner,
        )

    def test_owner_can_create_custom_role(self):
        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.post(
            self.roles_url,
            {
                "name": "Moderator",
                "permissions": [
                    AccessPermission.MANAGE_MEMBERS,
                    AccessPermission.DELETE_MESSAGES,
                ],
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        role = AccessRole.objects.get(
            public_id=response.data["data"]["id"]
        )

        self.assertEqual(
            role.name,
            "Moderator",
        )

        self.assertEqual(
            set(role.permissions),
            {
                AccessPermission.MANAGE_MEMBERS,
                AccessPermission.DELETE_MESSAGES,
            },
        )

        self.assertEqual(
            response.data["data"]["scope_type"],
            "group",
        )

    def test_regular_member_cannot_create_custom_role(self):
        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.post(
            self.roles_url,
            {
                "name": "Unauthorized Role",
                "permissions": [],
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

    def test_duplicate_role_name_is_rejected_case_insensitively(self):
        self.create_role(
            name="Moderator"
        )

        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.post(
            self.roles_url,
            {
                "name": "moderator",
                "permissions": [],
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
        )

        self.assertEqual(
            response.data["error"]["code"],
            "CONFLICT",
        )

    def test_group_member_can_list_active_roles(self):
        active_role = self.create_role(
            name="Active Role"
        )

        deleted_role = self.create_role(
            name="Deleted Role"
        )
        deleted_role.soft_delete()

        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.get(
            self.roles_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        role_ids = {
            item["id"]
            for item in response.data["data"]
        }

        self.assertIn(
            active_role.public_id,
            role_ids,
        )

        self.assertNotIn(
            deleted_role.public_id,
            role_ids,
        )

    def test_outsider_cannot_list_group_roles(self):
        self.client.force_authenticate(
            user=self.outsider
        )

        response = self.client.get(
            self.roles_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_owner_can_update_custom_role(self):
        role = self.create_role()

        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.patch(
            self.role_detail_url(role),
            {
                "name": "Senior Moderator",
                "permissions": [
                    AccessPermission.MANAGE_MEMBERS,
                ],
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        role.refresh_from_db()

        self.assertEqual(
            role.name,
            "Senior Moderator",
        )

        self.assertEqual(
            role.permissions,
            [
                AccessPermission.MANAGE_MEMBERS,
            ],
        )

    def test_owner_can_delete_role_and_remove_assignments(self):
        role = self.create_role()

        self.member_membership.custom_roles.add(
            role
        )

        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.delete(
            self.role_detail_url(role)
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        role.refresh_from_db()

        self.assertIsNotNone(
            role.deleted_at
        )

        self.assertFalse(
            self.member_membership.custom_roles.filter(
                pk=role.pk
            ).exists()
        )

    def test_owner_can_assign_role_to_group_member(self):
        role = self.create_role(
            permissions=[
                AccessPermission.MANAGE_GROUP,
            ]
        )

        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.post(
            self.assign_role_url(self.member),
            {
                "role_id": role.public_id,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertTrue(
            self.member_membership.custom_roles.filter(
                pk=role.pk
            ).exists()
        )

        assigned_role_ids = {
            item["id"]
            for item in response.data[
                "data"
            ]["custom_roles"]
        }

        self.assertIn(
            role.public_id,
            assigned_role_ids,
        )

    def test_role_from_another_group_cannot_be_assigned(self):
        other_role = AccessRole.objects.create(
            group=self.other_group,
            name="Other Group Role",
            permissions=[
                AccessPermission.MANAGE_GROUP,
            ],
            created_by=self.outsider,
        )

        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.post(
            self.assign_role_url(self.member),
            {
                "role_id": other_role.public_id,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        self.assertFalse(
            self.member_membership.custom_roles.filter(
                pk=other_role.pk
            ).exists()
        )

    def test_role_cannot_be_assigned_to_non_member(self):
        role = self.create_role()

        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.post(
            self.assign_role_url(self.outsider),
            {
                "role_id": role.public_id,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_manage_roles_permission_allows_role_management(self):
        role_manager = self.create_role(
            name="Role Manager",
            permissions=[
                AccessPermission.MANAGE_ROLES,
            ],
        )

        self.member_membership.custom_roles.add(
            role_manager
        )

        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.post(
            self.roles_url,
            {
                "name": "Created By Member",
                "permissions": [
                    AccessPermission.SEND_MESSAGES,
                ],
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertTrue(
            AccessRole.objects.active().filter(
                group=self.group,
                name="Created By Member",
                created_by=self.member,
            ).exists()
        )

    def test_manage_group_permission_allows_group_update(self):
        group_manager = self.create_role(
            name="Group Manager",
            permissions=[
                AccessPermission.MANAGE_GROUP,
            ],
        )

        self.member_membership.custom_roles.add(
            group_manager
        )

        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.patch(
            self.group_detail_url,
            {
                "name": "Updated By Custom Role",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.group.refresh_from_db()

        self.assertEqual(
            self.group.name,
            "Updated By Custom Role",
        )

    def test_manage_invitations_permission_allows_inviting_user(self):
        invitation_manager = self.create_role(
            name="Invitation Manager",
            permissions=[
                AccessPermission.MANAGE_INVITATIONS,
            ],
        )

        self.member_membership.custom_roles.add(
            invitation_manager
        )

        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.post(
            self.invitation_url,
            {
                "invitee_id": self.invitee.public_id,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertTrue(
            GroupInvitation.objects.filter(
                group=self.group,
                inviter=self.member,
                invitee=self.invitee,
                status=GroupInvitation.Status.PENDING,
            ).exists()
        )

    def test_manage_members_permission_allows_removing_member(self):
        membership_manager = self.create_role(
            name="Membership Manager",
            permissions=[
                AccessPermission.MANAGE_MEMBERS,
            ],
        )

        self.member_membership.custom_roles.add(
            membership_manager
        )

        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.delete(
            self.remove_member_url(
                self.second_member
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.assertFalse(
            GroupMembership.objects.filter(
                group=self.group,
                user=self.second_member,
            ).exists()
        )

    def test_invalid_permission_is_rejected(self):
        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.post(
            self.roles_url,
            {
                "name": "Invalid Role",
                "permissions": [
                    "destroy_everything",
                ],
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

    def test_unauthenticated_user_cannot_manage_roles(self):
        list_response = self.client.get(
            self.roles_url
        )

        create_response = self.client.post(
            self.roles_url,
            {
                "name": "Anonymous Role",
                "permissions": [],
            },
            format="json",
        )

        self.assertEqual(
            list_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self.assertEqual(
            create_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )


class ChannelEditDeleteTests(APITestCase):
    def setUp(self):
        self.creator = User.objects.create_user(
            email="channel-edit-creator@example.com",
            username="channel_edit_creator",
            name="Channel Edit Creator",
            password="StrongPassword123",
        )

        self.other_user = User.objects.create_user(
            email="channel-edit-other@example.com",
            username="channel_edit_other",
            name="Channel Edit Other",
            password="StrongPassword123",
        )

        self.channel = Channel.objects.create(
            name="Original Channel",
            description="Original description",
            creator=self.creator,
        )

        ChannelMembership.objects.create(
            channel=self.channel,
            user=self.creator,
            role=ChannelMembership.Role.OWNER,
        )

        ChannelMembership.objects.create(
            channel=self.channel,
            user=self.other_user,
            role=ChannelMembership.Role.MEMBER,
        )

        self.channel_detail_url = reverse(
            "channel-detail",
            kwargs={
                "channel_id": self.channel.public_id,
            },
        )

        self.channels_url = reverse(
            "channels"
        )

        self.topics_url = reverse(
            "channel-topics",
            kwargs={
                "channel_id": self.channel.public_id,
            },
        )

    def test_creator_can_update_channel(self):
        self.client.force_authenticate(
            user=self.creator
        )

        response = self.client.patch(
            self.channel_detail_url,
            {
                "name": "Updated Channel",
                "description": "Updated description",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.channel.refresh_from_db()

        self.assertEqual(
            self.channel.name,
            "Updated Channel",
        )

        self.assertEqual(
            self.channel.description,
            "Updated description",
        )

        self.assertEqual(
            response.data["data"]["name"],
            "Updated Channel",
        )

    def test_non_creator_cannot_update_channel(self):
        self.client.force_authenticate(
            user=self.other_user
        )

        response = self.client.patch(
            self.channel_detail_url,
            {
                "name": "Unauthorized Update",
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

        self.channel.refresh_from_db()

        self.assertEqual(
            self.channel.name,
            "Original Channel",
        )

    def test_empty_channel_update_is_rejected(self):
        self.client.force_authenticate(
            user=self.creator
        )

        response = self.client.patch(
            self.channel_detail_url,
            {},
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

    def test_creator_can_soft_delete_channel(self):
        self.client.force_authenticate(
            user=self.creator
        )

        response = self.client.delete(
            self.channel_detail_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.channel.refresh_from_db()

        self.assertIsNotNone(
            self.channel.deleted_at
        )

        self.assertFalse(
            Channel.objects.active().filter(
                pk=self.channel.pk
            ).exists()
        )

    def test_non_creator_cannot_delete_channel(self):
        self.client.force_authenticate(
            user=self.other_user
        )

        response = self.client.delete(
            self.channel_detail_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.channel.refresh_from_db()

        self.assertIsNone(
            self.channel.deleted_at
        )

    def test_deleted_channel_is_hidden_from_list_and_detail(self):
        self.channel.soft_delete()

        self.client.force_authenticate(
            user=self.creator
        )

        list_response = self.client.get(
            self.channels_url
        )

        channel_ids = {
            item["id"]
            for item in list_response.data["data"]
        }

        self.assertNotIn(
            self.channel.public_id,
            channel_ids,
        )

        detail_response = self.client.get(
            self.channel_detail_url
        )

        self.assertEqual(
            detail_response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_topics_of_deleted_channel_are_not_accessible(self):
        topic = Topic.objects.create(
            channel=self.channel,
            name="Hidden Topic",
            creator=self.creator,
        )

        self.channel.soft_delete()

        self.client.force_authenticate(
            user=self.creator
        )

        response = self.client.get(
            self.topics_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        self.assertFalse(
            Topic.objects.active().filter(
                pk=topic.pk
            ).exists()
        )

    def test_unauthenticated_user_cannot_update_or_delete_channel(self):
        update_response = self.client.patch(
            self.channel_detail_url,
            {
                "name": "Anonymous Update",
            },
            format="json",
        )

        delete_response = self.client.delete(
            self.channel_detail_url
        )

        self.assertEqual(
            update_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self.assertEqual(
            delete_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )


class ChannelMembershipPermissionTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="channel-member-owner@example.com",
            username="channel_member_owner",
            name="Channel Member Owner",
            password="StrongPassword123",
        )

        self.admin = User.objects.create_user(
            email="channel-member-admin@example.com",
            username="channel_member_admin",
            name="Channel Member Admin",
            password="StrongPassword123",
        )

        self.second_admin = User.objects.create_user(
            email="channel-member-admin-2@example.com",
            username="channel_member_admin_2",
            name="Second Channel Admin",
            password="StrongPassword123",
        )

        self.member = User.objects.create_user(
            email="channel-member@example.com",
            username="channel_member",
            name="Channel Member",
            password="StrongPassword123",
        )

        self.second_member = User.objects.create_user(
            email="channel-member-2@example.com",
            username="channel_member_2",
            name="Second Channel Member",
            password="StrongPassword123",
        )

        self.outsider = User.objects.create_user(
            email="channel-outsider@example.com",
            username="channel_outsider",
            name="Channel Outsider",
            password="StrongPassword123",
        )

        self.channel = Channel.objects.create(
            name="Membership Channel",
            description="Channel membership tests",
            creator=self.owner,
        )

        self.owner_membership = (
            ChannelMembership.objects.create(
                channel=self.channel,
                user=self.owner,
                role=ChannelMembership.Role.OWNER,
            )
        )

        self.admin_membership = (
            ChannelMembership.objects.create(
                channel=self.channel,
                user=self.admin,
                role=ChannelMembership.Role.ADMIN,
            )
        )

        self.second_admin_membership = (
            ChannelMembership.objects.create(
                channel=self.channel,
                user=self.second_admin,
                role=ChannelMembership.Role.ADMIN,
            )
        )

        self.member_membership = (
            ChannelMembership.objects.create(
                channel=self.channel,
                user=self.member,
                role=ChannelMembership.Role.MEMBER,
            )
        )

        self.second_member_membership = (
            ChannelMembership.objects.create(
                channel=self.channel,
                user=self.second_member,
                role=ChannelMembership.Role.MEMBER,
            )
        )

        self.channels_url = reverse(
            "channels"
        )

        self.channel_detail_url = reverse(
            "channel-detail",
            kwargs={
                "channel_id": self.channel.public_id,
            },
        )

        self.members_url = reverse(
            "channel-members",
            kwargs={
                "channel_id": self.channel.public_id,
            },
        )

        self.leave_url = reverse(
            "channel-leave",
            kwargs={
                "channel_id": self.channel.public_id,
            },
        )

        self.topics_url = reverse(
            "channel-topics",
            kwargs={
                "channel_id": self.channel.public_id,
            },
        )

    def member_detail_url(self, user):
        return reverse(
            "channel-member-detail",
            kwargs={
                "channel_id": self.channel.public_id,
                "user_id": user.public_id,
            },
        )

    def create_custom_role(
        self,
        name,
        permissions,
    ):
        return AccessRole.objects.create(
            channel=self.channel,
            name=name,
            permissions=permissions,
            created_by=self.owner,
        )

    def test_creating_channel_creates_owner_membership(self):
        self.client.force_authenticate(
            user=self.outsider
        )

        response = self.client.post(
            self.channels_url,
            {
                "name": "New Membership Channel",
                "description": "Created through API",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        channel = Channel.objects.get(
            public_id=response.data["data"]["id"]
        )

        self.assertTrue(
            ChannelMembership.objects.filter(
                channel=channel,
                user=self.outsider,
                role=ChannelMembership.Role.OWNER,
            ).exists()
        )

    def test_channel_list_only_contains_joined_channels(self):
        hidden_channel = Channel.objects.create(
            name="Hidden Channel",
            creator=self.outsider,
        )

        ChannelMembership.objects.create(
            channel=hidden_channel,
            user=self.outsider,
            role=ChannelMembership.Role.OWNER,
        )

        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.get(
            self.channels_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        channel_ids = {
            item["id"]
            for item in response.data["data"]
        }

        self.assertIn(
            self.channel.public_id,
            channel_ids,
        )

        self.assertNotIn(
            hidden_channel.public_id,
            channel_ids,
        )

    def test_outsider_cannot_view_channel_detail(self):
        self.client.force_authenticate(
            user=self.outsider
        )

        response = self.client.get(
            self.channel_detail_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_member_can_list_channel_members(self):
        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.get(
            self.members_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        user_ids = {
            item["user_id"]
            for item in response.data["data"]
        }

        self.assertEqual(
            user_ids,
            {
                self.owner.public_id,
                self.admin.public_id,
                self.second_admin.public_id,
                self.member.public_id,
                self.second_member.public_id,
            },
        )

    def test_outsider_cannot_list_channel_members(self):
        self.client.force_authenticate(
            user=self.outsider
        )

        response = self.client.get(
            self.members_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_owner_can_add_member(self):
        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.post(
            self.members_url,
            {
                "user_id": self.outsider.public_id,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertTrue(
            ChannelMembership.objects.filter(
                channel=self.channel,
                user=self.outsider,
                role=ChannelMembership.Role.MEMBER,
            ).exists()
        )

    def test_duplicate_channel_member_is_rejected(self):
        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.post(
            self.members_url,
            {
                "user_id": self.member.public_id,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
        )

    def test_regular_member_cannot_add_member(self):
        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.post(
            self.members_url,
            {
                "user_id": self.outsider.public_id,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_owner_can_promote_member_to_admin(self):
        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.patch(
            self.member_detail_url(
                self.member
            ),
            {
                "role": ChannelMembership.Role.ADMIN,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.member_membership.refresh_from_db()

        self.assertEqual(
            self.member_membership.role,
            ChannelMembership.Role.ADMIN,
        )

    def test_non_owner_cannot_change_builtin_role(self):
        self.client.force_authenticate(
            user=self.admin
        )

        response = self.client.patch(
            self.member_detail_url(
                self.second_member
            ),
            {
                "role": ChannelMembership.Role.ADMIN,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_admin_can_remove_regular_member(self):
        self.client.force_authenticate(
            user=self.admin
        )

        response = self.client.delete(
            self.member_detail_url(
                self.member
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.assertFalse(
            ChannelMembership.objects.filter(
                channel=self.channel,
                user=self.member,
            ).exists()
        )

    def test_admin_cannot_remove_another_admin(self):
        self.client.force_authenticate(
            user=self.admin
        )

        response = self.client.delete(
            self.member_detail_url(
                self.second_admin
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.assertTrue(
            ChannelMembership.objects.filter(
                channel=self.channel,
                user=self.second_admin,
            ).exists()
        )

    def test_owner_can_remove_admin(self):
        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.delete(
            self.member_detail_url(
                self.admin
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.assertFalse(
            ChannelMembership.objects.filter(
                channel=self.channel,
                user=self.admin,
            ).exists()
        )

    def test_owner_cannot_be_removed(self):
        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.delete(
            self.member_detail_url(
                self.owner
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.assertTrue(
            ChannelMembership.objects.filter(
                channel=self.channel,
                user=self.owner,
                role=ChannelMembership.Role.OWNER,
            ).exists()
        )

    def test_regular_member_can_leave_channel(self):
        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.delete(
            self.leave_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.assertFalse(
            ChannelMembership.objects.filter(
                channel=self.channel,
                user=self.member,
            ).exists()
        )

    def test_owner_cannot_leave_channel(self):
        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.delete(
            self.leave_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
        )

    def test_admin_cannot_delete_channel(self):
        self.client.force_authenticate(
            user=self.admin
        )

        response = self.client.delete(
            self.channel_detail_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.channel.refresh_from_db()

        self.assertIsNone(
            self.channel.deleted_at
        )

    def test_admin_can_update_channel(self):
        self.client.force_authenticate(
            user=self.admin
        )

        response = self.client.patch(
            self.channel_detail_url,
            {
                "name": "Updated By Admin",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.channel.refresh_from_db()

        self.assertEqual(
            self.channel.name,
            "Updated By Admin",
        )

    def test_admin_can_create_topic(self):
        self.client.force_authenticate(
            user=self.admin
        )

        response = self.client.post(
            self.topics_url,
            {
                "name": "Admin Topic",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

    def test_custom_manage_channel_permission_allows_update(self):
        role = self.create_custom_role(
            "Channel Manager",
            [
                AccessPermission.MANAGE_CHANNEL,
            ],
        )

        self.member_membership.custom_roles.add(
            role
        )

        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.patch(
            self.channel_detail_url,
            {
                "description": "Updated by custom role",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.channel.refresh_from_db()

        self.assertEqual(
            self.channel.description,
            "Updated by custom role",
        )

    def test_custom_manage_topics_permission_allows_topic_creation(self):
        role = self.create_custom_role(
            "Topic Manager",
            [
                AccessPermission.MANAGE_TOPICS,
            ],
        )

        self.member_membership.custom_roles.add(
            role
        )

        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.post(
            self.topics_url,
            {
                "name": "Custom Role Topic",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

    def test_admin_can_create_custom_role(self):
        self.client.force_authenticate(
            user=self.admin
        )

        response = self.client.post(
            reverse(
                "channel-roles",
                kwargs={
                    "channel_id":
                        self.channel.public_id,
                },
            ),
            {
                "name": "Admin Created Role",
                "permissions": [
                    AccessPermission.MANAGE_TOPICS,
                ],
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

    def test_custom_manage_roles_permission_allows_role_creation(self):
        role = self.create_custom_role(
            "Role Manager",
            [
                AccessPermission.MANAGE_ROLES,
            ],
        )

        self.member_membership.custom_roles.add(
            role
        )

        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.post(
            reverse(
                "channel-roles",
                kwargs={
                    "channel_id":
                        self.channel.public_id,
                },
            ),
            {
                "name": "Created By Custom Role",
                "permissions": [
                    AccessPermission.MANAGE_TOPICS,
                ],
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

    def test_regular_member_cannot_create_custom_role(self):
        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.post(
            reverse(
                "channel-roles",
                kwargs={
                    "channel_id":
                        self.channel.public_id,
                },
            ),
            {
                "name": "Unauthorized Role",
                "permissions": [
                    AccessPermission.MANAGE_TOPICS,
                ],
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_admin_can_get_channel_invite_link(self):
        self.client.force_authenticate(
            user=self.admin
        )

        response = self.client.post(
            reverse(
                "channel-invite-link",
                kwargs={
                    "channel_id":
                        self.channel.public_id,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertTrue(
            response.data["data"]["token"]
        )

    def test_custom_manage_invitations_allows_invite_link(self):
        role = self.create_custom_role(
            "Invite Manager",
            [
                AccessPermission.MANAGE_INVITATIONS,
            ],
        )

        self.member_membership.custom_roles.add(
            role
        )

        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.post(
            reverse(
                "channel-invite-link",
                kwargs={
                    "channel_id":
                        self.channel.public_id,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_regular_member_cannot_get_channel_invite_link(self):
        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.post(
            reverse(
                "channel-invite-link",
                kwargs={
                    "channel_id":
                        self.channel.public_id,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_manage_channel_members_does_not_grant_invite_link(self):
        role = self.create_custom_role(
            "Member Manager",
            [
                AccessPermission.MANAGE_CHANNEL_MEMBERS,
            ],
        )

        self.member_membership.custom_roles.add(
            role
        )

        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.post(
            reverse(
                "channel-invite-link",
                kwargs={
                    "channel_id":
                        self.channel.public_id,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )


class ChannelMessagingPermissionTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="channel-message-owner@example.com",
            username="channel_message_owner",
            name="Channel Message Owner",
            password="StrongPassword123",
        )

        self.member = User.objects.create_user(
            email="channel-message-member@example.com",
            username="channel_message_member",
            name="Channel Message Member",
            password="StrongPassword123",
        )

        self.outsider = User.objects.create_user(
            email="channel-message-outsider@example.com",
            username="channel_message_outsider",
            name="Channel Message Outsider",
            password="StrongPassword123",
        )

        self.channel = Channel.objects.create(
            name="Messaging Channel",
            description="Channel messaging tests",
            creator=self.owner,
        )

        ChannelMembership.objects.create(
            channel=self.channel,
            user=self.owner,
            role=ChannelMembership.Role.OWNER,
        )

        self.member_membership = (
            ChannelMembership.objects.create(
                channel=self.channel,
                user=self.member,
                role=ChannelMembership.Role.MEMBER,
            )
        )

        self.other_channel = Channel.objects.create(
            name="Other Messaging Channel",
            creator=self.owner,
        )

        ChannelMembership.objects.create(
            channel=self.other_channel,
            user=self.owner,
            role=ChannelMembership.Role.OWNER,
        )

        self.messages_url = reverse(
            "messages"
        )

        self.channel_messages_url = reverse(
            "messages-channels",
            kwargs={
                "channel_id": self.channel.public_id,
            },
        )

        self.search_url = reverse(
            "messages-search"
        )

        self.broadcast_patcher = patch(
            "api.services.messages."
            "broadcast_message_event_task.delay"
        )
        self.mock_broadcast = (
            self.broadcast_patcher.start()
        )
        self.addCleanup(
            self.broadcast_patcher.stop
        )

        self.client.force_authenticate(
            user=self.owner
        )

        topic_response = self.client.post(
            reverse(
                "channel-topics",
                kwargs={
                    "channel_id":
                        self.other_channel.public_id,
                },
            ),
            {
                "name": "Other Channel Topic",
            },
            format="json",
        )

        self.assertEqual(
            topic_response.status_code,
            status.HTTP_201_CREATED,
        )

        self.other_topic_id = (
            topic_response.data["data"]["id"]
        )

        self.client.force_authenticate(
            user=None
        )

    def message_detail_url(self, message):
        return reverse(
            "message-detail",
            kwargs={
                "message_id": message.public_id,
            },
        )

    def create_channel_message(
        self,
        sender=None,
        content="Channel test message",
    ):
        return Message.objects.create(
            user=sender or self.owner,
            message_type=Message.MessageType.CHANNEL,
            channel_id=self.channel.public_id,
            content=content,
        )

    def create_custom_role(
        self,
        name,
        permissions,
    ):
        return AccessRole.objects.create(
            channel=self.channel,
            name=name,
            permissions=permissions,
            created_by=self.owner,
        )

    def test_member_can_send_channel_message(self):
        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.post(
            self.messages_url,
            {
                "channel_id":
                    self.channel.public_id,
                "content": "Hello channel",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        message = Message.objects.get(
            public_id=response.data["data"]["id"]
        )

        self.assertEqual(
            message.user,
            self.member,
        )
        self.assertEqual(
            message.channel_id,
            self.channel.public_id,
        )
        self.assertEqual(
            message.message_type,
            Message.MessageType.CHANNEL,
        )

    def test_outsider_cannot_send_channel_message(self):
        self.client.force_authenticate(
            user=self.outsider
        )

        response = self.client.post(
            self.messages_url,
            {
                "channel_id":
                    self.channel.public_id,
                "content": "Forbidden message",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_member_can_list_channel_messages(self):
        message = self.create_channel_message()

        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.get(
            self.channel_messages_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        message_ids = {
            item["id"]
            for item in response.data["data"]
        }

        self.assertIn(
            message.public_id,
            message_ids,
        )

    def test_outsider_cannot_list_channel_messages(self):
        self.create_channel_message()

        self.client.force_authenticate(
            user=self.outsider
        )

        response = self.client.get(
            self.channel_messages_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_outsider_cannot_view_channel_message_detail(self):
        message = self.create_channel_message()

        self.client.force_authenticate(
            user=self.outsider
        )

        response = self.client.get(
            self.message_detail_url(message)
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_sender_can_edit_own_channel_message(self):
        message = self.create_channel_message(
            sender=self.member
        )

        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.patch(
            self.message_detail_url(message),
            {
                "content": "Edited own message",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        message.refresh_from_db()

        self.assertEqual(
            message.content,
            "Edited own message",
        )
        self.assertTrue(
            message.is_edited
        )

    def test_sender_can_delete_own_channel_message(self):
        message = self.create_channel_message(
            sender=self.member
        )

        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.delete(
            self.message_detail_url(message)
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        message.refresh_from_db()

        self.assertIsNotNone(
            message.deleted_at
        )

    def test_member_cannot_edit_another_users_message(self):
        message = self.create_channel_message(
            sender=self.owner
        )

        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.patch(
            self.message_detail_url(message),
            {
                "content": "Unauthorized edit",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_member_cannot_delete_another_users_message(self):
        message = self.create_channel_message(
            sender=self.owner
        )

        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.delete(
            self.message_detail_url(message)
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        message.refresh_from_db()

        self.assertIsNone(
            message.deleted_at
        )

    def test_edit_messages_permission_allows_editing_others(self):
        role = self.create_custom_role(
            "Message Editor",
            [
                AccessPermission.EDIT_MESSAGES,
            ],
        )

        self.member_membership.custom_roles.add(
            role
        )

        message = self.create_channel_message(
            sender=self.owner
        )

        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.patch(
            self.message_detail_url(message),
            {
                "content":
                    "Edited with permission",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        message.refresh_from_db()

        self.assertEqual(
            message.content,
            "Edited with permission",
        )

    def test_delete_messages_permission_allows_deleting_others(self):
        role = self.create_custom_role(
            "Message Moderator",
            [
                AccessPermission.DELETE_MESSAGES,
            ],
        )

        self.member_membership.custom_roles.add(
            role
        )

        message = self.create_channel_message(
            sender=self.owner
        )

        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.delete(
            self.message_detail_url(message)
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        message.refresh_from_db()

        self.assertIsNotNone(
            message.deleted_at
        )

    def test_topic_from_another_channel_is_rejected(self):
        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.post(
            self.messages_url,
            {
                "channel_id":
                    self.channel.public_id,
                "topic_id":
                    self.other_topic_id,
                "content":
                    "Invalid cross-channel topic",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        self.assertFalse(
            Message.objects.filter(
                user=self.member,
                content="Invalid cross-channel topic",
            ).exists()
        )

    def test_general_search_hides_channel_messages_from_outsider(self):
        message = self.create_channel_message(
            content="Secret channel phrase"
        )

        self.client.force_authenticate(
            user=self.outsider
        )

        response = self.client.get(
            self.search_url,
            {
                "q": "Secret channel phrase",
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        message_ids = {
            item["id"]
            for item in response.data["data"]
        }

        self.assertNotIn(
            message.public_id,
            message_ids,
        )

    def _create_attachment(self, owner=None):
        owner = owner or self.member

        return MediaAttachment.objects.create(
            owner=owner,
            file_key=(
                f"media/{owner.public_id}/"
                f"image/sample.png"
            ),
            file_url=(
                "http://localhost:9000/"
                f"discord-media/{owner.public_id}.png"
            ),
            original_name="sample.png",
            content_type="image/png",
            size=1024,
            media_type=MediaAttachment.MediaType.IMAGE,
        )

    def test_member_cannot_send_channel_media_without_upload_permission(self):
        attachment = self._create_attachment()

        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.post(
            self.messages_url,
            {
                "channel_id":
                    self.channel.public_id,
                "media_ids": [
                    attachment.public_id,
                ],
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

        attachment.refresh_from_db()

        self.assertIsNone(
            attachment.message_id
        )

    def test_upload_media_permission_allows_channel_attachments(self):
        role = self.create_custom_role(
            "Media Uploader",
            [
                AccessPermission.UPLOAD_MEDIA,
            ],
        )

        self.member_membership.custom_roles.add(
            role
        )

        attachment = self._create_attachment()

        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.post(
            self.messages_url,
            {
                "channel_id":
                    self.channel.public_id,
                "media_ids": [
                    attachment.public_id,
                ],
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        attachment.refresh_from_db()

        self.assertIsNotNone(
            attachment.message_id
        )

    def test_channel_admin_can_delete_other_members_message(self):
        admin = User.objects.create_user(
            email="channel-message-admin@example.com",
            username="channel_message_admin",
            name="Channel Message Admin",
            password="StrongPassword123",
        )

        ChannelMembership.objects.create(
            channel=self.channel,
            user=admin,
            role=ChannelMembership.Role.ADMIN,
        )

        message = self.create_channel_message(
            sender=self.member
        )

        self.client.force_authenticate(
            user=admin
        )

        response = self.client.delete(
            self.message_detail_url(message)
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        message.refresh_from_db()

        self.assertIsNotNone(
            message.deleted_at
        )

    def test_owner_can_send_channel_media_without_custom_role(self):
        attachment = self._create_attachment(
            owner=self.owner
        )

        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.post(
            self.messages_url,
            {
                "channel_id":
                    self.channel.public_id,
                "media_ids": [
                    attachment.public_id,
                ],
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )


class GroupMessageDeletionTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="group-delete-owner@example.com",
            username="group_delete_owner",
            name="Group Delete Owner",
            password="StrongPassword123",
        )

        self.admin = User.objects.create_user(
            email="group-delete-admin@example.com",
            username="group_delete_admin",
            name="Group Delete Admin",
            password="StrongPassword123",
        )

        self.member = User.objects.create_user(
            email="group-delete-member@example.com",
            username="group_delete_member",
            name="Group Delete Member",
            password="StrongPassword123",
        )

        self.group = Group.objects.create(
            name="Deletion Group",
            creator=self.owner,
        )

        GroupMembership.objects.create(
            group=self.group,
            user=self.owner,
            role=GroupMembership.Role.OWNER,
        )

        GroupMembership.objects.create(
            group=self.group,
            user=self.admin,
            role=GroupMembership.Role.ADMIN,
        )

        GroupMembership.objects.create(
            group=self.group,
            user=self.member,
            role=GroupMembership.Role.MEMBER,
        )

        self.message = Message.objects.create(
            user=self.member,
            message_type=Message.MessageType.GROUP,
            group_id=self.group.public_id,
            content="Member group message",
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
        self.mock_broadcast = (
            self.broadcast_patcher.start()
        )
        self.addCleanup(
            self.broadcast_patcher.stop
        )

    def test_group_owner_can_delete_other_members_message(self):
        self.client.force_authenticate(
            user=self.owner
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

    def test_group_admin_cannot_delete_other_members_message(self):
        self.client.force_authenticate(
            user=self.admin
        )

        response = self.client.delete(
            self.message_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.message.refresh_from_db()

        self.assertIsNone(
            self.message.deleted_at
        )

    def test_group_member_cannot_delete_other_members_message(self):
        owner_message = Message.objects.create(
            user=self.owner,
            message_type=Message.MessageType.GROUP,
            group_id=self.group.public_id,
            content="Owner group message",
        )

        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.delete(
            reverse(
                "message-detail",
                kwargs={
                    "message_id":
                        owner_message.public_id,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        owner_message.refresh_from_db()

        self.assertIsNone(
            owner_message.deleted_at
        )