#!/usr/bin/env bash
#
# Stop the local Workflow AI Copilot stack started by dev-local.sh.
#
# By default leaves Redis running (it's often a shared/brew-managed service).
#   --redis   also shut down the Redis started on COPILOT_REDIS_PORT
set -uo pipefail

STATE="${COPILOT_HOME:-$HOME/.copilot}"
PIDDIR="$STATE/pids"
PGDATA="$STATE/pgdata"
PG_BIN="${COPILOT_PG_BIN:-/opt/homebrew/opt/postgresql@17/bin}"
PG_PORT="${COPILOT_PG_PORT:-55432}"
REDIS_PORT="${COPILOT_REDIS_PORT:-6379}"

c_info() { printf '\033[1;36m▶ %s\033[0m\n' "$*"; }
c_ok()   { printf '\033[1;32m✓ %s\033[0m\n' "$*"; }

# Stop app processes (reverse of start order) via tracked PIDs.
for name in frontend beat worker api; do
  pidf="$PIDDIR/$name.pid"
  if [ -f "$pidf" ]; then
    pid="$(cat "$pidf")"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      c_ok "stopped $name (pid $pid)"
    fi
    rm -f "$pidf"
  fi
done

# Fallback: sweep any stragglers (e.g. Celery pool children, next dev's node).
pkill -f "uvicorn app.main:app" 2>/dev/null && c_info "swept uvicorn" || true
pkill -f "celery -A app.worker" 2>/dev/null && c_info "swept celery" || true
pkill -f "next dev" 2>/dev/null && c_info "swept next dev" || true

# Stop Postgres.
if "$PG_BIN/pg_ctl" -D "$PGDATA" status >/dev/null 2>&1; then
  "$PG_BIN/pg_ctl" -D "$PGDATA" stop >/dev/null 2>&1 && c_ok "stopped Postgres"
fi

# Redis only on request.
if [ "${1:-}" = "--redis" ]; then
  redis-cli -p "$REDIS_PORT" shutdown nosave >/dev/null 2>&1 && c_ok "stopped Redis" || true
else
  c_info "left Redis running (pass --redis to stop it)"
fi

c_ok "Done."
