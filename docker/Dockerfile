# MANSA — Production image (Python 3.13 slim)
# Multi-stage:
#   1. `builder` installs dependencies into a virtualenv.
#   2. `runtime` copies the venv + app, runs gunicorn as non-root user.
#
# Build:
#   docker build -t mansa:latest -f docker/Dockerfile .
# Run:
#   docker run --rm -p 5000:5000 \
#     -e MANSA_SECRET=$(python -c "import secrets;print(secrets.token_urlsafe(48))") \
#     -e MANSA_ADMIN_TOKEN=$(python -c "import secrets;print(secrets.token_urlsafe(32))") \
#     -e MANSA_ALLOWED_ORIGINS=https://mansa.finance \
#     mansa:latest

# ── Stage 1: builder ─────────────────────────────────────────────────────
FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Build deps for argon2-cffi, lxml.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libffi-dev libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY server/requirements.txt server/requirements-dev.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.txt gunicorn

# ── Stage 2: runtime ─────────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/server \
    FLASK_ENV=production

# Runtime deps only (libxml2 for lxml, libffi for argon2-cffi).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libxml2 libxslt1.1 libffi8 tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r mansa && useradd -r -g mansa -u 1000 mansa \
    && mkdir -p /app /data /app/server/logs \
    && chown -R mansa:mansa /app /data

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=mansa:mansa server/ /app/server/
COPY --chown=mansa:mansa scripts/ /app/scripts/
COPY --chown=mansa:mansa frontend/ /app/frontend/
COPY --chown=mansa:mansa docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

USER mansa

# DB lives on a mounted volume so it survives container rebuilds.
ENV MANSA_DB=/data/mansa.db
VOLUME ["/data"]

EXPOSE 5000

# tini reaps zombies and forwards SIGTERM to gunicorn for graceful shutdown.
ENTRYPOINT ["/usr/bin/tini", "--", "/app/entrypoint.sh"]
CMD ["gunicorn", \
     "--workers", "4", \
     "--threads", "2", \
     "--bind", "0.0.0.0:5000", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--timeout", "60", \
     "--graceful-timeout", "30", \
     "api_server:app"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/api/health',timeout=3).status==200 else 1)" \
        || exit 1
