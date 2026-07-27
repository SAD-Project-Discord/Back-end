from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Message, MessageReaction, Sticker, StickerPack, User


class StickerAndReactionTestCase(APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            email="stickeruser1@example.com", username="stickeruser1", name="Sticker One", password="Password123!"
        )
        self.user2 = User.objects.create_user(
            email="stickeruser2@example.com", username="stickeruser2", name="Sticker Two", password="Password123!"
        )
        self.client.force_authenticate(user=self.user1)

        # Create StickerPack & Sticker
        self.pack = StickerPack.objects.create(
            name="Pepe Pack", description="Famous Pepe stickers", icon_url="http://example.com/icon.png"
        )
        self.sticker = Sticker.objects.create(
            pack=self.pack, emoji_alias=":pepe_happy:", image_url="http://example.com/pepe.png"
        )

        # Create a Message
        self.msg = Message.objects.create(
            user=self.user1,
            receiver=self.user2,
            message_type=Message.MessageType.DIRECT,
            content="Hello with emojis and stickers",
        )

    def test_list_and_get_sticker_packs(self):
        url_list = reverse("sticker-packs-list")
        response = self.client.get(url_list)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        packs = response.data["data"]
        self.assertEqual(len(packs), 1)
        self.assertEqual(packs[0]["name"], "Pepe Pack")
        self.assertEqual(len(packs[0]["stickers"]), 1)

        url_detail = reverse("sticker-pack-detail", kwargs={"pack_id": self.pack.public_id})
        response_detail = self.client.get(url_detail)
        self.assertEqual(response_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(response_detail.data["data"]["id"], self.pack.public_id)

    def test_add_and_remove_emoji_reaction(self):
        url_add = reverse("message-reactions-add", kwargs={"message_id": self.msg.public_id})

        # Add emoji reaction 👍
        response_add = self.client.post(url_add, {"emoji": "👍"}, format="json")
        self.assertEqual(response_add.status_code, status.HTTP_201_CREATED)
        reaction_id = response_add.data["data"]["id"]
        self.assertEqual(response_add.data["data"]["emoji"], "👍")

        # Remove reaction
        url_remove = reverse(
            "message-reactions-remove",
            kwargs={"message_id": self.msg.public_id, "reaction_id": reaction_id},
        )
        response_remove = self.client.delete(url_remove)
        self.assertEqual(response_remove.status_code, status.HTTP_204_NO_CONTENT)

        self.assertFalse(MessageReaction.objects.filter(public_id=reaction_id).exists())

    def test_add_sticker_reaction(self):
        url_add = reverse("message-reactions-add", kwargs={"message_id": self.msg.public_id})
        response_add = self.client.post(url_add, {"sticker_id": self.sticker.public_id}, format="json")

        self.assertEqual(response_add.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response_add.data["data"]["sticker_id"], self.sticker.public_id)
