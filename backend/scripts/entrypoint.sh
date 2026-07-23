#!/usr/bin/env sh
# Container entrypoint: apply DB migrations, then exec the given command (the server).
# Idempotent — safe to run on every boot / every replica (alembic no-ops if up to date).
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting: $*"
exec "$@"
