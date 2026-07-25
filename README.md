# Workflow AI Copilot

Describe a repetitive task in plain English. The copilot understands your intent,
breaks it into a multi-step workflow, executes parts of it, and learns from your
feedback.

> _"Every morning, collect the latest AI startup news, summarize it, and send me a
> digest on Slack."_ → a runnable, reviewable workflow.

---

## What it does

1. **Understand intent** — parse a plain-English task into a structured goal.
2. **Plan** — break the goal into ordered, typed steps (search, summarize, notify…).
3. **Execute** — run steps using tools (web search, scraping, summarization, Slack/email).
4. **Review** — let the user approve, edit, or reject each result.
5. **Schedule** — trigger workflows on a schedule or on demand.
6. **Learn** — improve future suggestions from feedback.

## Tech stack

| Layer        | Technology                          |
| ------------ | ----------------------------------- |
| Frontend     | Next.js + Tailwind CSS              |
| Backend      | FastAPI (Python)                    |
| LLM          | Anthropic Claude                    |
| Vector DB    | pgvector (Postgres extension)       |
| Queue        | Redis + Celery                      |
| Storage      | PostgreSQL + S3                     |
| Deployment   | Docker → AWS ECS / Lambda           |

See [docs/decisions.md](docs/decisions.md) for why each choice was made.

## Repository layout

```
.
├── backend/     # FastAPI service (API, LLM orchestration, workers)
├── frontend/    # Next.js + Tailwind web app
├── docs/        # Architecture, roadmap, mind map, decision records
└── task.md      # Original project brief
```

## Documentation

- [Roadmap](docs/roadmap.md) — the step-by-step build plan (we commit after each step).
- [Architecture](docs/architecture.md) — system design and data flow.
- [Scalability](docs/scalability.md) — per-component scaling strategy (a design constraint, not an afterthought).
- [Deployment](docs/deployment.md) — Docker images, AWS ECS/Fargate topology, and the CI/CD pipeline.
- [Mind map](docs/mind-map.md) — how the concepts connect.
- [Decision records](docs/decisions.md) — key technical choices and their rationale.

## Deployment & CI/CD

Both apps are containerized (`backend/Dockerfile`, `frontend/Dockerfile`). GitHub
Actions runs the full quality gate on every push ([ci.yml](.github/workflows/ci.yml):
lint, tests incl. pgvector integration, and the eval/grounding gate) and deploys to
**AWS ECS on Fargate** on merges to `main` ([deploy.yml](.github/workflows/deploy.yml)
→ ECR + ECS, migrations as a one-off task). See [docs/deployment.md](docs/deployment.md).

## Status

✅ All 20 roadmap steps complete — see the [roadmap](docs/roadmap.md). The system runs
end-to-end locally (`./scripts/dev-local.sh`) and ships via CI/CD to AWS.

## Getting started

### Run everything locally (one command)

Brings up Postgres 17 (+pgvector), Redis, applies migrations, and starts the API,
Celery worker, Beat scheduler, and the frontend — no Docker required. Runs with
offline `fake` providers so it needs no API key.

```bash
./scripts/dev-local.sh      # UI: http://localhost:3000/workflows · API: http://localhost:8000/docs
./scripts/dev-local-stop.sh # stop everything (add --redis to also stop Redis)
```

Prerequisites: the backend venv (`backend/.venv`), Homebrew `postgresql@17` +
`pgvector`, `redis`, and `npm`. Runtime state and logs live under `~/.copilot/`.
Ports/paths are overridable via `COPILOT_*` env vars (see the script header). For
real Claude instead of the fakes, set `LLM_PROVIDER=anthropic`, `TOOLS_PROVIDER=live`,
and `ANTHROPIC_API_KEY` in `backend/.env`.

### Run the services individually

**Backend** (FastAPI):

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000   # http://localhost:8000/docs
```

**Frontend** (Next.js):

```bash
cd frontend
npm install
npm run dev                                  # http://localhost:3000
```

With both running, the frontend landing page shows a live "Backend online"
indicator. See [backend/README.md](backend/README.md) and
[frontend/README.md](frontend/README.md) for details, and
[docs/roadmap.md](docs/roadmap.md) for progress.
