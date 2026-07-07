from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from api.models import AuthSession, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("email",)
    list_display = ("email", "username", "name", "provider", "is_active", "created_at")
    search_fields = ("email", "username", "name", "public_id")
    readonly_fields = ("public_id", "created_at", "updated_at", "last_login")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("username", "name", "bio", "profile_picture", "provider")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Metadata", {"fields": ("public_id", "deleted_at", "created_at", "updated_at", "last_login")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "username", "name", "password1", "password2"),
            },
        ),
    )


@admin.register(AuthSession)
class AuthSessionAdmin(admin.ModelAdmin):
    list_display = ("public_id", "user", "device", "created_at", "expires_at", "revoked_at")
    search_fields = ("public_id", "user__email", "user__username", "device")
    readonly_fields = ("public_id", "refresh_jti", "created_at")
    list_filter = ("revoked_at",)
