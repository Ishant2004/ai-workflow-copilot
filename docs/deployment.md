# Deployment (Docker → AWS ECS/Lambda + CI/CD)

How the Workflow AI Copilot ships: containerized services, built and deployed by
GitHub Actions to **Amazon ECS on Fargate**, fronted by an ALB.

## Topology

```
                 ┌────────────────────── AWS ──────────────────────┐
Internet ──ALB──►│  ECS service: frontend (Next.js, :3000)          │
           │     │  ECS service: api      (FastAPI, :8000) ──┐      │
           └────►│                                           │      │
                 │  ECS service: worker   (Celery)      ┌────┴────┐ │
                 │  ECS service: beat     (Celery Beat) │  RDS    │ │
                 │  one-off task: migrate (alembic)     │ Postgres│ │
                 │                                      └─────────┘ │
                 │  ElastiCache Redis  ·  Secrets Manager  ·  S3    │
                 └──────────────────────────────────────────────────┘
```

- **frontend** — Next.js standalone image (`frontend/Dockerfile`), served behind the ALB.
- **api** — FastAPI (`backend/Dockerfile` `prod` target), multiple Uvicorn workers, stateless → scales horizontally behind the ALB target group. `RUN_ASYNC=true` so it enqueues runs.
- **worker** — Celery worker; the compute for workflow runs. Scale replicas by queue depth.
- **beat** — Celery Beat; the cron dispatcher. **Exactly one** replica (`desiredCount: 1`) — it's the single scheduler (see [scalability.md](scalability.md)).
- **migrate** — a one-off Fargate task (`alembic upgrade head`) run by CI *before* services roll, so schema changes never race across replicas.
- **Postgres** = RDS (with the `vector` extension for pgvector); **Redis** = ElastiCache; large artifacts/uploads = **S3**.

Images are **ARM64** (Fargate Graviton — cheaper/faster); adjust `runtimePlatform` in the task defs for x86.

## Images

| Image | Dockerfile | Notes |
|-------|-----------|-------|
| backend | `backend/Dockerfile` (`--target prod`) | non-root, N Uvicorn workers; same image runs api/worker/beat/migrate via command overrides |
| frontend | `frontend/Dockerfile` | multi-stage → Next `output: "standalone"`, non-root; `NEXT_PUBLIC_API_BASE_URL` is a **build arg** (browser-facing, inlined at build) |

Build locally (when Docker is available):

```bash
docker build -t copilot-backend ./backend --target prod
docker build -t copilot-frontend ./frontend --build-arg NEXT_PUBLIC_API_BASE_URL=https://api.example.com
```

## CI/CD (GitHub Actions)

- **`.github/workflows/ci.yml`** — on every push/PR. Backend: ruff lint + format check, migrations apply, full `pytest` (unit + integration against a pgvector service container), and the **eval harness gate** (`python -m app.eval`). Frontend: eslint, vitest, production build. This is the quality gate.
- **`.github/workflows/deploy.yml`** — on push to `main` (or manual). Builds + pushes both images to ECR, runs the migration task, then rolls each ECS service to the new image and waits for stability.

The deploy workflow is **inert until you opt in**: it only runs when the repo variable `DEPLOY_ENABLED=true`. Auth uses GitHub OIDC assuming an AWS role (no long-lived keys).

### Required configuration

Repo **variables** (Settings → Variables):

| Variable | Example |
|----------|---------|
| `DEPLOY_ENABLED` | `true` |
| `AWS_REGION` | `ap-south-1` |
| `ECR_BACKEND_REPO` / `ECR_FRONTEND_REPO` | `copilot-backend` / `copilot-frontend` |
| `ECS_CLUSTER` | `copilot` |
| `ECS_SERVICE_API` / `_WORKER` / `_BEAT` / `_FRONTEND` | `copilot-api`, … |
| `ECS_SUBNETS` | `subnet-aaa,subnet-bbb` (private) |
| `ECS_SECURITY_GROUP` | `sg-xxxx` |
| `FRONTEND_API_BASE_URL` | `https://api.example.com` |

Repo **secret**: `AWS_DEPLOY_ROLE_ARN` — the IAM role Actions assumes via OIDC (ECR push + ECS deploy + `iam:PassRole` for the task/execution roles).

### Task definitions

Templates live in `deploy/ecs/*.json` (api, worker, beat, migrate, frontend). Replace the
`<AWS_ACCOUNT_ID>` / `<AWS_REGION>` placeholders and the Secrets Manager ARNs; CI injects
the image at deploy time via `amazon-ecs-render-task-definition`. Secrets
(`DATABASE_URL`, `REDIS_URL`, `ANTHROPIC_API_KEY`) are pulled from **Secrets Manager** —
never baked into images or task defs.

For production, set `LLM_PROVIDER=anthropic` and `TOOLS_PROVIDER=live` (the task defs
default `APP_ENV=production`, which also disables the interactive docs).

## One-time AWS setup (outline)

1. ECR repos: `copilot-backend`, `copilot-frontend`.
2. RDS Postgres (enable `vector`), ElastiCache Redis, S3 bucket.
3. Secrets Manager entries under `copilot/*`.
4. ECS cluster + ALB + target groups (api :8000, frontend :3000).
5. IAM: task execution role (pull ECR, read secrets, write logs), task role (S3, etc.), and the GitHub OIDC deploy role.
6. Create the ECS services referencing the task-def families; then pushes to `main` deploy automatically.

## Render (all-in-one, no AWS / no local Docker)

`render.yaml` (repo root) is a Render Blueprint that runs the entire stack — frontend,
API, worker (Celery worker + embedded beat via `-B`), managed Postgres (pgvector), and
Redis. Render builds the Dockerfiles in its own cloud, so nothing is built locally.

Deploy: Render Dashboard → **New → Blueprint** → select this repo → Apply. Then:

1. Set the **`ANTHROPIC_API_KEY`** secret on the `copilot-api` and `copilot-worker`
   services (or set `LLM_PROVIDER=fake`/`TOOLS_PROVIDER=fake` to run without a key).
2. Note the assigned URLs; if they differ from the defaults, update
   `NEXT_PUBLIC_API_BASE_URL` (frontend) and `CORS_ORIGINS` (api), then redeploy.

Notes: migrations run on API startup (`alembic upgrade head && uvicorn …`), so no
separate migrate step; the app normalizes the `postgresql://` URL Render provides to
the `postgresql+psycopg://` driver automatically (`app/config.py`); the worker is a
paid instance (Render requirement) and must stay at 1 replica because `-B` embeds the
scheduler. The same app runs unchanged on Railway, Fly.io, or a self-hosted PaaS
(Coolify/Dokploy) via `docker-compose.prod.yml`.

## Lambda alternative

The stateless **api** can instead run on **AWS Lambda** behind API Gateway/Lambda Function
URL via an ASGI adapter (e.g. Mangum) using the same image — good for spiky, low-baseline
traffic. The **worker** and **beat** are long-lived processes and stay on ECS (or move to
EventBridge Scheduler → SQS → Lambda consumers if you re-architect the queue). ECS Fargate
is the default here because it runs all four services with one image and one deploy path.
