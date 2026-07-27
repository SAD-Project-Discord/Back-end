from django.urls import path

from api.views import messages, scheduled_messages, stickers

urlpatterns = [
    path("", messages.messages, name="messages"),
    path("scheduled/", scheduled_messages.scheduled_messages_list_create, name="scheduled-messages-list-create"),
    path("scheduled/<str:scheduled_id>/", scheduled_messages.scheduled_message_detail, name="scheduled-message-detail"),
    path("search", messages.search_message_list, name="messages-search"),
    path("search/global/", messages.global_search_view, name="messages-global-search"),
    path("direct/<str:user_id>", messages.direct_messages, name="messages-direct"),
    path("direct/<str:user_id>/search/", messages.search_direct_messages_view, name="messages-direct-search"),
    path("groups/<str:group_id>", messages.group_messages, name="messages-groups"),
    path("groups/<str:group_id>/search/", messages.search_group_messages_view, name="messages-groups-search"),
    path("channels/<str:channel_id>", messages.channel_messages, name="messages-channels"),
    path("channels/<str:channel_id>/search/", messages.search_channel_messages_view, name="messages-channels-search"),
    path("<str:message_id>", messages.message_detail, name="message-detail"),
    path("<str:message_id>/reactions/", stickers.add_reaction_view, name="message-reactions-add"),
    path("<str:message_id>/reactions/<str:reaction_id>/", stickers.remove_reaction_view, name="message-reactions-remove"),
]
