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
| Queue        | Redis + Celery (optional async path) |
| Storage      | PostgreSQL (+ pgvector)             |
| Deployment   | Docker → Render (free tier)         |

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

- [How it works](docs/how-it-works.md) — the full end-to-end flow, and how it runs in production.
- [Roadmap](docs/roadmap.md) — the step-by-step build plan (we commit after each step).
- [Architecture](docs/architecture.md) — system design and data flow.
- [Scalability](docs/scalability.md) — per-component scaling strategy (a design constraint, not an afterthought).
- [Deployment](docs/deployment.md) — free Render deploy, container images, scheduling, and CI.
- [Mind map](docs/mind-map.md) — how the concepts connect.
- [Decision records](docs/decisions.md) — key technical choices and their rationale.

## Deployment & CI/CD

Both apps are containerized (`backend/Dockerfile`, `frontend/Dockerfile`) and deploy
**free on Render** from one Blueprint ([render.yaml](render.yaml)) — frontend + API +
managed Postgres, with runs executing inline and cron handled by a free external
scheduler hitting `/api/scheduler/tick`. GitHub Actions ([ci.yml](.github/workflows/ci.yml))
runs the quality gate on every push (lint, tests incl. pgvector integration, eval/grounding);
Render auto-deploys on merge to `main`. See [docs/deployment.md](docs/deployment.md) and
the full runtime walkthrough in [docs/how-it-works.md](docs/how-it-works.md).

## What's built

**Backend** — plan generation, workflow CRUD + visual step editing, typed tool
execution, human-in-the-loop review gate, RAG (upload → pgvector → retrieve),
multi-agent orchestration (researcher/summarizer/reviewer), feedback learning loop,
retries + structured logging + uniform errors, and an evaluation harness (quality +
grounding gate).

**Frontend** — describe a task → preview plan → create; list workflows; visual editor
(reorder/edit steps, set status + cron); **run workflows + view run history**;
**human review** (edit output → approve/reject); **document upload** (RAG);
**👍/👎 feedback**.

**Every external provider sits behind an interface with an offline fake**, so the whole
app runs with zero API keys. Flip to the real version by setting one or two env vars:

| Capability | Offline default | Real version — set |
|---|---|---|
| Plan generation | fake planner | `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY` |
| Summarize / multi-agent | deterministic fake | `TOOLS_PROVIDER=live` + `ANTHROPIC_API_KEY` |
| Web search | simulated results | `SEARCH_PROVIDER=tavily` + `TAVILY_API_KEY` |
| Scrape (URL → text) | simulated | `TOOLS_PROVIDER=live` (real fetch, **no key**) |
| RAG embeddings | hashing embedder | `EMBEDDING_PROVIDER=openai` + `OPENAI_API_KEY` |
| Slack delivery | simulated | `SLACK_WEBHOOK_URL` |
| Email delivery | simulated | `SMTP_HOST` + `EMAIL_FROM` (+ `SMTP_USER`/`SMTP_PASSWORD`) |
| Async run queue | inline execution | `RUN_ASYNC=true` + Celery worker + Redis |
| Cron scheduling | — | `SCHEDULER_TOKEN` + an external cron (or Celery Beat) |

The `live`/`tavily`/`openai` real tools all fall back to their fake if the key is
missing, so nothing breaks — you just get the simulated result. See
[backend/.env.example](backend/.env.example) for every setting.

**Not built (optional):** S3 file storage — uploads are chunked into Postgres, but the
raw file isn't archived to object storage. Everything else is implemented.

## Status

✅ All 20 [roadmap](docs/roadmap.md) steps complete, plus post-roadmap enhancements:
real providers (Tavily search, OpenAI embeddings), a real scrape tool, the full
run/review/RAG/feedback UI, and worker-free cron scheduling. The system runs
end-to-end locally (`./scripts/dev-local.sh`), ships to **AWS** via CI/CD, and deploys
free to **Render** ([render.yaml](render.yaml)) — see [docs/deployment.md](docs/deployment.md).

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
