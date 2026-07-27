from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Group, GroupMembership, User, UserPrivacySetting
from api.services.privacy import can_add_user_to_group, get_user_privacy, update_user_privacy


class PrivacyControlTestCase(APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            email="privacy1@example.com", username="privacy1", name="Privacy One", password="Password123!"
        )
        self.user2 = User.objects.create_user(
            email="privacy2@example.com", username="privacy2", name="Privacy Two", password="Password123!"
        )
        self.client.force_authenticate(user=self.user1)

    def test_get_and_update_user_privacy(self):
        url = reverse("users-me-privacy")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["group_add_permission"], "everyone")
        self.assertTrue(response.data["data"]["allow_direct_add"])

        # Update privacy to nobody
        patch_response = self.client.patch(
            url, {"group_add_permission": "nobody", "allow_direct_add": False}, format="json"
        )
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.data["data"]["group_add_permission"], "nobody")
        self.assertFalse(patch_response.data["data"]["allow_direct_add"])

    def test_can_add_user_to_group_privacy_check(self):
        # Default: allowed
        self.assertTrue(can_add_user_to_group(self.user2))

        # Restrict user2 privacy
        update_user_privacy(self.user2, {"group_add_permission": "nobody", "allow_direct_add": False})

        # Check: blocked
        self.assertFalse(can_add_user_to_group(self.user2))
