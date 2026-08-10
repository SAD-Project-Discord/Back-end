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
