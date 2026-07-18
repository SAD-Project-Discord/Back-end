from django.urls import path

from api.views import (
    channel_memberships,
    channel_roles,
    channels,
)


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
        "<str:channel_id>/members",
        channel_memberships.channel_member_list_create,
        name="channel-members",
    ),
    path(
        "<str:channel_id>/members/me",
        channel_memberships.channel_leave,
        name="channel-leave",
    ),
    path(
        "<str:channel_id>/members/<str:user_id>/roles",
        channel_roles.channel_member_role_assign,
        name="channel-member-role-assign",
    ),
    path(
        "<str:channel_id>/members/<str:user_id>/roles/<str:role_id>",
        channel_roles.channel_member_role_remove,
        name="channel-member-role-remove",
    ),
    path(
        "<str:channel_id>/members/<str:user_id>",
        channel_memberships.channel_member_detail,
        name="channel-member-detail",
    ),
    path(
        "<str:channel_id>/roles",
        channel_roles.channel_role_list_create,
        name="channel-roles",
    ),
    path(
        "<str:channel_id>/roles/<str:role_id>",
        channel_roles.channel_role_detail,
        name="channel-role-detail",
    ),
    path(
        "<str:channel_id>",
        channels.channel_detail,
        name="channel-detail",
    ),
]