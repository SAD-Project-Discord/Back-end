from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from api.serializers import (
    MediaAttachmentSerializer,
)
from api.services.storage import (
    StorageServiceError,
    create_media_attachment,
    delete_media_attachment,
    get_media_download_url,
)
from api.utils.responses import error_response, no_content_response, success_response


def _handle_storage_error(exc):
    return error_response(exc.code, exc.message, exc.status_code)


@extend_schema(
    tags=["Media Storage"],
    summary="Upload media file",
    description="Uploads an image, video, audio, or document file to S3/MinIO storage as multipart/form-data (`file` field). Returns attachment details and S3 URL.",
    responses={
        201: MediaAttachmentSerializer,
        400: OpenApiResponse(description="No file uploaded or unsupported media type / file size limit exceeded."),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_media(request):
    if "file" not in request.FILES:
        return error_response(
            "VALIDATION_ERROR",
            "No file provided for upload.",
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


@extend_schema(
    tags=["Media Storage"],
    summary="Get presigned download URL or delete media file",
    description="GET: Generates a presigned S3 download URL for an uploaded file.\nDELETE: Deletes an unattached file from storage.",
    methods=["GET"],
    responses={
        200: OpenApiResponse(description="Presigned URL generated successfully."),
        403: OpenApiResponse(description="Forbidden."),
        404: OpenApiResponse(description="File not found."),
    },
)
@extend_schema(
    tags=["Media Storage"],
    summary="Delete media file",
    description="Deletes an unattached media file from storage.",
    methods=["DELETE"],
    responses={
        204: OpenApiResponse(description="File deleted successfully."),
        403: OpenApiResponse(description="Forbidden."),
        409: OpenApiResponse(description="Cannot delete file attached to a message."),
    },
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