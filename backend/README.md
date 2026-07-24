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
├── llm/               # planner: Claude integration behind a swappable interface
│   ├── base.py        # Planner ABC + PlannerError
│   ├── schemas.py     # WorkflowPlan / PlannedStep (structured output)
│   ├── prompts.py     # system prompt + forced tool schema
│   ├── anthropic_planner.py  # Claude (async, config-driven, concurrency-capped)
│   ├── fake_planner.py       # deterministic, offline (dev/tests)
│   └── factory.py     # get_planner(settings)
├── tools/             # step execution behind a Tool interface + registry
│   ├── base.py        # Tool ABC + ToolError
│   ├── fake.py        # deterministic web_search / summarize / notify (default)
│   ├── summarize.py   # ClaudeSummarizeTool (live provider example)
│   ├── notify.py      # LiveSlackNotifyTool (webhook) + LiveEmailNotifyTool (SMTP)
│   └── registry.py    # build_tool_registry(settings)
├── execution/
│   └── executor.py    # WorkflowExecutor: runs steps → Run + StepResults
├── worker/            # Celery: async run execution + cron scheduling
│   ├── celery_app.py  # Celery app + beat schedule
│   ├── tasks.py       # execute_run, dispatch_due_workflows
│   └── scheduling.py  # cron is_due / due_workflows / dispatch_due (pure)
├── rag/               # RAG: embeddings, chunking, extraction, ingest/search
│   ├── embeddings.py  # Embedder interface + HashingEmbedder (offline default)
│   ├── chunking.py    # overlapping character chunker
│   ├── extract.py     # text/PDF → plain text
│   ├── retriever.py   # DocumentRetriever: query → chunks (grounds workflows)
│   └── service.py     # ingest_document / search_documents
├── schemas/           # API DTOs (WorkflowCreate/Update/Out, RunOut, ...)
├── services/          # pure plan/DTO → ORM mapping (DB-free, unit-tested)
├── repositories/      # WorkflowRepository interface + SQLAlchemy impl
└── api/routes/
    ├── health.py      # /health, /health/live, /health/ready
    ├── planner.py     # POST /api/planner/preview
    ├── workflows.py   # /api/workflows CRUD + /{id}/runs
    └── runs.py        # GET /api/runs/{id}
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

## Planner (Claude integration)

Turns a plain-English task into a structured, typed workflow plan using Claude's
**tool use** (forced `emit_workflow_plan` tool → validated against `WorkflowPlan`).
The provider is isolated behind the `Planner` interface (ADR-002) and swappable:

- `LLM_PROVIDER=anthropic` (default) — real Claude; needs `ANTHROPIC_API_KEY`.
- `LLM_PROVIDER=fake` — deterministic, offline; the dev/test default (no key).

Model, max tokens, timeout, retries, and max concurrency are all config values
(no magic numbers). The concurrency cap bounds in-flight LLM calls per process.

```bash
curl -s -X POST http://localhost:8000/api/planner/preview \
  -H 'Content-Type: application/json' \
  -d '{"task_description":"Every morning collect AI startup news, summarize it, and Slack me a digest"}'
```

Returns a `WorkflowPlan` (title, summary, ordered typed steps). No persistence yet
— that's Step 6. Returns **503** if no provider is configured, **502** if the model
fails to produce a valid plan.

## Workflows API

Persists planner output as `Workflow` + ordered `Step` rows and exposes CRUD +
read-only run history. Storage sits behind a `WorkflowRepository` interface, so
routes are fully tested offline with an in-memory fake (no DB needed).

| Method | Path | Purpose |
| ------ | ---- | ------- |
| POST   | `/api/workflows` | Create from a task (runs planner) or a supplied plan |
| GET    | `/api/workflows` | List (paginated: `limit`≤`api_max_page_size`, `offset`) |
| GET    | `/api/workflows/{id}` | Fetch one (with steps) |
| PATCH  | `/api/workflows/{id}` | Update title/description/status; optionally replace steps |
| DELETE | `/api/workflows/{id}` | Delete (cascades to steps & runs) |
| GET    | `/api/workflows/{id}/runs` | List run history for a workflow |
| POST   | `/api/workflows/{id}/runs` | **Execute** the workflow now; persist the run |
| GET    | `/api/runs/{id}` | Fetch a run with its step results |
| PATCH  | `/api/runs/{id}/steps/{step_result_id}` | Edit a step's output during review |
| POST   | `/api/runs/{id}/approve` | Approve a paused run → run remaining steps |
| POST   | `/api/runs/{id}/reject` | Reject a paused run (no side effects) |

```bash
# Create and persist a workflow from a plain-English task
curl -s -X POST http://localhost:8000/api/workflows \
  -H 'Content-Type: application/json' \
  -d '{"task_description":"Every morning collect AI startup news and Slack me a digest"}'
```

Run creation/execution lands in later steps; the run endpoints return history
(empty until then). Integration tests exercise the real Postgres-backed
repository and auto-skip when no `DATABASE_URL` is reachable.

## Tool execution

`POST /api/workflows/{id}/runs` executes a workflow's steps in order — each step's
output is threaded into a shared context for downstream steps (search → summarize →
notify) — and persists a `Run` with one `StepResult` per step (output/error + timings).

Tools sit behind a `Tool` interface + registry, selected by `TOOLS_PROVIDER`:

- `fake` (default) — deterministic, offline tools; no keys/network. Great for dev/tests.
- `live` — real providers where configured (e.g. the Claude summarizer with a key),
  falling back to fake for anything not yet wired.

Each tool call is bounded by `TOOL_TIMEOUT_SECONDS`; a failing step stops the run and
marks it `failed`. Execution is synchronous for now — Step 12 moves it onto a queue.

### Human-in-the-loop review

With `REQUIRE_REVIEW=true` (default), a run **pauses at `awaiting_review`** before the
first side-effecting step (Slack/email). The produced result can be edited
(`PATCH …/steps/{id}`), then **approved** (resumes and runs the remaining steps,
using any edits) or **rejected** (cancels with no side effects). This enforces the
"nothing side-effecting runs without review" principle.

### Output actions (Slack / email)

The `notify_slack` / `notify_email` steps deliver the reviewed summary. Under
`TOOLS_PROVIDER=live`:

- **Slack** — set `SLACK_WEBHOOK_URL` (incoming webhook); the tool POSTs the message.
- **Email** — set `SMTP_HOST` + `EMAIL_FROM` (and `SMTP_USER`/`SMTP_PASSWORD` if the
  server requires auth); the tool sends via SMTP (STARTTLS).

Anything not configured falls back to the simulated notifier, so a run still
completes. These run only *after* approval, so nothing is sent without review.
Keep webhook URLs and SMTP passwords in `.env` (git-ignored), never in tracked files.

## RAG (documents + pgvector)

Upload a document → text is extracted (text/PDF), chunked, embedded, and stored in
a pgvector column; search embeds the query and returns the nearest chunks by cosine
similarity. The embedder is swappable (`EMBEDDING_PROVIDER`); the default is a
deterministic offline hashing embedder so retrieval works with no API key.

| Method | Path | Purpose |
| ------ | ---- | ------- |
| POST   | `/api/documents` | Upload a file (multipart) → chunk + embed + store |
| GET    | `/api/documents` | List documents (paginated) |
| GET/DELETE | `/api/documents/{id}` | Fetch / delete a document |
| POST   | `/api/documents/search` | Semantic search → nearest chunks with scores |

```bash
curl -s -X POST http://localhost:8000/api/documents -F 'file=@notes.txt'
curl -s -X POST http://localhost:8000/api/documents/search \
  -H 'Content-Type: application/json' -d '{"query":"payment terms","top_k":5}'
```

Search is **exact** cosine (sequential scan) — correct at MVP scale; an approximate
index (HNSW) is the scale upgrade.

### Grounding workflows (retrieve step)

A `retrieve` step type queries the document store during a run and threads the
matching chunks into the execution context; the `summarize` step then grounds its
output on them (alongside any `web_search` results). The retriever is built per run
from the request/worker DB session + embedder and passed to the executor — so a
workflow can answer from your uploaded documents, not just the open web.

## Queue & scheduling (Celery + Redis)

With `RUN_ASYNC=true`, `POST /runs` enqueues a Celery task and returns a **pending**
run (202); a worker executes it off the request path and updates the run (poll
`GET /api/runs/{id}`). Default (`false`) executes inline (201).

Workflows with `status=active` and a `schedule_cron` are fired by **Celery Beat**:
a dispatcher runs every `BEAT_DISPATCH_INTERVAL_SECONDS`, finds due workflows
(via cron), creates a run, and enqueues it. This covers the "every morning" use case.

```bash
# worker (executes runs)
celery -A app.worker.celery_app worker -Q copilot --loglevel=info
# beat (fires schedules)
celery -A app.worker.celery_app beat --loglevel=info
```

`docker compose up` starts `worker` and `beat` alongside the API (with
`RUN_ASYNC=true`). For tests/simple dev, `CELERY_TASK_ALWAYS_EAGER=true` runs tasks
inline without a worker.

## Reliability & observability

**Retries with backoff.** A step that fails transiently is retried up to
`STEP_MAX_RETRIES` times with exponential backoff (`STEP_RETRY_BACKOFF_SECONDS`,
`2**attempt`). Timeouts and generic tool errors are treated as transient; a
`ToolError(..., retryable=False)` (e.g. a missing required config field — a bug that
won't fix itself) fails immediately without wasting retries. Only after retries are
exhausted is the step (and run) marked `failed`.

**Structured logging.** Logs are single-line JSON (`app/logging_config.py`). Every
line carries a `request_id`; logs emitted while a run executes also carry its
`run_id`, and step logs add `step` / `step_type` / `attempt` — so a run can be traced
end-to-end and filtered by step in aggregation. Any `logger.*(..., extra={...})`
fields are merged into the JSON.

**Consistent error responses.** Any unhandled exception escaping a route is logged
with its traceback (correlated by `request_id`) and returned to the client as a
uniform `500 {"detail": "Internal server error"}` — internals never leak, in any
environment (this holds even with `debug=true`, since it's enforced in
`RequestIDMiddleware`, not only the app error handler). Expected errors keep their
existing shapes (`404`/`502` still use FastAPI's `{"detail": ...}`).

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
