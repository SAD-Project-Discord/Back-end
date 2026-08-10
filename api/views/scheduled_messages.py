from drf_spectacular.utils import OpenApiResponse, extend_schema
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


@extend_schema(
    tags=["Scheduled Messages"],
    summary="List scheduled messages",
    description="Returns all pending scheduled messages created by the authenticated user.",
    methods=["GET"],
    responses={200: ScheduledMessageSerializer(many=True)},
)
@extend_schema(
    tags=["Scheduled Messages"],
    summary="Schedule a message",
    description="Schedules a direct, group, or channel message to be automatically sent at `scheduled_at` timestamp.",
    methods=["POST"],
    request=CreateScheduledMessageSerializer,
    responses={
        201: ScheduledMessageSerializer,
        400: OpenApiResponse(description="Validation error or invalid schedule time."),
    },
)
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
            "Invalid data for scheduled message.",
            status.HTTP_400_BAD_REQUEST,
            serializer.errors,
        )

    try:
        scheduled_msg = create_scheduled_message(request.user, serializer.validated_data)
    except MessageServiceError as exc:
        return _handle_service_error(exc)

    return success_response(ScheduledMessageSerializer(scheduled_msg).data, status.HTTP_201_CREATED)


@extend_schema(
    tags=["Scheduled Messages"],
    summary="Cancel scheduled message",
    description="Cancels and deletes a pending scheduled message.",
    responses={
        204: OpenApiResponse(description="Scheduled message cancelled."),
        404: OpenApiResponse(description="Scheduled message not found."),
    },
)
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def scheduled_message_detail(request, scheduled_id):
    try:
        cancel_scheduled_message(request.user, scheduled_id)
    except MessageServiceError as exc:
        return _handle_service_error(exc)

    return no_content_response()
