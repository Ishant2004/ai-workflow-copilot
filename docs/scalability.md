# Scalability

Scalability is a **per-component design constraint**, not a later optimization. Every
component we add is reviewed against the concerns below, and this file records the
strategy for each. Updated as components land.

## Guiding principles

1. **Stateless services scale horizontally.** The API and workers hold no in-memory
   session state; anything durable lives in Postgres, Redis, or S3. Add replicas
   behind a load balancer to scale out.
2. **Push slow work to the queue.** HTTP requests stay fast; LLM calls, scraping, and
   summarization run async via Celery workers that scale independently of the API.
3. **Config via environment.** No hardcoded hosts/secrets — 12-factor config so the
   same image runs from laptop to ECS with different replica counts.
4. **Bounded resource use.** Timeouts, retries with backoff, and rate limits on every
   external call (LLM, search, scrape) so one slow dependency can't exhaust the pool.
5. **Observability first.** Structured logs, request IDs, and per-step run records so
   bottlenecks are measurable before we scale them.
6. **Backpressure over collapse.** Queues have max lengths; APIs return 429/503 rather
   than falling over under load.

## Per-component strategy

| Component | Scaling axis | Strategy | Bottleneck watch |
|-----------|-------------|----------|------------------|
| **Frontend (Next.js)** | Horizontal / CDN | Static assets on CDN, SSR stateless, cache-friendly | N/A (client-heavy) |
| **API (FastAPI)** | Horizontal | Stateless, async I/O, multiple Uvicorn workers behind LB; autoscale on CPU/RPS | DB connections, event-loop blocking |
| **Planner (Claude)** | Provider + concurrency | Cap concurrent LLM calls, retries w/ backoff, cache identical prompts, stream responses | Token latency, rate limits, cost |
| **Orchestrator/Workers (Celery)** | Horizontal | Scale worker replicas by queue depth; separate queues per step type; idempotent tasks | Long tasks starving queue |
| **Postgres + pgvector** | Vertical + read replicas | Connection pooling (PgBouncer), indexes, read replicas for heavy reads; partition runs by time | Write throughput, vector index size |
| **Redis (broker/cache)** | Vertical + cluster | Separate broker vs cache; eviction policy; Redis Cluster if needed | Memory, single-thread hotspots |
| **S3 (storage)** | Effectively unlimited | Offload large artifacts/uploads; presigned URLs; lifecycle rules | Egress cost |
| **Scheduler (Celery Beat)** | Single + failover | One active scheduler; distributed lock to prevent duplicate triggers | Single point — needs HA |

## Cross-cutting concerns

- **Connection pooling** — bounded DB/Redis pools sized to replica count so we don't
  exhaust Postgres `max_connections` as the API scales out.
- **Rate limiting & quotas** — per-user and global caps on LLM/tool usage (cost + fairness).
- **Idempotency** — every task/run is safe to retry; steps key off run + step IDs.
- **Graceful degradation** — if the LLM or a tool is down, fail the step, keep the run
  record, allow retry; don't cascade.
- **Caching** — cache LLM plans for identical intents and search results with TTLs.

## Schema migrations at scale

Migrations run as a **separate one-off job** (`migrate` service / `alembic upgrade head`),
not inside the server's startup path. Running them per-replica would race when the
backend scales out. In dev (single replica) the container entrypoint applies them for
convenience; in prod the backend waits for the migrate job to complete first.

Pool sizing is config-driven (`db_pool_size`, `db_max_overflow`) so that
`replicas * (pool_size + max_overflow)` stays under Postgres `max_connections`.
`pool_pre_ping` recycles dropped connections transparently.

## Planner / LLM calls

The planner is isolated behind an interface with concrete reliability/scalability
controls, all config-driven (no magic numbers):

- **Bounded concurrency** — a per-process semaphore (`llm_max_concurrency`) caps
  in-flight LLM calls so a burst can't exhaust the worker or overrun provider rate
  limits (backpressure over collapse).
- **Timeouts + retries** — `llm_timeout_seconds` and `llm_max_retries` (SDK
  exponential backoff) keep one slow/failed call from blocking the request pool.
- **Provider-swappable** — the `fake` provider runs offline (dev/tests) with zero
  cost/latency; the real provider is a config flip.
- **Future levers** (noted in the table above): cache identical-intent plans,
  per-user quotas, and streaming for long outputs.

## When we revisit this

Each new component's step will note its entry in the table above and any new bottleneck
it introduces. See [architecture.md](architecture.md) for the component map and
[decisions.md](decisions.md) for the infra choices these strategies build on.
