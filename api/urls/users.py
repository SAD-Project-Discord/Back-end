from django.urls import path

from api.views import users


urlpatterns = [
    path("me", users.my_profile, name="users-me"),
    path("me/", users.my_profile, name="users-me-slash"),
    path("me/privacy/", users.user_privacy_view, name="users-me-privacy"),
    path("me/privacy", users.user_privacy_view, name="users-me-privacy-noslash"),
    path("me/settings/", users.user_privacy_view, name="users-me-settings"),
    path("me/settings", users.user_privacy_view, name="users-me-settings-noslash"),
    path("search/", users.user_search, name="users-search"),
    path("search", users.user_search, name="users-search-noslash"),
    path("contacts/", users.user_contacts_view, name="users-contacts"),
    path("contacts", users.user_contacts_view, name="users-contacts-noslash"),
    path("contacts/<str:user_id>", users.user_contact_detail_view, name="users-contact-detail-noslash"),
    path("contacts/<str:user_id>/", users.user_contact_detail_view, name="users-contact-detail"),
    path("<str:user_id>", users.user_profile, name="users-detail"),
    path("<str:user_id>/", users.user_profile, name="users-detail-slash"),
]