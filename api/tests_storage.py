from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import (
    SimpleUploadedFile,
)
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import (
    MediaAttachment,
    Message,
    User,
)
from api.services.storage import (
    StorageServiceError,
    delete_file,
    get_presigned_url,
    upload_file,
    validate_media_file,
)


class StorageServiceTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="storageuser@example.com",
            username="storageuser",
            name="Storage User",
            password="Password123!",
        )
        self.client.force_authenticate(user=self.user)

    @patch("api.services.storage.get_s3_client")
    def test_upload_file_success(self, mock_get_client):
        mock_s3 = MagicMock()
        mock_get_client.return_value = mock_s3

        file_obj = SimpleUploadedFile("test_image.png", b"file_content", content_type="image/png")
        result = upload_file(file_obj, filename="test_image.png", folder="test_folder")

        self.assertIn("file_key", result)
        self.assertIn("file_url", result)
        self.assertTrue(result["file_key"].startswith("test_folder/"))
        self.assertEqual(result["filename"], "test_image.png")
        self.assertEqual(result["content_type"], "image/png")
        mock_s3.upload_fileobj.assert_called_once()

    @patch("api.services.storage.get_s3_client")
    def test_delete_file_success(self, mock_get_client):
        mock_s3 = MagicMock()
        mock_get_client.return_value = mock_s3

        success = delete_file("uploads/test_file.png")
        self.assertTrue(success)
        mock_s3.delete_object.assert_called_once_with(
            Bucket="discord-media", Key="uploads/test_file.png"
        )

    @patch("api.services.storage.get_s3_client")
    def test_get_presigned_url(self, mock_get_client):
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = "http://localhost:9000/discord-media/uploads/test.png?token=123"
        mock_get_client.return_value = mock_s3

        url = get_presigned_url("uploads/test.png")
        self.assertIn("token=123", url)

    @patch("api.services.storage.get_s3_client")
    def test_upload_media_api_endpoint(self, mock_get_client):
        mock_s3 = MagicMock()
        mock_get_client.return_value = mock_s3

        test_file = SimpleUploadedFile("sample.pdf", b"%PDF-1.4 sample content", content_type="application/pdf")
        url = reverse("storage-upload")
        response = self.client.post(url, {"file": test_file}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["filename"], "sample.pdf")

    def test_upload_media_api_missing_file(self):
        url = reverse("storage-upload")
        response = self.client.post(url, {}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")


class MediaMessageTests(APITestCase):
    def setUp(self):
        self.sender = User.objects.create_user(
            email="media-sender@example.com",
            username="media_sender",
            name="Media Sender",
            password="StrongPassword123",
        )

        self.receiver = User.objects.create_user(
            email="media-receiver@example.com",
            username="media_receiver",
            name="Media Receiver",
            password="StrongPassword123",
        )

        self.outsider = User.objects.create_user(
            email="media-outsider@example.com",
            username="media_outsider",
            name="Media Outsider",
            password="StrongPassword123",
        )

        self.messages_url = reverse(
            "messages"
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

    def create_attachment(
        self,
        owner=None,
        media_type=MediaAttachment.MediaType.IMAGE,
        content_type="image/png",
        original_name="sample.png",
    ):
        owner = owner or self.sender

        return MediaAttachment.objects.create(
            owner=owner,
            file_key=(
                f"media/{owner.public_id}/"
                f"{media_type}/{original_name}"
            ),
            file_url=(
                "http://localhost:9000/"
                f"discord-media/{original_name}"
            ),
            original_name=original_name,
            content_type=content_type,
            size=1024,
            media_type=media_type,
        )

    def send_media_message(
        self,
        attachment,
        sender=None,
    ):
        sender = sender or self.sender

        self.client.force_authenticate(
            user=sender
        )

        return self.client.post(
            self.messages_url,
            {
                "receiver_id":
                    self.receiver.public_id,
                "media_ids": [
                    attachment.public_id,
                ],
            },
            format="json",
        )

    def media_detail_url(self, attachment):
        return reverse(
            "storage-file-detail",
            kwargs={
                "media_id":
                    attachment.public_id,
            },
        )

    @patch(
        "api.services.storage.get_s3_client"
    )
    def test_upload_image_creates_attachment(
        self,
        mock_get_client,
    ):
        mock_get_client.return_value = (
            MagicMock()
        )

        self.client.force_authenticate(
            user=self.sender
        )

        image = SimpleUploadedFile(
            "photo.png",
            b"image-content",
            content_type="image/png",
        )

        response = self.client.post(
            reverse("storage-upload"),
            {
                "file": image,
            },
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        attachment = (
            MediaAttachment.objects.get(
                public_id=
                    response.data["data"]["id"]
            )
        )

        self.assertEqual(
            attachment.owner,
            self.sender,
        )
        self.assertEqual(
            attachment.media_type,
            MediaAttachment.MediaType.IMAGE,
        )
        self.assertEqual(
            attachment.content_type,
            "image/png",
        )

    @patch(
        "api.services.storage.get_s3_client"
    )
    def test_upload_video_creates_video_attachment(
        self,
        mock_get_client,
    ):
        mock_get_client.return_value = (
            MagicMock()
        )

        self.client.force_authenticate(
            user=self.sender
        )

        video = SimpleUploadedFile(
            "video.mp4",
            b"video-content",
            content_type="video/mp4",
        )

        response = self.client.post(
            reverse("storage-upload"),
            {
                "file": video,
            },
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(
            response.data["data"]["media_type"],
            MediaAttachment.MediaType.VIDEO,
        )

    @patch(
        "api.services.storage.get_s3_client"
    )
    def test_upload_audio_creates_audio_attachment(
        self,
        mock_get_client,
    ):
        mock_get_client.return_value = (
            MagicMock()
        )

        self.client.force_authenticate(
            user=self.sender
        )

        audio = SimpleUploadedFile(
            "voice.mp3",
            b"audio-content",
            content_type="audio/mpeg",
        )

        response = self.client.post(
            reverse("storage-upload"),
            {
                "file": audio,
            },
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(
            response.data["data"]["media_type"],
            MediaAttachment.MediaType.AUDIO,
        )

    @patch(
        "api.services.storage.get_s3_client"
    )
    def test_upload_document_creates_document_attachment(
        self,
        mock_get_client,
    ):
        mock_get_client.return_value = (
            MagicMock()
        )

        self.client.force_authenticate(
            user=self.sender
        )

        document = SimpleUploadedFile(
            "report.pdf",
            b"%PDF-1.4 test",
            content_type="application/pdf",
        )

        response = self.client.post(
            reverse("storage-upload"),
            {
                "file": document,
            },
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(
            response.data["data"]["media_type"],
            MediaAttachment.MediaType.DOCUMENT,
        )

    @patch(
        "api.services.storage.get_s3_client"
    )
    def test_upload_m4a_creates_audio_attachment(
        self,
        mock_get_client,
    ):
        mock_get_client.return_value = (
            MagicMock()
        )

        self.client.force_authenticate(
            user=self.sender
        )

        audio = SimpleUploadedFile(
            "voice.m4a",
            b"m4a-content",
            content_type="audio/x-m4a",
        )

        response = self.client.post(
            reverse("storage-upload"),
            {
                "file": audio,
            },
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(
            response.data["data"]["media_type"],
            MediaAttachment.MediaType.AUDIO,
        )

    @patch(
        "api.services.storage.get_s3_client"
    )
    def test_upload_avi_creates_video_attachment(
        self,
        mock_get_client,
    ):
        mock_get_client.return_value = (
            MagicMock()
        )

        self.client.force_authenticate(
            user=self.sender
        )

        video = SimpleUploadedFile(
            "clip.avi",
            b"avi-content",
            content_type="video/x-msvideo",
        )

        response = self.client.post(
            reverse("storage-upload"),
            {
                "file": video,
            },
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(
            response.data["data"]["media_type"],
            MediaAttachment.MediaType.VIDEO,
        )

    @patch(
        "api.services.storage.get_s3_client"
    )
    def test_upload_zip_creates_document_attachment(
        self,
        mock_get_client,
    ):
        mock_get_client.return_value = (
            MagicMock()
        )

        self.client.force_authenticate(
            user=self.sender
        )

        archive = SimpleUploadedFile(
            "bundle.zip",
            b"PK-zip-content",
            content_type="application/x-zip-compressed",
        )

        response = self.client.post(
            reverse("storage-upload"),
            {
                "file": archive,
            },
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(
            response.data["data"]["media_type"],
            MediaAttachment.MediaType.DOCUMENT,
        )

    @patch(
        "api.services.storage.get_s3_client"
    )
    def test_upload_m4a_with_octet_stream_uses_extension(
        self,
        mock_get_client,
    ):
        mock_get_client.return_value = (
            MagicMock()
        )

        self.client.force_authenticate(
            user=self.sender
        )

        audio = SimpleUploadedFile(
            "voice.m4a",
            b"m4a-content",
            content_type="application/octet-stream",
        )

        response = self.client.post(
            reverse("storage-upload"),
            {
                "file": audio,
            },
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(
            response.data["data"]["media_type"],
            MediaAttachment.MediaType.AUDIO,
        )

    def test_unsupported_file_type_is_rejected(self):
        self.client.force_authenticate(
            user=self.sender
        )

        file_obj = SimpleUploadedFile(
            "program.exe",
            b"MZ-content",
            content_type=(
                "application/x-msdownload"
            ),
        )

        response = self.client.post(
            reverse("storage-upload"),
            {
                "file": file_obj,
            },
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            response.data["error"]["code"],
            "UNSUPPORTED_MEDIA_TYPE",
        )

    def test_oversized_file_is_rejected(self):
        file_obj = MagicMock()
        file_obj.content_type = "image/png"
        file_obj.size = (
            10 * 1024 * 1024
        ) + 1

        with self.assertRaises(
            StorageServiceError
        ) as context:
            validate_media_file(file_obj)

        self.assertEqual(
            context.exception.code,
            "FILE_TOO_LARGE",
        )

    def test_message_can_contain_only_media(self):
        attachment = self.create_attachment()

        response = self.send_media_message(
            attachment
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        attachment.refresh_from_db()

        self.assertIsNotNone(
            attachment.message_id
        )
        self.assertIsNotNone(
            attachment.attached_at
        )

        self.assertEqual(
            response.data["data"]["content"],
            "",
        )
        self.assertEqual(
            response.data["data"]["media"][0][
                "id"
            ],
            attachment.public_id,
        )
        self.assertEqual(
            response.data["data"]["media"][0][
                "media_type"
            ],
            MediaAttachment.MediaType.IMAGE,
        )

    def test_user_cannot_attach_another_users_file(self):
        attachment = self.create_attachment(
            owner=self.outsider
        )

        response = self.send_media_message(
            attachment
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        attachment.refresh_from_db()

        self.assertIsNone(
            attachment.message_id
        )

    def test_attached_file_cannot_be_reused(self):
        attachment = self.create_attachment()

        first_response = (
            self.send_media_message(
                attachment
            )
        )

        self.assertEqual(
            first_response.status_code,
            status.HTTP_201_CREATED,
        )

        second_response = (
            self.send_media_message(
                attachment
            )
        )

        self.assertEqual(
            second_response.status_code,
            status.HTTP_409_CONFLICT,
        )

    def test_duplicate_media_ids_are_rejected(self):
        attachment = self.create_attachment()

        self.client.force_authenticate(
            user=self.sender
        )

        response = self.client.post(
            self.messages_url,
            {
                "receiver_id":
                    self.receiver.public_id,
                "media_ids": [
                    attachment.public_id,
                    attachment.public_id,
                ],
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_more_than_ten_attachments_are_rejected(self):
        attachments = [
            self.create_attachment(
                original_name=f"file-{index}.png"
            )
            for index in range(11)
        ]

        self.client.force_authenticate(
            user=self.sender
        )

        response = self.client.post(
            self.messages_url,
            {
                "receiver_id":
                    self.receiver.public_id,
                "media_ids": [
                    attachment.public_id
                    for attachment in attachments
                ],
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    @patch(
        "api.services.storage."
        "get_presigned_url"
    )
    def test_receiver_can_download_attached_media(
        self,
        mock_presigned_url,
    ):
        mock_presigned_url.return_value = (
            "http://minio/file?token=123"
        )

        attachment = self.create_attachment()

        response = self.send_media_message(
            attachment
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.client.force_authenticate(
            user=self.receiver
        )

        response = self.client.get(
            self.media_detail_url(attachment)
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.data["data"][
                "presigned_url"
            ],
            "http://minio/file?token=123",
        )

        self.client.force_authenticate(
            user=self.outsider
        )

        response = self.client.get(
            self.media_detail_url(attachment)
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    @patch(
        "api.services.storage.delete_file"
    )
    def test_owner_can_delete_unattached_media(
        self,
        mock_delete_file,
    ):
        mock_delete_file.return_value = True

        attachment = self.create_attachment()

        self.client.force_authenticate(
            user=self.sender
        )

        response = self.client.delete(
            self.media_detail_url(attachment)
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.assertFalse(
            MediaAttachment.objects.filter(
                pk=attachment.pk
            ).exists()
        )

        mock_delete_file.assert_called_once_with(
            attachment.file_key
        )

    @patch(
        "api.services.storage.delete_file"
    )
    def test_attached_media_cannot_be_deleted_directly(
        self,
        mock_delete_file,
    ):
        attachment = self.create_attachment()

        response = self.send_media_message(
            attachment
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.client.force_authenticate(
            user=self.sender
        )

        response = self.client.delete(
            self.media_detail_url(attachment)
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
        )

        self.assertTrue(
            MediaAttachment.objects.filter(
                pk=attachment.pk
            ).exists()
        )

        mock_delete_file.assert_not_called()

    @patch(
        "api.services.storage."
        "get_presigned_url"
    )
    def test_deleted_message_media_is_not_accessible(
        self,
        mock_presigned_url,
    ):
        attachment = self.create_attachment()

        response = self.send_media_message(
            attachment
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        attachment.refresh_from_db()

        message = attachment.message
        message.soft_delete()

        self.client.force_authenticate(
            user=self.receiver
        )

        response = self.client.get(
            self.media_detail_url(attachment)
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        mock_presigned_url.assert_not_called()