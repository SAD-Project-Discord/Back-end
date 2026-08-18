from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from api.serializers import (
    DirectConversationSerializer,
    EditMessageSerializer,
    MessageSerializer,
    SendMessageSerializer,
)
from api.services.messages import (
    MessageServiceError,
    create_message,
    delete_message,
    get_message,
    global_search_messages,
    list_channel_messages,
    list_direct_messages,
    list_group_messages,
    search_channel_messages,
    search_direct_messages,
    search_group_messages,
    search_messages,
    update_message,
    list_direct_conversations,
)
from api.utils.responses import error_response, no_content_response, success_response


def _handle_service_error(exc):
    return error_response(exc.code, exc.message, exc.status_code)


@extend_schema(
    tags=["Messages"],
    summary="Send a message",
    description="Sends a direct message, group message, or channel message. Supports attachments, reply_to, and stickers.",
    request=SendMessageSerializer,
    responses={
        201: MessageSerializer,
        400: OpenApiResponse(description="Validation error."),
        403: OpenApiResponse(description="Forbidden."),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def messages(request):
    serializer = SendMessageSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response(
            "VALIDATION_ERROR",
            "Invalid request data.",
            status.HTTP_400_BAD_REQUEST,
            serializer.errors,
        )
    try:
        message = create_message(request.user, serializer.validated_data)
    except MessageServiceError as exc:
        return _handle_service_error(exc)
    return success_response(MessageSerializer(message).data, status.HTTP_201_CREATED)


@extend_schema(
    tags=["Messages"],
    summary="List direct conversations",
    description=(
        "Returns one conversation per direct-message participant, "
        "ordered by the latest message."
    ),
    parameters=[
        OpenApiParameter(
            name="limit",
            description="Number of conversations to retrieve.",
            required=False,
            type=int,
        ),
        OpenApiParameter(
            name="cursor",
            description="Cursor for conversation pagination.",
            required=False,
            type=str,
        ),
    ],
    responses={
        200: DirectConversationSerializer(many=True),
        400: OpenApiResponse(
            description="Invalid cursor."
        ),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def direct_conversations(request):
    limit = request.query_params.get("limit", 50)
    cursor = request.query_params.get("cursor")

    try:
        conversations, meta = list_direct_conversations(
            request.user,
            limit=limit,
            cursor=cursor,
        )
    except MessageServiceError as exc:
        return _handle_service_error(exc)

    return success_response(
        DirectConversationSerializer(
            conversations,
            many=True,
        ).data,
        status.HTTP_200_OK,
        meta=meta,
    )


@extend_schema(
    tags=["Messages"],
    summary="List direct messages",
    description="Retrieves message history of direct conversation with a specific user.",
    parameters=[
        OpenApiParameter(name="limit", description="Number of messages to retrieve", required=False, type=int),
        OpenApiParameter(name="before", description="Cursor timestamp or message ID for pagination", required=False, type=str),
    ],
    responses={200: MessageSerializer(many=True)},
)
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


@extend_schema(
    tags=["Messages"],
    summary="List group messages",
    description="Retrieves message history of a group conversation.",
    parameters=[
        OpenApiParameter(name="limit", description="Number of messages to retrieve", required=False, type=int),
        OpenApiParameter(name="before", description="Cursor for pagination", required=False, type=str),
    ],
    responses={200: MessageSerializer(many=True)},
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


@extend_schema(
    tags=["Messages"],
    summary="List channel messages",
    description="Retrieves message history in a channel or specific channel topic.",
    parameters=[
        OpenApiParameter(name="limit", description="Number of messages to retrieve", required=False, type=int),
        OpenApiParameter(name="before", description="Cursor for pagination", required=False, type=str),
        OpenApiParameter(name="topic_id", description="Filter messages by topic ID", required=False, type=str),
    ],
    responses={200: MessageSerializer(many=True)},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def channel_messages(request, channel_id):
    limit = request.query_params.get(
        "limit",
        50,
    )
    before = request.query_params.get(
        "before"
    )
    topic_id = request.query_params.get(
        "topic_id"
    )

    try:
        messages_list, has_more = (
            list_channel_messages(
                request.user,
                channel_id,
                topic_id,
                limit,
                before,
            )
        )
    except MessageServiceError as exc:
        return _handle_service_error(exc)

    return success_response(
        MessageSerializer(
            messages_list,
            many=True,
        ).data,
        meta={
            "limit": int(limit),
            "has_more": has_more,
        },
    )


@extend_schema(
    tags=["Messages"],
    summary="Search user messages",
    description="Searches all accessible messages for a search query string `q`.",
    parameters=[
        OpenApiParameter(name="q", description="Query string to search", required=True, type=str),
        OpenApiParameter(name="limit", description="Limit of search results", required=False, type=int),
    ],
    responses={200: MessageSerializer(many=True), 400: OpenApiResponse(description="Query parameter 'q' is required.")},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def search_message_list(request):
    query = request.query_params.get("q", "").strip()
    limit = request.query_params.get("limit", 20)
    if not query:
        return error_response("VALIDATION_ERROR", "Parameter q is required.", status.HTTP_400_BAD_REQUEST)

    messages_list, has_more, meta = search_messages(request.user, query, limit)
    meta["has_more"] = has_more
    return success_response(MessageSerializer(messages_list, many=True).data, meta=meta)


@extend_schema(
    tags=["Messages"],
    summary="Global search messages",
    description="Global search across all conversations with advanced filters (message_type, from_user, date_from, date_to).",
    parameters=[
        OpenApiParameter(name="q", description="Search query string", required=False, type=str),
        OpenApiParameter(name="message_type", description="Filter by direct, group, or channel", required=False, type=str),
        OpenApiParameter(name="from_user", description="Filter by sender user public ID", required=False, type=str),
        OpenApiParameter(name="date_from", description="Filter starting date (YYYY-MM-DD)", required=False, type=str),
        OpenApiParameter(name="date_to", description="Filter ending date (YYYY-MM-DD)", required=False, type=str),
        OpenApiParameter(name="limit", description="Result limit", required=False, type=int),
        OpenApiParameter(name="before", description="Cursor for pagination", required=False, type=str),
    ],
    responses={200: MessageSerializer(many=True)},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def global_search_view(request):
    query = request.query_params.get("q", "").strip()
    message_type = request.query_params.get("message_type")
    from_user = request.query_params.get("from_user")
    date_from = request.query_params.get("date_from")
    date_to = request.query_params.get("date_to")
    limit = request.query_params.get("limit", 20)
    before = request.query_params.get("before")

    try:
        messages_list, has_more, meta = global_search_messages(
            request.user,
            query,
            message_type=message_type,
            from_user_id=from_user,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            before=before,
        )
    except MessageServiceError as exc:
        return _handle_service_error(exc)

    return success_response(MessageSerializer(messages_list, many=True).data, meta=meta)


@extend_schema(
    tags=["Messages"],
    summary="Get, edit, or delete message",
    description="GET: Retrieves a single message.\nPATCH: Edits message content.\nDELETE: Soft-deletes a message.",
    methods=["GET"],
    responses={200: MessageSerializer, 404: OpenApiResponse(description="Message not found.")},
)
@extend_schema(
    tags=["Messages"],
    summary="Edit message content",
    description="Edits text content of a message sent by current user.",
    methods=["PATCH"],
    request=EditMessageSerializer,
    responses={200: MessageSerializer, 400: OpenApiResponse(description="Validation error."), 403: OpenApiResponse(description="Forbidden.")},
)
@extend_schema(
    tags=["Messages"],
    summary="Delete message",
    description="Deletes a message.",
    methods=["DELETE"],
    responses={204: OpenApiResponse(description="Message deleted successfully."), 403: OpenApiResponse(description="Forbidden.")},
)
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
                "Invalid request data.",
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


@extend_schema(
    tags=["Messages"],
    summary="Search direct messages",
    description="Searches text inside direct messages exchanged with a specific user.",
    parameters=[
        OpenApiParameter(name="q", description="Query string", required=False, type=str),
        OpenApiParameter(name="limit", description="Limit", required=False, type=int),
        OpenApiParameter(name="before", description="Cursor", required=False, type=str),
    ],
    responses={200: MessageSerializer(many=True)},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def search_direct_messages_view(request, user_id):
    query = request.query_params.get("q", "")
    limit = request.query_params.get("limit", 20)
    before = request.query_params.get("before")
    try:
        messages_list, has_more = search_direct_messages(request.user, user_id, query, limit, before)
    except MessageServiceError as exc:
        return _handle_service_error(exc)

    return success_response(
        MessageSerializer(messages_list, many=True).data,
        meta={"limit": int(limit), "has_more": has_more},
    )


@extend_schema(
    tags=["Messages"],
    summary="Search group messages",
    description="Searches text inside group messages.",
    parameters=[
        OpenApiParameter(name="q", description="Query string", required=False, type=str),
        OpenApiParameter(name="limit", description="Limit", required=False, type=int),
        OpenApiParameter(name="before", description="Cursor", required=False, type=str),
    ],
    responses={200: MessageSerializer(many=True)},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def search_group_messages_view(request, group_id):
    query = request.query_params.get("q", "")
    limit = request.query_params.get("limit", 20)
    before = request.query_params.get("before")
    try:
        messages_list, has_more = search_group_messages(request.user, group_id, query, limit, before)
    except MessageServiceError as exc:
        return _handle_service_error(exc)

    return success_response(
        MessageSerializer(messages_list, many=True).data,
        meta={"limit": int(limit), "has_more": has_more},
    )


@extend_schema(
    tags=["Messages"],
    summary="Search channel messages",
    description="Searches text inside channel messages or specific topic.",
    parameters=[
        OpenApiParameter(name="q", description="Query string", required=False, type=str),
        OpenApiParameter(name="limit", description="Limit", required=False, type=int),
        OpenApiParameter(name="before", description="Cursor", required=False, type=str),
        OpenApiParameter(name="topic_id", description="Topic ID", required=False, type=str),
    ],
    responses={200: MessageSerializer(many=True)},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def search_channel_messages_view(request, channel_id):
    query = request.query_params.get("q", "")
    limit = request.query_params.get("limit", 20)
    before = request.query_params.get("before")
    topic_id = request.query_params.get("topic_id")
    try:
        messages_list, has_more = search_channel_messages(request.user, channel_id, topic_id, query, limit, before)
    except MessageServiceError as exc:
        return _handle_service_error(exc)

    return success_response(
        MessageSerializer(messages_list, many=True).data,
        meta={"limit": int(limit), "has_more": has_more},
    )
