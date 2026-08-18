from django.urls import path

from api.views import invites

urlpatterns = [
    path(
        "<str:token>",
        invites.invite_link_preview,
        name="invite-link-preview-noslash",
    ),
    path(
        "<str:token>/",
        invites.invite_link_preview,
        name="invite-link-preview",
    ),
    path(
        "<str:token>/join",
        invites.invite_link_join,
        name="invite-link-join-noslash",
    ),
    path(
        "<str:token>/join/",
        invites.invite_link_join,
        name="invite-link-join",
    ),
]
