import os
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured


def postgres_from_url(url: str, *, sslmode: str, conn_max_age: int) -> dict:
    parsed = urlparse(url)
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parsed.path.lstrip("/"),
        "USER": parsed.username or "",
        "PASSWORD": parsed.password or "",
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or 5432),
        "CONN_MAX_AGE": conn_max_age,
        "OPTIONS": {"sslmode": sslmode},
    }


def postgres_from_env(*, sslmode: str, conn_max_age: int) -> dict:
    required = ("DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST")
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise ImproperlyConfigured(
            f"Missing database settings: {', '.join(missing)}. "
            "Set DATABASE_URL or individual DB_* variables."
        )

    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["DB_NAME"],
        "USER": os.environ["DB_USER"],
        "PASSWORD": os.environ["DB_PASSWORD"],
        "HOST": os.environ["DB_HOST"],
        "PORT": os.getenv("DB_PORT", "5432"),
        "CONN_MAX_AGE": conn_max_age,
        "OPTIONS": {"sslmode": sslmode},
    }


def get_postgres_database(*, default_sslmode: str, default_conn_max_age: int) -> dict:
    sslmode = os.getenv("DB_SSLMODE", default_sslmode)
    conn_max_age = int(os.getenv("DB_CONN_MAX_AGE", str(default_conn_max_age)))
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        return postgres_from_url(
            database_url,
            sslmode=sslmode,
            conn_max_age=conn_max_age,
        )

    return postgres_from_env(sslmode=sslmode, conn_max_age=conn_max_age)
