import uuid
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from django.conf import settings


class StorageServiceError(Exception):
    def __init__(self, code, message, status_code=400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def get_s3_client():
    protocol = "https" if settings.MINIO_USE_SSL else "http"
    endpoint_url = f"{protocol}://{settings.MINIO_ENDPOINT}"
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
    )


def ensure_bucket_exists(client=None):
    if client is None:
        client = get_s3_client()
    bucket_name = settings.MINIO_BUCKET_NAME
    try:
        client.head_bucket(Bucket=bucket_name)
    except ClientError:
        try:
            client.create_bucket(Bucket=bucket_name)
        except Exception as exc:
            raise StorageServiceError(
                "STORAGE_ERROR",
                f"خطا در ایجاد باکت ذخیره‌سازی: {str(exc)}",
                500,
            ) from exc


def upload_file(file_obj, filename=None, folder="uploads"):
    client = get_s3_client()
    ensure_bucket_exists(client)

    original_name = filename or getattr(file_obj, "name", "file")
    ext = original_name.rsplit(".", 1)[-1] if "." in original_name else ""
    unique_id = uuid.uuid4().hex
    file_key = f"{folder}/{unique_id}.{ext}" if ext else f"{folder}/{unique_id}"

    content_type = getattr(file_obj, "content_type", "application/octet-stream")
    file_size = getattr(file_obj, "size", 0)

    try:
        file_obj.seek(0)
    except Exception:
        pass

    try:
        client.upload_fileobj(
            file_obj,
            settings.MINIO_BUCKET_NAME,
            file_key,
            ExtraArgs={"ContentType": content_type},
        )
    except Exception as exc:
        raise StorageServiceError(
            "UPLOAD_FAILED",
            f"خطا در آپلود فایل در MinIO/S3: {str(exc)}",
            500,
        ) from exc

    file_url = f"{settings.MINIO_PUBLIC_URL}/{file_key}"
    return {
        "file_key": file_key,
        "file_url": file_url,
        "filename": original_name,
        "content_type": content_type,
        "size": file_size,
    }


def delete_file(file_key):
    client = get_s3_client()
    try:
        client.delete_object(Bucket=settings.MINIO_BUCKET_NAME, Key=file_key)
        return True
    except Exception as exc:
        raise StorageServiceError(
            "DELETE_FAILED",
            f"خطا در حذف فایل از MinIO/S3: {str(exc)}",
            500,
        ) from exc


def get_presigned_url(file_key, expires_in=3600):
    client = get_s3_client()
    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.MINIO_BUCKET_NAME, "Key": file_key},
            ExpiresIn=expires_in,
        )
        return url
    except Exception as exc:
        raise StorageServiceError(
            "PRESIGNED_URL_FAILED",
            f"خطا در تولید لینک دسترسی: {str(exc)}",
            500,
        ) from exc
