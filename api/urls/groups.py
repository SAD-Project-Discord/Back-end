from django.urls import path

from api.views import groups


urlpatterns = [
    path(
        "",
        groups.group_list_create,
        name="groups",
    ),
    path(
        "invitations",
        groups.received_group_invitations,
        name="group-invitations",
    ),
    path(
        "invitations/<str:invitation_id>/respond",
        groups.group_invitation_respond,
        name="group-invitation-respond",
    ),
    path(
        "<str:group_id>/invitations",
        groups.group_invitation_create,
        name="group-invitation-create",
    ),
    path(
        "<str:group_id>",
        groups.group_detail,
        name="group-detail",
    ),
]