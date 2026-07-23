# syntax=docker/dockerfile:1

# ---------- base: shared deps ----------
FROM python:3.12-slim AS base
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
COPY scripts ./scripts
RUN chmod +x scripts/entrypoint.sh

# ---------- dev: hot reload, source mounted via compose ----------
FROM base AS dev
ENV APP_ENV=development
# entrypoint applies migrations (single dev replica → no race), then runs the server.
ENTRYPOINT ["./scripts/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ---------- prod: multiple workers, non-root, no reload ----------
FROM base AS prod
ENV APP_ENV=production
# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 appuser
USER appuser
# Worker count is overridable via UVICORN_WORKERS in the platform.
ENV UVICORN_WORKERS=4
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS}"]
