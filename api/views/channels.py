from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from api.serializers import (
    ChannelSerializer,
    CreateChannelSerializer,
    CreateTopicSerializer,
    TopicSerializer,
    UpdateTopicSerializer,
    UpdateChannelSerializer,
)
from api.services.channels import (
    ChannelServiceError,
    create_channel,
    create_topic,
    delete_channel,
    delete_topic,
    get_channel,
    get_channel_topic,
    list_channel_topics,
    list_channels,
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
            "اطلاعات ارسالی نامعتبر است.",
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
                "اطلاعات ارسالی نامعتبر است.",
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
            "اطلاعات ارسالی نامعتبر است.",
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
                "اطلاعات ارسالی نامعتبر است.",
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