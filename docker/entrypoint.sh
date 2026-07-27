#!/bin/sh
set -e

python manage.py collectstatic --noinput --clear || true

echo "Waiting for database..."
python - <<'PY'
import os
import sys
import time

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.db import connection
from django.db.utils import OperationalError

django.setup()

for attempt in range(30):
    try:
        connection.ensure_connection()
        break
    except OperationalError:
        if attempt == 29:
            sys.exit("Database unavailable after 60 seconds")
        time.sleep(2)
PY

python manage.py migrate --noinput
exec "$@"
