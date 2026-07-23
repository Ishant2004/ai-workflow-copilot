# Decision records

Lightweight ADRs. Each entry: the decision, the context, and why. `task.md` offered
several options per layer; this records which we picked and why.

---

## ADR-001 — Backend: FastAPI (Python)

**Decision:** Build the backend in Python with FastAPI.

**Why:** The project is heavy on LLM orchestration, embeddings, RAG, and agents.
Python has the richest ecosystem for these (Anthropic SDK, LangChain/LlamaIndex,
pgvector clients, Celery). FastAPI gives async performance, typed request/response
models via Pydantic, and automatic OpenAPI docs. The trade-off — a second language
alongside the TS frontend — is worth it for the AI tooling.

## ADR-002 — LLM: Anthropic Claude

**Decision:** Use Anthropic Claude as the primary LLM.

**Why:** Strong tool-use / structured-output behavior, which is central to the
planner (intent → typed steps) and to agent orchestration in later phases. We isolate
the provider behind a service interface so it can be swapped if needed.

## ADR-003 — Infra: Docker Compose from the start

**Decision:** Run Postgres (with pgvector), Redis, and the backend via Docker Compose
locally from early on.

**Why:** Keeps local dev close to production, avoids a painful migration later
(e.g. SQLite → Postgres), and makes pgvector and the Redis-backed queue available
when we need them. Matches the eventual AWS/Docker deployment goal.

## ADR-004 — Vector DB: pgvector

**Decision:** Use the `pgvector` Postgres extension rather than a separate vector DB.

**Why:** One datastore instead of two. Workflows/runs and embeddings live together,
simplifying ops for an MVP. Can migrate to a dedicated vector DB (Qdrant/Pinecone)
if scale demands it.

## ADR-005 — Queue: Redis + Celery

**Decision:** Use Redis as broker with Celery workers for async step execution and
scheduling.

**Why:** Mature, well-documented, runs locally in Docker, and Celery Beat covers the
"every morning" scheduling requirement. Portable toward SQS later if desired.

## ADR-006 — Build process: small steps, commit per step

**Decision:** Ship in small, focused, commit-sized steps; the user commits and pushes
after each.

**Why:** Reviewable diffs, clean history, and a clear place to stop/resume. Progress
is tracked in [roadmap.md](roadmap.md).
