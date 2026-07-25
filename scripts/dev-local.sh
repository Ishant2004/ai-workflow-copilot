#!/usr/bin/env bash
#
# Start the whole Workflow AI Copilot stack locally, no Docker:
#   Postgres 17 (+pgvector) · Redis · migrations · API · Celery worker · Beat · frontend
#
# Usage:   ./scripts/dev-local.sh
# Stop:    ./scripts/dev-local-stop.sh
# Logs:    ~/.copilot/logs/*.log   (override base dir with COPILOT_HOME)
#
# Everything below is configurable via env vars (no magic numbers baked in):
#   COPILOT_HOME, COPILOT_PG_BIN, COPILOT_PG_PORT, COPILOT_REDIS_PORT,
#   COPILOT_API_PORT, COPILOT_FRONTEND_PORT
set -euo pipefail

# --- paths ---
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
# Runtime state lives outside the repo (repo path has a space, which Postgres dislikes).
STATE="${COPILOT_HOME:-$HOME/.copilot}"
LOGDIR="$STATE/logs"
PIDDIR="$STATE/pids"
PGDATA="$STATE/pgdata"

# --- config (override via env) ---
PG_BIN="${COPILOT_PG_BIN:-/opt/homebrew/opt/postgresql@17/bin}"
PG_PORT="${COPILOT_PG_PORT:-55432}"
PG_USER="${COPILOT_PG_USER:-copilot}"
PG_DB="${COPILOT_PG_DB:-copilot}"
REDIS_PORT="${COPILOT_REDIS_PORT:-6379}"
API_HOST="127.0.0.1"
API_PORT="${COPILOT_API_PORT:-8000}"
FRONTEND_PORT="${COPILOT_FRONTEND_PORT:-3000}"

# macOS: Postgres needs a real UTF-8 locale in the environment or the postmaster
# aborts with "postmaster became multithreaded during startup".
export LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
# App env: this makes backend/.env authoritative (no tracked .env.<env> overlay).
export APP_ENV=local

mkdir -p "$LOGDIR" "$PIDDIR"

c_info() { printf '\033[1;36m▶ %s\033[0m\n' "$*"; }
c_ok()   { printf '\033[1;32m✓ %s\033[0m\n' "$*"; }
c_warn() { printf '\033[1;33m! %s\033[0m\n' "$*"; }
c_err()  { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; }

# --- preflight ---
[ -x "$BACKEND/.venv/bin/python" ] || {
  c_err "Backend venv missing. Create it first:"
  echo "    cd \"$BACKEND\" && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
}
[ -x "$PG_BIN/pg_ctl" ] || { c_err "Postgres 17 not found at $PG_BIN (override with COPILOT_PG_BIN)"; exit 1; }
command -v redis-server >/dev/null || { c_err "redis-server not on PATH (brew install redis)"; exit 1; }
command -v npm >/dev/null || { c_err "npm not on PATH"; exit 1; }

# --- 1. Postgres ---
if [ ! -f "$PGDATA/PG_VERSION" ]; then
  c_info "Initializing Postgres data dir at $PGDATA"
  "$PG_BIN/initdb" -D "$PGDATA" -U "$PG_USER" --encoding=UTF8 --locale=en_US.UTF-8 \
    >"$LOGDIR/pg-init.log" 2>&1
fi
if "$PG_BIN/pg_isready" -p "$PG_PORT" -q 2>/dev/null; then
  c_ok "Postgres already running on :$PG_PORT"
else
  c_info "Starting Postgres on :$PG_PORT"
  "$PG_BIN/pg_ctl" -D "$PGDATA" -o "-p $PG_PORT" -l "$LOGDIR/postgres.log" start >/dev/null
  for _ in $(seq 1 30); do "$PG_BIN/pg_isready" -p "$PG_PORT" -q 2>/dev/null && break; sleep 0.5; done
  "$PG_BIN/pg_isready" -p "$PG_PORT" -q || { c_err "Postgres failed to start; see $LOGDIR/postgres.log"; exit 1; }
  c_ok "Postgres up"
fi
if ! "$PG_BIN/psql" -p "$PG_PORT" -U "$PG_USER" -d postgres -tAc \
     "SELECT 1 FROM pg_database WHERE datname='$PG_DB'" | grep -q 1; then
  c_info "Creating database '$PG_DB' (UTF8)"
  "$PG_BIN/createdb" -p "$PG_PORT" -U "$PG_USER" -E UTF8 -T template0 "$PG_DB"
fi
"$PG_BIN/psql" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" -c "CREATE EXTENSION IF NOT EXISTS vector;" >/dev/null
c_ok "Database '$PG_DB' ready (pgvector enabled)"

# --- 2. Redis ---
if redis-cli -p "$REDIS_PORT" ping >/dev/null 2>&1; then
  c_ok "Redis already running on :$REDIS_PORT"
else
  c_info "Starting Redis on :$REDIS_PORT"
  redis-server --daemonize yes --port "$REDIS_PORT" --save '' >"$LOGDIR/redis.log" 2>&1
  sleep 1
  redis-cli -p "$REDIS_PORT" ping >/dev/null 2>&1 || { c_err "Redis failed to start"; exit 1; }
  c_ok "Redis up"
fi

# --- 3. backend/.env (created once if missing) ---
if [ ! -f "$BACKEND/.env" ]; then
  c_info "Writing $BACKEND/.env (offline fake providers)"
  cat > "$BACKEND/.env" <<EOF
APP_ENV=local
LOG_LEVEL=INFO
DEBUG=true
CORS_ORIGINS=http://localhost:$FRONTEND_PORT

DATABASE_URL=postgresql+psycopg://$PG_USER:$PG_USER@localhost:$PG_PORT/$PG_DB
REDIS_URL=redis://localhost:$REDIS_PORT/0

LLM_PROVIDER=fake
TOOLS_PROVIDER=fake
EMBEDDING_PROVIDER=fake

RUN_ASYNC=true
EOF
fi

# --- 4. Migrations ---
c_info "Applying database migrations"
( cd "$BACKEND" && .venv/bin/alembic upgrade head >>"$LOGDIR/migrate.log" 2>&1 )
c_ok "Migrations applied (see $LOGDIR/migrate.log)"

# --- 5. Frontend deps (installed once if missing) ---
if [ ! -d "$FRONTEND/node_modules" ]; then
  c_info "Installing frontend dependencies (first run)"
  ( cd "$FRONTEND" && npm install >"$LOGDIR/npm-install.log" 2>&1 )
fi

# --- 6. Long-running processes ---
# start_bg <name> <workdir> <logfile> <command...>
start_bg() {
  local name="$1" dir="$2" logf="$3"; shift 3
  local pidf="$PIDDIR/$name.pid"
  if [ -f "$pidf" ] && kill -0 "$(cat "$pidf")" 2>/dev/null; then
    c_warn "$name already running (pid $(cat "$pidf")) — skipping"
    return
  fi
  ( cd "$dir" && exec "$@" ) >"$logf" 2>&1 &
  echo $! > "$pidf"
  c_ok "$name started (pid $(cat "$pidf"))"
}

start_bg api      "$BACKEND"  "$LOGDIR/api.log" \
  .venv/bin/uvicorn app.main:app --host "$API_HOST" --port "$API_PORT" --reload
start_bg worker   "$BACKEND"  "$LOGDIR/worker.log" \
  .venv/bin/celery -A app.worker.celery_app worker --loglevel=info -Q copilot
start_bg beat     "$BACKEND"  "$LOGDIR/beat.log" \
  .venv/bin/celery -A app.worker.celery_app beat --loglevel=info
start_bg frontend "$FRONTEND" "$LOGDIR/frontend.log" \
  npm run dev

# --- 7. Wait for the API to report ready (pg + redis reachable) ---
c_info "Waiting for the API to become ready..."
ready=""
for _ in $(seq 1 40); do
  if curl -fsS "http://$API_HOST:$API_PORT/health/ready" >/dev/null 2>&1; then ready=1; break; fi
  sleep 0.5
done
if [ -n "$ready" ]; then
  c_ok "API ready"
else
  c_warn "API not ready yet — check $LOGDIR/api.log"
fi

echo
c_ok "Stack is up:"
echo "    UI          http://localhost:$FRONTEND_PORT/workflows"
echo "    API docs    http://localhost:$API_PORT/docs"
echo "    Readiness   http://localhost:$API_PORT/health/ready"
echo "    Logs        $LOGDIR/"
echo "    Stop        ./scripts/dev-local-stop.sh"
