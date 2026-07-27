from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from api.serializers import CreateScheduledMessageSerializer, ScheduledMessageSerializer
from api.services.messages import MessageServiceError
from api.services.scheduled_messages import (
    cancel_scheduled_message,
    create_scheduled_message,
    list_scheduled_messages,
)
from api.utils.responses import error_response, no_content_response, success_response


def _handle_service_error(exc):
    return error_response(exc.code, exc.message, exc.status_code)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def scheduled_messages_list_create(request):
    if request.method == "GET":
        items = list_scheduled_messages(request.user)
        return success_response(ScheduledMessageSerializer(items, many=True).data)

    serializer = CreateScheduledMessageSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response(
            "VALIDATION_ERROR",
            "اطلاعات ارسالی برای زمان‌بندی پیام نامعتبر است.",
            status.HTTP_400_BAD_REQUEST,
            serializer.errors,
        )

    try:
        scheduled_msg = create_scheduled_message(request.user, serializer.validated_data)
    except MessageServiceError as exc:
        return _handle_service_error(exc)

    return success_response(ScheduledMessageSerializer(scheduled_msg).data, status.HTTP_201_CREATED)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def scheduled_message_detail(request, scheduled_id):
    try:
        cancel_scheduled_message(request.user, scheduled_id)
    except MessageServiceError as exc:
        return _handle_service_error(exc)

    return no_content_response()
