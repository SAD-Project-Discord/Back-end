import os

from .base import *  # noqa: F403
from .database import get_postgres_database

DEBUG = True

if not SECRET_KEY:  # noqa: F405
    SECRET_KEY = "django-insecure-dev-only-change-me"

if not ALLOWED_HOSTS:  # noqa: F405
    ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

if not CORS_ALLOWED_ORIGINS:  # noqa: F405
    CORS_ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

if os.getenv("DATABASE_URL") or os.getenv("DB_HOST"):  # noqa: F405
    DATABASES = {
        "default": get_postgres_database(
            default_sslmode="prefer",
            default_conn_max_age=0,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
        }
    }

REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [  # noqa: F405
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",
]

CELERY_TASK_ALWAYS_EAGER = os.getenv("CELERY_TASK_ALWAYS_EAGER", "True") == "True"
CELERY_TASK_EAGER_PROPAGATES = True
