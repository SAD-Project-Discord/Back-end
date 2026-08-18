from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from api.serializers import (
    ChannelSerializer,
    CreateChannelSerializer,
    CreateTopicSerializer,
    TopicSerializer,
    UpdateChannelSerializer,
    UpdateTopicSerializer,
)
from api.services.channels import (
    ChannelServiceError,
    create_channel,
    create_topic,
    delete_channel,
    delete_topic,
    get_channel,
    get_channel_topic,
    join_channel,
    list_channel_topics,
    list_channels,
    list_public_channels,
    update_channel,
    update_topic,
)
from api.utils.responses import (
    error_response,
    no_content_response,
    success_response,
)


def _handle_service_error(exc):
    return error_response(
        exc.code,
        exc.message,
        exc.status_code,
    )


@extend_schema(
    tags=["Channels"],
    summary="List channels",
    description="Lists all channels accessible to the authenticated user.",
    methods=["GET"],
    responses={200: ChannelSerializer(many=True)},
)
@extend_schema(
    tags=["Channels"],
    summary="Create channel",
    description="Creates a new text or voice channel.",
    methods=["POST"],
    request=CreateChannelSerializer,
    responses={
        201: ChannelSerializer,
        400: OpenApiResponse(description="Validation error."),
    },
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def channel_list_create(request):
    if request.method == "GET":
        channels = list_channels(
            request.user
        )

        return success_response(
            ChannelSerializer(
                channels,
                many=True,
            ).data
        )

    serializer = CreateChannelSerializer(
        data=request.data
    )

    if not serializer.is_valid():
        return error_response(
            "VALIDATION_ERROR",
            "Invalid request data.",
            status.HTTP_400_BAD_REQUEST,
            serializer.errors,
        )

    channel = create_channel(
        request.user,
        serializer.validated_data,
    )

    return success_response(
        ChannelSerializer(channel).data,
        status.HTTP_201_CREATED,
    )


@extend_schema(
    tags=["Channels"],
    summary="Get channel detail",
    description="Returns detailed information about a specific channel.",
    methods=["GET"],
    responses={200: ChannelSerializer, 404: OpenApiResponse(description="Channel not found.")},
)
@extend_schema(
    tags=["Channels"],
    summary="Update channel",
    description="Updates channel name or details.",
    methods=["PATCH"],
    request=UpdateChannelSerializer,
    responses={200: ChannelSerializer, 400: OpenApiResponse(description="Validation error."), 403: OpenApiResponse(description="Forbidden.")},
)
@extend_schema(
    tags=["Channels"],
    summary="Delete channel",
    description="Deletes a channel.",
    methods=["DELETE"],
    responses={204: OpenApiResponse(description="Channel deleted successfully."), 403: OpenApiResponse(description="Forbidden.")},
)
@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def channel_detail(request, channel_id):
    if request.method == "GET":
        try:
            channel = get_channel(
                channel_id,
                request.user,
            )
        except ChannelServiceError as exc:
            return _handle_service_error(exc)

        return success_response(
            ChannelSerializer(channel).data
        )

    if request.method == "PATCH":
        serializer = UpdateChannelSerializer(
            data=request.data
        )

        if not serializer.is_valid():
            return error_response(
                "VALIDATION_ERROR",
                "Invalid request data.",
                status.HTTP_400_BAD_REQUEST,
                serializer.errors,
            )

        try:
            channel = update_channel(
                channel_id,
                request.user,
                serializer.validated_data,
            )
        except ChannelServiceError as exc:
            return _handle_service_error(exc)

        return success_response(
            ChannelSerializer(channel).data
        )

    try:
        delete_channel(
            channel_id,
            request.user,
        )
    except ChannelServiceError as exc:
        return _handle_service_error(exc)

    return no_content_response()


@extend_schema(
    tags=["Channels"],
    summary="List topics in channel",
    description="Lists all sub-topics created within a channel.",
    methods=["GET"],
    responses={200: TopicSerializer(many=True)},
)
@extend_schema(
    tags=["Channels"],
    summary="Create topic in channel",
    description="Creates a new topic in the channel.",
    methods=["POST"],
    request=CreateTopicSerializer,
    responses={201: TopicSerializer, 400: OpenApiResponse(description="Validation error.")},
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def channel_topic_list_create(request, channel_id):
    if request.method == "GET":
        try:
            topics = list_channel_topics(
                channel_id,
                request.user,
            )
        except ChannelServiceError as exc:
            return _handle_service_error(exc)

        return success_response(
            TopicSerializer(
                topics,
                many=True,
            ).data
        )

    serializer = CreateTopicSerializer(
        data=request.data
    )

    if not serializer.is_valid():
        return error_response(
            "VALIDATION_ERROR",
            "Invalid request data.",
            status.HTTP_400_BAD_REQUEST,
            serializer.errors,
        )

    try:
        topic = create_topic(
            channel_id,
            request.user,
            serializer.validated_data,
        )
    except ChannelServiceError as exc:
        return _handle_service_error(exc)

    return success_response(
        TopicSerializer(topic).data,
        status.HTTP_201_CREATED,
    )


@extend_schema(
    tags=["Channels"],
    summary="Get topic details",
    description="Retrieves topic details by channel ID and topic ID.",
    methods=["GET"],
    responses={200: TopicSerializer, 404: OpenApiResponse(description="Topic not found.")},
)
@extend_schema(
    tags=["Channels"],
    summary="Update topic",
    description="Updates topic details.",
    methods=["PATCH"],
    request=UpdateTopicSerializer,
    responses={200: TopicSerializer, 400: OpenApiResponse(description="Validation error.")},
)
@extend_schema(
    tags=["Channels"],
    summary="Delete topic",
    description="Deletes a topic from the channel.",
    methods=["DELETE"],
    responses={204: OpenApiResponse(description="Topic deleted successfully.")},
)
@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def channel_topic_detail(
    request,
    channel_id,
    topic_id,
):
    if request.method == "GET":
        try:
            topic = get_channel_topic(
                channel_id,
                topic_id,
                request.user,
            )
        except ChannelServiceError as exc:
            return _handle_service_error(exc)

        return success_response(
            TopicSerializer(topic).data
        )

    if request.method == "PATCH":
        serializer = UpdateTopicSerializer(
            data=request.data
        )

        if not serializer.is_valid():
            return error_response(
                "VALIDATION_ERROR",
                "Invalid request data.",
                status.HTTP_400_BAD_REQUEST,
                serializer.errors,
            )

        try:
            topic = update_topic(
                channel_id,
                topic_id,
                request.user,
                serializer.validated_data,
            )
        except ChannelServiceError as exc:
            return _handle_service_error(exc)

        return success_response(
            TopicSerializer(topic).data
        )

    try:
        delete_topic(
            channel_id,
            topic_id,
            request.user,
        )
    except ChannelServiceError as exc:
        return _handle_service_error(exc)

    return no_content_response()


@extend_schema(
    tags=["Channels"],
    summary="List public channels",
    description="Lists public channels matching search query q, excluding channels the user has already joined.",
    parameters=[
        OpenApiParameter(name="q", description="Filter channels by search query", required=False, type=str),
    ],
    responses={200: ChannelSerializer(many=True)},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def channel_public_list(request):
    query = request.query_params.get("q", "")
    channels_list = list_public_channels(query=query, requester=request.user)
    return success_response(ChannelSerializer(channels_list, many=True).data)


@extend_schema(
    tags=["Channels"],
    summary="Join public channel",
    description="Self-service join for a public channel (no invitation needed).",
    request=None,
    responses={
        200: ChannelSerializer,
        403: OpenApiResponse(description="Channel is private."),
        404: OpenApiResponse(description="Channel not found."),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def channel_join(request, channel_id):
    try:
        channel = join_channel(channel_id, request.user)
    except ChannelServiceError as exc:
        return _handle_service_error(exc)

    return success_response(ChannelSerializer(channel).data)