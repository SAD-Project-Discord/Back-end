from unittest.mock import MagicMock, patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import User
from api.services.storage import delete_file, get_presigned_url, upload_file


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
