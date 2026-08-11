from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Group, GroupMembership, Message, User


class UserSearchAndContactsTestCase(APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            email="mmd1@example.com",
            username="mmd",
            name="MMD One",
            password="Password123!",
        )
        self.user2 = User.objects.create_user(
            email="mmd2@example.com",
            username="mmd2",
            name="MMD Two",
            password="Password123!",
        )
        self.user3 = User.objects.create_user(
            email="other@example.com",
            username="otheruser",
            name="Other Person",
            password="Password123!",
        )

        # Create DM between user1 and user2
        Message.objects.create(
            user=self.user1,
            receiver=self.user2,
            message_type=Message.MessageType.DIRECT,
            content="Hello MMD2",
        )

    def test_search_users_query_param(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.get("/api/v1/users/search", {"q": "mmd"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        usernames = [u["username"] for u in response.data["data"]]
        self.assertIn("mmd", usernames)
        self.assertIn("mmd2", usernames)
        self.assertNotIn("otheruser", usernames)

    def test_search_users_query_param_with_slash(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.get("/api/v1/users/search/", {"q": "mmd"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])

    def test_list_user_contacts(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.get("/api/v1/users/contacts")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        usernames = [u["username"] for u in response.data["data"]]
        self.assertIn("mmd2", usernames)
        self.assertNotIn("otheruser", usernames)


class GroupAddMemberTestCase(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com",
            username="grpowner",
            name="Group Owner",
            password="Password123!",
        )
        self.target_user = User.objects.create_user(
            email="target@example.com",
            username="targetuser",
            name="Target User",
            password="Password123!",
        )
        self.group = Group.objects.create(name="Test Group", creator=self.owner)
        GroupMembership.objects.create(
            group=self.group,
            user=self.owner,
            role=GroupMembership.Role.OWNER,
        )

    def test_add_group_member_by_user_id(self):
        self.client.force_authenticate(user=self.owner)
        url = f"/api/v1/groups/{self.group.public_id}/members"
        response = self.client.post(url, {"user_id": self.target_user.public_id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["user_id"], self.target_user.public_id)

    def test_add_group_member_by_username(self):
        self.client.force_authenticate(user=self.owner)
        url = f"/api/v1/groups/{self.group.public_id}/members/"
        response = self.client.post(url, {"username": "targetuser"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])

    def test_add_existing_member_fails(self):
        self.client.force_authenticate(user=self.owner)
        url = f"/api/v1/groups/{self.group.public_id}/members"
        response = self.client.post(url, {"user_id": self.owner.public_id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)


class AuthRegistrationErrorMessagesTestCase(APITestCase):
    def setUp(self):
        User.objects.create_user(
            email="taken@example.com",
            username="takenusername",
            name="Taken User",
            password="Password123!",
        )

    def test_register_duplicate_username_error_message(self):
        url = reverse("auth-register")
        response = self.client.post(
            url,
            {
                "email": "newuser@example.com",
                "username": "takenusername",
                "password": "Password123!",
                "name": "New User",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["error"]["message"], "Username is already taken.")


class PrivacyAndAvatarLifecycleTestCase(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner_p@example.com",
            username="owner_p",
            name="Owner P",
            password="Password123!",
        )
        self.friend = User.objects.create_user(
            email="friend_p@example.com",
            username="friend_p",
            name="Friend P",
            password="Password123!",
        )
        self.stranger = User.objects.create_user(
            email="stranger_p@example.com",
            username="stranger_p",
            name="Stranger P",
            password="Password123!",
        )
        self.target = User.objects.create_user(
            email="target_p@example.com",
            username="target_p",
            name="Target P",
            password="Password123!",
        )

        # Make friend and target contacts via DM
        Message.objects.create(
            user=self.friend,
            receiver=self.target,
            message_type=Message.MessageType.DIRECT,
            content="Hello DM contact",
        )

        # Set target privacy to 'contacts'
        from api.services.privacy import get_user_privacy
        p = get_user_privacy(self.target)
        p.group_add_permission = "contacts"
        p.allow_direct_add = True
        p.save()

        # Group owned by stranger
        self.stranger_group = Group.objects.create(name="Stranger Group", creator=self.stranger)
        GroupMembership.objects.create(group=self.stranger_group, user=self.stranger, role=GroupMembership.Role.OWNER)

        # Group owned by friend
        self.friend_group = Group.objects.create(name="Friend Group", creator=self.friend)
        GroupMembership.objects.create(group=self.friend_group, user=self.friend, role=GroupMembership.Role.OWNER)

    def test_contacts_only_blocks_stranger_from_direct_adding(self):
        self.client.force_authenticate(user=self.stranger)
        url = f"/api/v1/groups/{self.stranger_group.public_id}/members"
        response = self.client.post(url, {"user_id": self.target.public_id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_contacts_only_allows_friend_contact_from_direct_adding(self):
        self.client.force_authenticate(user=self.friend)
        url = f"/api/v1/groups/{self.friend_group.public_id}/members"
        response = self.client.post(url, {"user_id": self.target.public_id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_invitation_respects_privacy_settings(self):
        # Set target privacy to 'nobody'
        from api.services.privacy import get_user_privacy
        p = get_user_privacy(self.target)
        p.group_add_permission = "nobody"
        p.save()

        self.client.force_authenticate(user=self.friend)
        url = f"/api/v1/groups/{self.friend_group.public_id}/invitations"
        response = self.client.post(url, {"invitee_id": self.target.public_id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_avatar_replacement_deletes_old_file(self):
        from api.models import MediaAttachment
        self.client.force_authenticate(user=self.owner)

        old_attachment = MediaAttachment.objects.create(
            owner=self.owner,
            file_key="media/usr_owner/image/old_avatar.png",
            file_url="http://localhost:9000/discord-media/media/usr_owner/image/old_avatar.png",
            original_name="old.png",
            content_type="image/png",
            size=100,
            media_type=MediaAttachment.MediaType.IMAGE,
        )

        # Set user avatar to old_attachment
        self.owner.profile_picture = old_attachment.file_url
        self.owner.save()

        # Update avatar via PATCH /users/me
        new_url = "http://localhost:9000/discord-media/media/usr_owner/image/new_avatar.png"
        with patch("api.services.storage.delete_file") as mock_delete:
            response = self.client.patch(reverse("users-me"), {"avatar_url": new_url}, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            mock_delete.assert_called_once_with("media/usr_owner/image/old_avatar.png")

        # Verify old attachment object was deleted
        self.assertFalse(MediaAttachment.objects.filter(pk=old_attachment.pk).exists())

    def test_invitation_allowed_when_allow_direct_add_false(self):
        from api.services.privacy import get_user_privacy
        p = get_user_privacy(self.target)
        p.group_add_permission = "everyone"
        p.allow_direct_add = False
        p.save()

        self.client.force_authenticate(user=self.friend)
        url = f"/api/v1/groups/{self.friend_group.public_id}/invitations"
        response = self.client.post(url, {"invitee_id": self.target.public_id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_group_with_is_private_and_member_ids(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            "/api/v1/groups/",
            {
                "name": "Secret Group",
                "description": "Top secret",
                "is_private": True,
                "member_ids": [self.friend.public_id],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["data"]["is_private"])
        member_ids = [m["user_id"] for m in response.data["data"]["members"]]
        self.assertIn(self.friend.public_id, member_ids)

    def test_group_invites_alias_url(self):
        self.client.force_authenticate(user=self.friend)
        url = f"/api/v1/groups/{self.friend_group.public_id}/invites"
        response = self.client.post(url, {"invitee_id": self.target.public_id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

