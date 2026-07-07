from django.urls import include, path

from api.views import health

urlpatterns = [
    path("health/", health.health_check, name="health-check"),
    path("auth/", include("api.urls.auth")),
]
