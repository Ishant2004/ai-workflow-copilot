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
- [Mind map](docs/mind-map.md) — how the concepts connect.
- [Decision records](docs/decisions.md) — key technical choices and their rationale.

## Status

🚧 Early development. Building incrementally — see the [roadmap](docs/roadmap.md)
for what's done and what's next.

## Getting started

Setup instructions will be filled in as the backend, frontend, and infra land in
the coming steps. Track progress in [docs/roadmap.md](docs/roadmap.md).
