from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from api.serializers import EditMessageSerializer, MessageSerializer, SendMessageSerializer
from api.services.messages import (
    MessageServiceError,
    create_message,
    delete_message,
    get_message,
    list_channel_messages,
    list_direct_messages,
    list_group_messages,
    search_messages,
    update_message,
)
from api.utils.responses import error_response, no_content_response, success_response


def _handle_service_error(exc):
    return error_response(exc.code, exc.message, exc.status_code)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def messages(request):
    serializer = SendMessageSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response(
            "VALIDATION_ERROR",
            "اطلاعات ارسالی نامعتبر است.",
            status.HTTP_400_BAD_REQUEST,
            serializer.errors,
        )
    try:
        message = create_message(request.user, serializer.validated_data)
    except MessageServiceError as exc:
        return _handle_service_error(exc)
    return success_response(MessageSerializer(message).data, status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def direct_messages(request, user_id):
    limit = request.query_params.get("limit", 50)
    before = request.query_params.get("before")
    try:
        messages_list, has_more = list_direct_messages(request.user, user_id, limit, before)
    except MessageServiceError as exc:
        return _handle_service_error(exc)

    return success_response(
        MessageSerializer(messages_list, many=True).data,
        status.HTTP_200_OK,
        meta={"limit": int(limit), "has_more": has_more},
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def group_messages(request, group_id):
    limit = request.query_params.get("limit", 50)
    before = request.query_params.get("before")
    messages_list, has_more = list_group_messages(group_id, limit, before)
    return success_response(
        MessageSerializer(messages_list, many=True).data,
        meta={"limit": int(limit), "has_more": has_more},
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def channel_messages(request, channel_id):
    limit = request.query_params.get("limit", 50)
    before = request.query_params.get("before")
    topic_id = request.query_params.get("topic_id")
    messages_list, has_more = list_channel_messages(channel_id, topic_id, limit, before)
    return success_response(
        MessageSerializer(messages_list, many=True).data,
        meta={"limit": int(limit), "has_more": has_more},
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def search_message_list(request):
    query = request.query_params.get("q", "").strip()
    limit = request.query_params.get("limit", 20)
    if not query:
        return error_response("VALIDATION_ERROR", "پارامتر q الزامی است.", status.HTTP_400_BAD_REQUEST)

    messages_list, has_more, meta = search_messages(request.user, query, limit)
    meta["has_more"] = has_more
    return success_response(MessageSerializer(messages_list, many=True).data, meta=meta)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def message_detail(request, message_id):
    try:
        message = get_message(
            message_id,
            request.user,
        )
    except MessageServiceError as exc:
        return _handle_service_error(exc)

    if request.method == "GET":
        return success_response(MessageSerializer(message).data)

    if request.method == "PATCH":
        serializer = EditMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                "VALIDATION_ERROR",
                "اطلاعات ارسالی نامعتبر است.",
                status.HTTP_400_BAD_REQUEST,
                serializer.errors,
            )
        try:
            message = update_message(message, request.user, serializer.validated_data["content"])
        except MessageServiceError as exc:
            return _handle_service_error(exc)
        return success_response(MessageSerializer(message).data)

    try:
        delete_message(message, request.user)
    except MessageServiceError as exc:
        return _handle_service_error(exc)
    return no_content_response()
