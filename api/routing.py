from django.urls import path

from api.consumers import MessageConsumer

websocket_urlpatterns = [
    path("ws/v1/messages/", MessageConsumer.as_asgi()),
]
