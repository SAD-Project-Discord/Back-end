from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import User


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
