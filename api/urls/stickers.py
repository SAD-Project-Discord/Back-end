from django.urls import path
from api.views import stickers

urlpatterns = [
    path("packs/", stickers.sticker_packs_list, name="sticker-packs-list"),
    path("packs/<str:pack_id>/", stickers.sticker_pack_detail, name="sticker-pack-detail"),
]
