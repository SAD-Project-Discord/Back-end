from django.urls import path

from api.views import auth

urlpatterns = [
    path("register", auth.register, name="auth-register"),
    path("login", auth.login, name="auth-login"),
]
