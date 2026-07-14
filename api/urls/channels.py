from django.urls import path

from api.views import channels


urlpatterns = [
    path(
        "",
        channels.channel_list_create,
        name="channels",
    ),
    path(
        "<str:channel_id>/topics",
        channels.channel_topic_list_create,
        name="channel-topics",
    ),
    path(
        "<str:channel_id>/topics/<str:topic_id>",
        channels.channel_topic_detail,
        name="channel-topic-detail",
    ),
    path(
        "<str:channel_id>",
        channels.channel_detail,
        name="channel-detail",
    ),
]