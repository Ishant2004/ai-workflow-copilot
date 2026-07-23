# Backend — Workflow AI Copilot

FastAPI service. Stateless and config-driven so it scales horizontally (see
[../docs/scalability.md](../docs/scalability.md)).

## Layout

```
app/
├── main.py            # create_app() factory; opens/closes DB pool in lifespan
├── config.py          # Pydantic settings; APP_ENV selects the dotenv layer
├── dependencies.py    # DI: per-instance settings from app.state
├── logging_config.py  # structured JSON logging + request-id context
├── middleware.py      # X-Request-ID correlation middleware
├── health_checks.py   # concurrent, timeout-bounded Postgres/Redis probes
├── db/
│   ├── base.py        # DeclarativeBase + UUID/Timestamp mixins
│   └── session.py     # async engine (pool sized from config) + get_db dependency
├── models/            # Workflow, Step, Run, StepResult + enums
└── api/routes/
    └── health.py      # /health, /health/live, /health/ready
migrations/            # Alembic env + versioned migrations
tests/
├── conftest.py        # shared fixtures (client, settings, prod_client)
├── unit/              # fast, no external deps
└── integration/       # require running infra (added in later steps)
Dockerfile             # multi-stage: base → dev / prod targets
pyproject.toml         # ruff lint/format config
```

## Database & migrations

Models (SQLAlchemy 2.0, async): `Workflow` → `Step` (the plan) and `Run` →
`StepResult` (each execution, for history/observability). Connection pool size,
overflow, timeout, and recycle are all in config — no magic numbers.

```bash
# Apply migrations (needs Postgres running; Docker does this automatically)
alembic upgrade head

# Preview the SQL without a database
alembic upgrade head --sql

# After changing models, generate a migration
alembic revision --autogenerate -m "describe change"
```

In Docker: **dev** applies migrations via the container entrypoint; **prod** runs a
separate one-off `migrate` service the backend waits on (avoids multi-replica races).

## Lint & format

```bash
ruff check .        # lint
ruff check --fix .  # autofix
ruff format .       # format
```

## Environment separation

Config layers load lowest-priority first:

```
.env                 # shared / local defaults
.env.<APP_ENV>       # per-environment overrides (.env.development committed; prod injected)
real env vars        # highest priority (Docker/ECS/CI)
```

`APP_ENV` (`development` | `staging` | `production`) picks the overlay. In
**production**, interactive docs/OpenAPI are disabled and the container runs as a
non-root user with multiple workers.

- Dev defaults: [.env.development](.env.development) (committed, secret-free)
- Prod template: [.env.production.example](.env.production.example) (copy → inject real secrets out-of-repo)

## Run with Docker Compose (recommended)

```bash
# Dev: hot reload, Postgres+pgvector, Redis (auto-loads docker-compose.override.yml)
docker compose up --build
```

- API docs: http://localhost:8000/docs
- Readiness (checks DB + Redis): http://localhost:8000/health/ready

```bash
# Prod-like: built image, 4 workers, non-root, no reload
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## Run without Docker

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Scale out (independent, stateless processes):

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Test

```bash
source .venv/bin/activate
pytest              # all
pytest -m unit      # fast unit tests only
```

## Notes

- **Python 3.12–3.14** supported (deps pinned to versions with 3.14 wheels;
  Docker image pins 3.12).
- **Probes:** `/health` (identity), `/health/live` (liveness), `/health/ready`
  (readiness — returns 503 if a *configured* dependency is unreachable).
- **Config:** all via env vars — see [.env.example](.env.example).
