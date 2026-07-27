from django.urls import path

from api.views import messages

urlpatterns = [
    path("", messages.messages, name="messages"),
    path("search", messages.search_message_list, name="messages-search"),
    path("search/global/", messages.global_search_view, name="messages-global-search"),
    path("direct/<str:user_id>", messages.direct_messages, name="messages-direct"),
    path("groups/<str:group_id>", messages.group_messages, name="messages-groups"),
    path("channels/<str:channel_id>", messages.channel_messages, name="messages-channels"),
    path("<str:message_id>", messages.message_detail, name="message-detail"),
]
