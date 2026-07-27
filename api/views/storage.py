from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from api.services.storage import (
    StorageServiceError,
    delete_file,
    get_presigned_url,
    upload_file,
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

    file_obj = request.FILES["file"]
    folder = request.data.get("folder", "uploads")
    try:
        result = upload_file(file_obj, filename=file_obj.name, folder=folder)
    except StorageServiceError as exc:
        return _handle_storage_error(exc)

    return success_response(result, status.HTTP_201_CREATED)


@api_view(["GET", "DELETE"])
@permission_classes([IsAuthenticated])
def file_detail(request, file_key):
    if request.method == "GET":
        try:
            url = get_presigned_url(file_key)
        except StorageServiceError as exc:
            return _handle_storage_error(exc)
        return success_response({"file_key": file_key, "presigned_url": url})

    try:
        delete_file(file_key)
    except StorageServiceError as exc:
        return _handle_storage_error(exc)

    return no_content_response()
