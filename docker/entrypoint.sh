#!/bin/sh
# MANSA — container entrypoint.
# 1. Ensure the DB exists at $MANSA_DB (creates schema on first boot).
# 2. Optionally seed from app.html if SEED_ON_STARTUP=1.
# 3. Exec the CMD (gunicorn by default).

set -eu

DB="${MANSA_DB:-/data/mansa.db}"

if [ ! -f "$DB" ]; then
    echo "[entrypoint] $DB not found — initializing schema"
    python /app/server/db_init.py
    if [ "${SEED_ON_STARTUP:-0}" = "1" ]; then
        echo "[entrypoint] seeding from frontend/app.html"
        python /app/scripts/seed_from_app_html.py --db "$DB" || echo "[entrypoint] seed failed (continuing)"
    fi
else
    echo "[entrypoint] using existing $DB"
fi

# Sanity: required secrets must exist in production.
if [ "${FLASK_ENV:-production}" != "development" ]; then
    : "${MANSA_SECRET:?MANSA_SECRET must be set (>= 32 chars)}"
    : "${MANSA_ADMIN_TOKEN:?MANSA_ADMIN_TOKEN must be set (>= 32 chars)}"
    : "${MANSA_ALLOWED_ORIGINS:?MANSA_ALLOWED_ORIGINS must be set}"
fi

exec "$@"
