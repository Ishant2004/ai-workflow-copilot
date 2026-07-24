# Roadmap

We build in **small, focused, commit-sized steps**. After each step you commit and
push; then we start the next. This file is the single source of truth for progress.

Legend: ✅ done · 🔨 in progress · ⬜ not started

---

## Phase 0 — Foundation

| # | Step | Status |
|---|------|--------|
| 1 | Project scaffolding, README, docs, git init | ✅ |
| 2 | FastAPI backend skeleton (health endpoint, config, settings) | ✅ |
| 3 | Docker Compose infra (Postgres + pgvector, Redis, backend) + dev/prod env split + structured tests | ✅ |
| 4 | Database models & migrations (Workflow, Step, Run, StepResult) + linting | ✅ |

## Phase 1 — MVP (core copilot)

| # | Step | Status |
|---|------|--------|
| 5 | Claude integration: intent → structured workflow steps | ✅ |
| 6 | Workflow CRUD API + history storage | ✅ |
| 7 | Next.js + Tailwind frontend skeleton | ✅ |
| 8 | Frontend: task input → render generated workflow | ✅ |
| 9 | Tool execution: web search + summarization + run executor | ✅ |
| 10 | Approve / edit / reject workflow results (human-in-the-loop, backend) | ✅ |
| 11 | Output actions: Slack (webhook) / email (SMTP) delivery | ✅ |
| 12 | Queue + scheduling (Celery + Redis) — async runs + cron dispatch | ✅ |

**🎉 Phase 1 (MVP) complete.**

## Phase 2 — Grounding & UX

| # | Step | Status |
|---|------|--------|
| 13 | RAG: upload PDFs/docs, embed into pgvector | ⬜ |
| 14 | Retrieval in workflows (ground answers in user docs) | ⬜ |
| 15 | Visual workflow editor (drag-and-drop nodes) | ⬜ |
| 16 | Retries, structured logging, error handling | ⬜ |

## Phase 3 — Agents, feedback, deploy

| # | Step | Status |
|---|------|--------|
| 17 | Multi-agent orchestration (research / summarizer / reviewer) | ⬜ |
| 18 | Feedback loop to improve workflow suggestions | ⬜ |
| 19 | Evaluation harness (quality, hallucination checks) | ⬜ |
| 20 | Deploy: Docker → AWS ECS/Lambda + CI/CD | ⬜ |

---

## How each step works

1. I explain what the step adds and why.
2. I implement the smallest useful slice.
3. I tell you how to verify it runs.
4. **You commit & push.**
5. We move to the next step and update this table.
