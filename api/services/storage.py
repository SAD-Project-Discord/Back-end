import uuid

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from django.conf import settings
from django.db import transaction

from api.models import (
    ChannelMembership,
    GroupMembership,
    MediaAttachment,
    Message,
)


class StorageServiceError(Exception):
    def __init__(self, code, message, status_code=400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


MEDIA_UPLOAD_RULES = {
    MediaAttachment.MediaType.IMAGE: {
        "content_types": {
            "image/jpeg",
            "image/png",
            "image/gif",
            "image/webp",
        },
        "max_size": 10 * 1024 * 1024,
    },
    MediaAttachment.MediaType.VIDEO: {
        "content_types": {
            "video/mp4",
            "video/webm",
            "video/quicktime",
        },
        "max_size": 100 * 1024 * 1024,
    },
    MediaAttachment.MediaType.AUDIO: {
        "content_types": {
            "audio/mpeg",
            "audio/mp4",
            "audio/ogg",
            "audio/wav",
            "audio/x-wav",
            "audio/webm",
        },
        "max_size": 25 * 1024 * 1024,
    },
    MediaAttachment.MediaType.DOCUMENT: {
        "content_types": {
            "application/pdf",
            "text/plain",
            "application/msword",
            (
                "application/vnd.openxmlformats-"
                "officedocument.wordprocessingml.document"
            ),
            "application/vnd.ms-excel",
            (
                "application/vnd.openxmlformats-"
                "officedocument.spreadsheetml.sheet"
            ),
            "application/vnd.ms-powerpoint",
            (
                "application/vnd.openxmlformats-"
                "officedocument.presentationml.presentation"
            ),
            "application/zip",
        },
        "max_size": 25 * 1024 * 1024,
    },
}


def get_s3_client(endpoint_url=None):
    protocol = "https" if settings.MINIO_USE_SSL else "http"
    if not endpoint_url:
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

    try:
        import json
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": ["*"]},
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{bucket_name}/*"],
                }
            ],
        }
        client.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(policy))
    except Exception:
        pass


def validate_media_file(file_obj):
    content_type = (
        getattr(
            file_obj,
            "content_type",
            "application/octet-stream",
        )
        or "application/octet-stream"
    ).lower()

    file_size = getattr(
        file_obj,
        "size",
        0,
    )

    if file_size <= 0:
        raise StorageServiceError(
            "VALIDATION_ERROR",
            "فایل ارسالی خالی است.",
            400,
        )

    media_type = None
    max_size = None

    for candidate_type, rules in (
        MEDIA_UPLOAD_RULES.items()
    ):
        if content_type in rules["content_types"]:
            media_type = candidate_type
            max_size = rules["max_size"]
            break

    if media_type is None:
        raise StorageServiceError(
            "UNSUPPORTED_MEDIA_TYPE",
            "نوع فایل ارسالی پشتیبانی نمی‌شود.",
            400,
        )

    if file_size > max_size:
        max_size_mb = max_size // (
            1024 * 1024
        )

        raise StorageServiceError(
            "FILE_TOO_LARGE",
            (
                "حجم فایل بیشتر از حد مجاز "
                f"{max_size_mb} مگابایت است."
            ),
            400,
        )

    return {
        "media_type": media_type,
        "content_type": content_type,
        "size": file_size,
    }


@transaction.atomic
def create_media_attachment(
    owner,
    file_obj,
):
    validation = validate_media_file(
        file_obj
    )

    upload_result = upload_file(
        file_obj,
        filename=file_obj.name,
        folder=(
            f"media/{owner.public_id}/"
            f"{validation['media_type']}"
        ),
    )

    try:
        attachment = (
            MediaAttachment.objects.create(
                owner=owner,
                file_key=upload_result[
                    "file_key"
                ],
                file_url=upload_result[
                    "file_url"
                ],
                original_name=upload_result[
                    "filename"
                ],
                content_type=validation[
                    "content_type"
                ],
                size=validation["size"],
                media_type=validation[
                    "media_type"
                ],
            )
        )
    except Exception:
        try:
            delete_file(
                upload_result["file_key"]
            )
        except StorageServiceError:
            pass

        raise

    return attachment


def _get_media_attachment_or_404(
    media_id,
):
    try:
        return (
            MediaAttachment.objects
            .select_related(
                "owner",
                "message",
                "message__user",
                "message__receiver",
            )
            .get(public_id=media_id)
        )
    except MediaAttachment.DoesNotExist as exc:
        raise StorageServiceError(
            "NOT_FOUND",
            "فایل رسانه‌ای یافت نشد.",
            404,
        ) from exc


def _can_access_media(
    requester,
    attachment,
):
    message = attachment.message

    # فایل هنوز به پیامی متصل نشده است
    if message is None:
        return attachment.owner_id == requester.id

    # فایل پیام حذف‌شده قابل دریافت نیست
    if message.deleted_at is not None:
        return False

    if (
        message.message_type
        == Message.MessageType.DIRECT
    ):
        return requester.id in {
            message.user_id,
            message.receiver_id,
        }

    if (
        message.message_type
        == Message.MessageType.GROUP
    ):
        return GroupMembership.objects.filter(
            group__public_id=message.group_id,
            group__deleted_at__isnull=True,
            user=requester,
        ).exists()

    if (
        message.message_type
        == Message.MessageType.CHANNEL
    ):
        return ChannelMembership.objects.filter(
            channel__public_id=message.channel_id,
            channel__deleted_at__isnull=True,
            user=requester,
        ).exists()

    return False


def get_media_attachment(
    requester,
    media_id,
):
    attachment = (
        _get_media_attachment_or_404(
            media_id
        )
    )

    if not _can_access_media(
        requester,
        attachment,
    ):
        raise StorageServiceError(
            "FORBIDDEN",
            "شما اجازه دسترسی به این فایل را ندارید.",
            403,
        )

    return attachment


def get_media_download_url(
    requester,
    media_id,
):
    attachment = get_media_attachment(
        requester,
        media_id,
    )

    return (
        attachment,
        get_presigned_url(
            attachment.file_key
        ),
    )


@transaction.atomic
def delete_media_attachment(
    requester,
    media_id,
):
    attachment = (
        _get_media_attachment_or_404(
            media_id
        )
    )

    if attachment.owner_id != requester.id:
        raise StorageServiceError(
            "FORBIDDEN",
            "شما اجازه حذف این فایل را ندارید.",
            403,
        )

    if attachment.message_id is not None:
        raise StorageServiceError(
            "CONFLICT",
            "فایل متصل‌شده به پیام قابل حذف نیست.",
            409,
        )

    delete_file(
        attachment.file_key
    )

    attachment.delete()

    return True


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
    public_endpoint = getattr(settings, "MINIO_PUBLIC_ENDPOINT", None)
    if public_endpoint:
        protocol = "https" if settings.MINIO_USE_SSL else "http"
        client = get_s3_client(endpoint_url=f"{protocol}://{public_endpoint}")
    else:
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


def delete_replaced_avatar(user, old_avatar_url, new_avatar_url):
    old_avatar_url = (old_avatar_url or "").strip()
    new_avatar_url = (new_avatar_url or "").strip()

    if not old_avatar_url or old_avatar_url == new_avatar_url:
        return

    attachment = MediaAttachment.objects.filter(owner=user, file_url=old_avatar_url).first()
    if attachment:
        if attachment.message_id is None:
            try:
                delete_file(attachment.file_key)
            except Exception:
                pass
            attachment.delete()
    else:
        bucket = settings.MINIO_BUCKET_NAME
        if f"/{bucket}/" in old_avatar_url:
            file_key = old_avatar_url.split(f"/{bucket}/", 1)[-1]
            try:
                delete_file(file_key)
            except Exception:
                pass
