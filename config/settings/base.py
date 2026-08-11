import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.getenv("SECRET_KEY", "")

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "daphne",
    "whitenoise.runserver_nostatic",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "channels",
    "api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

AUTH_USER_MODEL = "api.User"

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "USER_ID_FIELD": "public_id",
    "USER_ID_CLAIM": "sub",
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

REST_FRAMEWORK = {
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "api.authentication.SessionJWTAuthentication",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "EXCEPTION_HANDLER": "api.exception_handler.custom_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Discord-like Messaging API",
    "DESCRIPTION": """
# Discord-like Messaging System - REST API Documentation

Comprehensive REST API for Discord-like messaging application developed for **System Analysis and Design (SAD)** course project.

### Key Features & Subsystems
1. **Authentication & Session Management**: JWT access & refresh token pair rotation, multiple active device sessions management.
2. **Users & Contacts**: User search, user profiles, direct message contacts list, and granular privacy controls.
3. **Groups**: Group creation, membership management, direct member addition, invitation lifecycle, and custom permission roles.
4. **Channels & Topics**: Text/voice channels within servers/workspaces and topic sub-channels.
5. **Messages**: Direct, group, and channel messaging, reply hierarchy, pinning, search, and emoji/sticker reactions.
6. **Scheduled Messages**: Schedule messages to be automatically delivered at a future timestamp.
7. **Media Storage**: Attachment uploads to MinIO / S3 storage with presigned URLs and automatic avatar replacement lifecycle cleanup.
8. **Stickers**: Custom sticker packs and sticker reactions.

### Authorization
All protected endpoints require a JWT Bearer token in HTTP header:
`Authorization: Bearer <access_token>`
    """,
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "TAGS": [
        {"name": "Authentication", "description": "User registration, login, JWT token rotation, and active session management"},
        {"name": "Users & Contacts", "description": "Profile management, user search, contacts list, and privacy settings"},
        {"name": "Groups", "description": "Group creation, member management, and invitation workflows"},
        {"name": "Group Roles", "description": "Custom access roles and permission assignments for group members"},
        {"name": "Channels", "description": "Text/voice channels and topic sub-channels"},
        {"name": "Channel Memberships", "description": "Channel member management and role updates"},
        {"name": "Channel Roles", "description": "Custom access roles for channel members"},
        {"name": "Messages", "description": "Direct, group, and channel messaging, message editing, searching, and reactions"},
        {"name": "Scheduled Messages", "description": "Schedule messages for future delivery"},
        {"name": "Media Storage", "description": "File and image uploads to MinIO/S3 and presigned download URLs"},
        {"name": "Stickers", "description": "Sticker packs and sticker metadata"},
        {"name": "System Health", "description": "Server health status check"},
    ],
    "POSTPROCESSING_HOOKS": [
        "api.utils.schema.envelope_postprocessing_hook",
    ],
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
        "displayRequestDuration": True,
    },
}

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [os.getenv("CHANNEL_REDIS_URL", "redis://localhost:6379/1")],
        },
    },
}

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME", "discord-media")
MINIO_USE_SSL = os.getenv("MINIO_USE_SSL", "False").lower() in ("true", "1", "t")
MINIO_PUBLIC_ENDPOINT = os.getenv("MINIO_PUBLIC_ENDPOINT", "")
_default_public_url = f"http://{MINIO_PUBLIC_ENDPOINT or MINIO_ENDPOINT}/{MINIO_BUCKET_NAME}"
MINIO_PUBLIC_URL = os.getenv("MINIO_PUBLIC_URL", _default_public_url)
if not MINIO_PUBLIC_ENDPOINT and MINIO_PUBLIC_URL:
    from urllib.parse import urlparse
    parsed = urlparse(MINIO_PUBLIC_URL)
    if parsed.netloc:
        MINIO_PUBLIC_ENDPOINT = parsed.netloc

