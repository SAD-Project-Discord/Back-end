from django.urls import include, path

from api.views import health

urlpatterns = [
    path("health/", health.health_check, name="health-check"),
    path("auth/", include("api.urls.auth")),
    path("messages/", include("api.urls.messages")),
    path("users/", include("api.urls.users")),
    path("groups/", include("api.urls.groups")),
    path("channels/", include("api.urls.channels")),
    path("storage/", include("api.urls.storage")),
    path("stickers/", include("api.urls.stickers")),
]
