from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from api.services.storage import (
    StorageServiceError,
    create_media_attachment,
    delete_media_attachment,
    get_media_download_url,
)
from api.serializers import (
    MediaAttachmentSerializer,
)
from api.utils.responses import error_response, no_content_response, success_response


def _handle_storage_error(exc):
    return error_response(exc.code, exc.message, exc.status_code)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_media(request):
    if "file" not in request.FILES:
        return error_response(
            "VALIDATION_ERROR",
            "فایل جهت آپلود ارسال نشده است.",
            status.HTTP_400_BAD_REQUEST,
        )

    try:
        attachment = (
            create_media_attachment(
                request.user,
                request.FILES["file"],
            )
        )
    except StorageServiceError as exc:
        return _handle_storage_error(exc)

    return success_response(
        MediaAttachmentSerializer(
            attachment
        ).data,
        status.HTTP_201_CREATED,
    )


@api_view(["GET", "DELETE"])
@permission_classes([IsAuthenticated])
def file_detail(
    request,
    media_id,
):
    if request.method == "GET":
        try:
            attachment, url = (
                get_media_download_url(
                    request.user,
                    media_id,
                )
            )
        except StorageServiceError as exc:
            return _handle_storage_error(exc)

        return success_response(
            {
                "id": attachment.public_id,
                "filename":
                    attachment.original_name,
                "media_type":
                    attachment.media_type,
                "content_type":
                    attachment.content_type,
                "size": attachment.size,
                "presigned_url": url,
            }
        )

    try:
        delete_media_attachment(
            request.user,
            media_id,
        )
    except StorageServiceError as exc:
        return _handle_storage_error(exc)

    return no_content_response()