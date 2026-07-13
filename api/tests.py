from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import (
    Group,
    GroupInvitation,
    GroupMembership,
    Message,
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