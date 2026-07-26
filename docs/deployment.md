# Deployment

The app is deployed **free on [Render](https://render.com)** from a single Blueprint
([`render.yaml`](../render.yaml)). Render builds the Dockerfiles in its own cloud, so
you deploy straight from GitHub — no local Docker, no paid worker, no cloud account to
manage.

## Topology (Render free tier)

```
                     ┌──────────────── Render ────────────────┐
Browser ────────────►│  Web service: copilot-frontend (Next.js)│
   │                 │                                         │
   └── /api, /health ┼─► Web service: copilot-api (FastAPI) ───┼─► Managed Postgres
                     │        └ migrations on start            │    (pgvector)
                     └─────────────────────────────────────────┘
   cron-job.org ──POST /api/scheduler/tick──► (fires due scheduled workflows)
```

- **copilot-frontend** — Next.js standalone image ([`frontend/Dockerfile`](../frontend/Dockerfile)).
- **copilot-api** — FastAPI ([`backend/Dockerfile`](../backend/Dockerfile), `prod` target). On
  start it runs `alembic upgrade head` then serves ([`scripts/render-start.sh`](../backend/scripts/render-start.sh)).
- **copilot-db** — Render managed Postgres; the app enables the `vector` extension in its
  first migration.
- **Runs execute inline** (`RUN_ASYNC=false`) — no Celery worker or Redis needed on the
  free tier.
- **Scheduling** is worker-free: an external cron pokes `/api/scheduler/tick` (below).

## Deploy it

1. **Render → New → Blueprint** → pick this repo → **Apply**. It creates the three
   resources above (all free plans).
2. Set secrets on **copilot-api → Environment** (all optional — each falls back to an
   offline fake if unset; see the capability table in the [root README](../README.md)):
   - `ANTHROPIC_API_KEY` — real planning / summarizing / multi-agent
   - `OPENAI_API_KEY` — real RAG embeddings
   - `TAVILY_API_KEY` — real web search
   - `SLACK_WEBHOOK_URL`, `SMTP_HOST` / `EMAIL_FROM` (+ `SMTP_USER` / `SMTP_PASSWORD`) — real delivery
   - `SCHEDULER_TOKEN` — enable the scheduler tick (Render can generate it)
3. If Render's assigned URLs differ from the defaults, update
   `NEXT_PUBLIC_API_BASE_URL` (frontend, build-time) and `CORS_ORIGINS` (api), then redeploy.

`git push` to `main` triggers Render's auto-deploy for each service.

## Images

| Image | Dockerfile | Notes |
|-------|-----------|-------|
| backend | `backend/Dockerfile` (`--target prod`) | non-root, N Uvicorn workers; one image also serves the (optional) Celery worker/beat via command overrides |
| frontend | `frontend/Dockerfile` | multi-stage → Next `output: "standalone"`, non-root; `NEXT_PUBLIC_API_BASE_URL` is a build arg (browser-facing, inlined at build) |

The app normalizes the `postgresql://…` URL managed hosts hand out to the
`postgresql+psycopg://` driver (`app/config.py`), so Render / Neon / Railway / Supabase
Postgres all work unchanged.

## Scheduling without a worker (free)

Celery Beat needs an always-on (usually paid) process. Instead, the API exposes
`POST /api/scheduler/tick` — it runs the same "find due scheduled workflows → execute
them" logic inline, driven by an external cron. No worker or Redis.

1. Set `SCHEDULER_TOKEN` (a long random secret) on the API. Unset → the endpoint is
   disabled (503).
2. Point a **free scheduler** at it, passing `window_seconds` equal to the cron interval
   so each occurrence fires exactly once:
   ```bash
   curl -X POST "https://<api-url>/api/scheduler/tick?window_seconds=60" \
     -H "X-Scheduler-Token: <SCHEDULER_TOKEN>"
   ```
   - **cron-job.org / UptimeRobot** — free, precise; 1-min interval → `window_seconds=60` (recommended).
   - **GitHub Actions** — [`.github/workflows/scheduler.yml`](../.github/workflows/scheduler.yml)
     is ready; set repo vars `SCHEDULER_ENABLED=true` + `SCHEDULER_URL` and secret `SCHEDULER_TOKEN`.

Scheduled runs execute unattended (no review gate). Pinging every minute also keeps the
free API instance warm (no cold-start).

## CI

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs on every push/PR: backend
ruff lint + format check, migrations apply, full `pytest` (unit + integration against a
pgvector service container), and the eval/grounding gate; frontend eslint + vitest +
production build. It's the quality gate — it does not deploy (Render auto-deploys on push).

## Free tier trade-offs

- Free web services **cold-start** after ~15 min idle (a scheduler ping keeps the API warm).
- Free Postgres **expires after ~90 days** — bump the plan for anything long-lived.
- The **async run queue** (Celery worker) and **Redis** are not deployed; runs execute
  inline. To enable them, run the full stack elsewhere (any Docker host / VM via
  `docker-compose.prod.yml`) or add a paid Render worker + Redis, and set `RUN_ASYNC=true`.

## Other platforms

Because it's plain containers + Postgres, the same app runs on Railway, Fly.io, Koyeb, or
a self-hosted PaaS (Coolify / Dokploy) via `docker-compose.prod.yml`. For blob storage,
any S3-compatible provider (Cloudflare R2, Backblaze B2) works once storage is wired in.
