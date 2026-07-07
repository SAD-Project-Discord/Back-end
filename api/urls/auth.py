from django.urls import path

from api.views import auth

urlpatterns = [
    path("register", auth.register, name="auth-register"),
    path("login", auth.login, name="auth-login"),
    path("refresh", auth.refresh, name="auth-refresh"),
    path("logout", auth.logout, name="auth-logout"),
    path("logout-all", auth.logout_all, name="auth-logout-all"),
    path("sessions", auth.list_sessions, name="auth-sessions"),
    path("sessions/<str:session_id>", auth.delete_session, name="auth-delete-session"),
]
