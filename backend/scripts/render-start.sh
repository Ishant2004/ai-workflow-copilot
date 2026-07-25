#!/bin/sh
# Render API start: apply migrations, then run the server on Render's $PORT.
# Kept as a script so there's no shell-quoting ambiguity in render.yaml's dockerCommand.
set -e
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers "${UVICORN_WORKERS:-2}"
