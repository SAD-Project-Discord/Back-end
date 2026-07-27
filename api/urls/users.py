from django.urls import path

from api.views import users


urlpatterns = [
    path("me", users.my_profile, name="users-me"),
    path("me/privacy/", users.user_privacy_view, name="users-me-privacy"),
    path("<str:user_id>", users.user_profile, name="users-detail"),
]