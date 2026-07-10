from django.urls import path

from api.views import users


urlpatterns = [
    path("me", users.my_profile, name="users-me"),
    path("<str:user_id>", users.user_profile, name="users-detail"),
]