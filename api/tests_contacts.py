from unittest.mock import patch
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import UserContact, UserPrivacySetting

User = get_user_model()


class PersistentContactsTestCase(APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username="user1",
            email="user1@example.com",
            password="password123",
            name="User One",
        )
        self.user2 = User.objects.create_user(
            username="user2",
            email="user2@example.com",
            password="password123",
            name="User Two",
        )
        self.user3 = User.objects.create_user(
            username="user3",
            email="user3@example.com",
            password="password123",
            name="User Three",
        )

    @patch("api.tasks.broadcast_message_event_task.delay")
    def test_add_contact_success_and_ws_event(self, mock_delay):
        self.client.force_authenticate(user=self.user1)
        response = self.client.post(
            "/api/v1/users/contacts",
            {"user_id": self.user2.public_id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["data"]["id"], self.user2.public_id)
        self.assertTrue(response.data["data"]["is_contact"])

        self.assertTrue(UserContact.objects.filter(owner=self.user1, contact=self.user2).exists())
        mock_delay.assert_called_once()
        self.assertEqual(mock_delay.call_args[0][0], "contact.added")

    def test_add_contact_self_fails(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.post(
            "/api/v1/users/contacts",
            {"user_id": self.user1.public_id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")

    def test_add_contact_idempotent(self):
        self.client.force_authenticate(user=self.user1)
        res1 = self.client.post(
            "/api/v1/users/contacts",
            {"user_id": self.user2.public_id},
            format="json",
        )
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        res2 = self.client.post(
            "/api/v1/users/contacts",
            {"user_id": self.user2.public_id},
            format="json",
        )
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(UserContact.objects.filter(owner=self.user1, contact=self.user2).count(), 1)

    def test_add_contact_nonexistent_user_fails(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.post(
            "/api/v1/users/contacts",
            {"user_id": "usr_nonexistent999"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("api.tasks.broadcast_message_event_task.delay")
    def test_remove_contact_success_and_idempotent(self, mock_delay):
        UserContact.objects.create(owner=self.user1, contact=self.user2)
        self.client.force_authenticate(user=self.user1)

        res1 = self.client.delete(f"/api/v1/users/contacts/{self.user2.public_id}")
        self.assertEqual(res1.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(UserContact.objects.filter(owner=self.user1, contact=self.user2).exists())
        mock_delay.assert_called_once_with(
            "contact.removed",
            f"user_{self.user1.public_id}",
            {"user_id": self.user2.public_id},
        )

        res2 = self.client.delete(f"/api/v1/users/contacts/{self.user2.public_id}")
        self.assertEqual(res2.status_code, status.HTTP_204_NO_CONTENT)

    def test_list_contacts_pagination_and_search(self):
        self.client.force_authenticate(user=self.user1)
        UserContact.objects.create(owner=self.user1, contact=self.user2)
        UserContact.objects.create(owner=self.user1, contact=self.user3)

        # Query with limit 1
        res1 = self.client.get("/api/v1/users/contacts?limit=1")
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res1.data["data"]), 1)
        self.assertTrue(res1.data["meta"]["has_more"])
        self.assertIsNotNone(res1.data["meta"]["next_cursor"])

        cursor = res1.data["meta"]["next_cursor"]
        res2 = self.client.get(f"/api/v1/users/contacts?limit=1&cursor={cursor}")
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res2.data["data"]), 1)
        self.assertFalse(res2.data["meta"]["has_more"])

        # Search query
        res_search = self.client.get("/api/v1/users/contacts?q=Three")
        self.assertEqual(res_search.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_search.data["data"]), 1)
        self.assertEqual(res_search.data["data"][0]["id"], self.user3.public_id)

    def test_user_profile_and_search_includes_is_contact(self):
        UserContact.objects.create(owner=self.user1, contact=self.user2)
        self.client.force_authenticate(user=self.user1)

        # Profile user2 (contact)
        res_user2 = self.client.get(f"/api/v1/users/{self.user2.public_id}")
        self.assertEqual(res_user2.status_code, status.HTTP_200_OK)
        self.assertTrue(res_user2.data["data"]["is_contact"])

        # Profile user3 (not contact)
        res_user3 = self.client.get(f"/api/v1/users/{self.user3.public_id}")
        self.assertEqual(res_user3.status_code, status.HTTP_200_OK)
        self.assertFalse(res_user3.data["data"]["is_contact"])

        # Search users
        res_search = self.client.get("/api/v1/users/search?q=user")
        self.assertEqual(res_search.status_code, status.HTTP_200_OK)
        for u in res_search.data["data"]:
            if u["id"] == self.user2.public_id:
                self.assertTrue(u["is_contact"])
            elif u["id"] == self.user3.public_id:
                self.assertFalse(u["is_contact"])

    def test_privacy_contacts_only_checks_saved_contact(self):
        from api.services.privacy import can_add_user_to_group, get_user_privacy
        p = get_user_privacy(self.user2)
        p.group_add_permission = UserPrivacySetting.GroupAddPermission.CONTACTS
        p.allow_direct_add = True
        p.save()

        # Before user2 saves user1 as contact -> user1 cannot add user2 to group
        self.assertFalse(can_add_user_to_group(target_user=self.user2, inviter=self.user1))

        # user2 saves user1 as contact
        UserContact.objects.create(owner=self.user2, contact=self.user1)

        # Now user1 can add user2 to group
        self.assertTrue(can_add_user_to_group(target_user=self.user2, inviter=self.user1))
