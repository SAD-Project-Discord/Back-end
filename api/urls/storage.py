from django.urls import path
from api.views import storage

urlpatterns = [
    path("upload/", storage.upload_media, name="storage-upload"),
    path(
        "files/<str:media_id>/",
        storage.file_detail,
        name="storage-file-detail",
    ),
]
