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
   same image runs from laptop to any host with different replica counts.
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
| **Agent team (orchestrate)** | Provider + concurrency | Bound review rounds (config), share the LLM concurrency cap, run on workers; fake team offline | Fan-out of LLM calls, cost, latency |
| **Orchestrator/Workers (Celery)** | Horizontal | Scale worker replicas by queue depth; separate queues per step type; idempotent tasks | Long tasks starving queue |
| **Postgres + pgvector** | Vertical + read replicas | Connection pooling (PgBouncer), indexes, read replicas for heavy reads; partition runs by time | Write throughput, vector index size |
| **Redis (broker/cache)** | Vertical + cluster | Separate broker vs cache; eviction policy; Redis Cluster if needed | Memory, single-thread hotspots |
| **Object storage** _(optional, not wired yet)_ | Effectively unlimited | S3-compatible (R2/B2/S3) for large uploads/artifacts; presigned URLs; lifecycle rules | Egress cost |
| **Scheduler** | Stateless (current) / singleton (Beat) | Worker-free: external cron → stateless `/scheduler/tick` with a fire-once window; or one Celery Beat with a distributed lock | Missed/duplicate fires if window ≠ interval |

## Cross-cutting concerns

- **Connection pooling** — bounded DB/Redis pools sized to replica count so we don't
  exhaust Postgres `max_connections` as the API scales out.
- **Rate limiting & quotas** — per-user and global caps on LLM/tool usage (cost + fairness).
- **Idempotency** — every task/run is safe to retry; steps key off run + step IDs.
- **Graceful degradation** — if the LLM or a tool is down, fail the step, keep the run
  record, allow retry; don't cascade.
- **Caching** — cache LLM plans for identical intents and search results with TTLs.

## Tool execution (Step 9)

Runs execute **synchronously** in the request for now, but the design is
queue-ready:

- **Tools behind an interface + registry** — swap fake/real providers via config
  (`tools_provider`), no executor changes. Bounds each tool call with a timeout
  (`tool_timeout_seconds`) so a hung tool can't block the worker.
- **Everything recorded as a Run** — each step writes a `StepResult` (output/error,
  timings), so runs are listable (history), inspectable, and retriable.
- **Done (Step 12):** `POST /runs` enqueues a Celery task (`RUN_ASYNC=true`); a
  worker executes off the request path and the API stays fast. Workers scale
  horizontally by queue depth (add replicas); Beat fires cron schedules. Next
  levers: per-tool concurrency caps, retries with backoff, and separate queues
  per step type.

**Scheduling at scale:** one Beat process should run (a single scheduler). The
dispatcher only *enqueues* work — the workers do it — so the scheduler stays light.
The current cron check is at-least-once within the dispatch window; exactly-once
scheduling (distributed lock / DB-backed scheduler like RedBeat) is the HA upgrade.

## Vector search (RAG, Step 13)

Embeddings live in a pgvector column in the same Postgres — one datastore, per
ADR-004. Search is **exact cosine** (sequential scan) at MVP scale, which is
correct and simple. The scale path: add an **HNSW** index (`vector_cosine_ops`)
for approximate nearest-neighbour — note that an under-tuned IVFFlat index (too
many `lists` for the row count, low `probes`) can silently return incomplete
results, so HNSW is the safer default.

**Real providers (search + scrape + embeddings).** The `tavily` web-search tool, the
`scrape` tool (fetch URL → extract text), and the `openai` embedder are wired behind
the same interfaces, all HTTP-based and timeout-bounded. `scrape` fetches a
user-supplied URL, so it caps extracted text (`scrape_max_chars`) and applies a basic
SSRF guard (rejects non-HTTP(S) and internal/metadata hosts) — a production guard would
also resolve DNS and re-check the IP. Their network calls run off the event loop (`asyncio.to_thread`) so
they don't block the async API, and each falls back to its offline fake when the key
is unset — degradation over failure. The embedder is requested at the column's fixed
`EMBEDDING_DIM` (via OpenAI's `dimensions` param) so real vectors need no migration.
Scale levers: **batch** embedding requests (ingest already passes the whole chunk
list in one call), cache query embeddings, and give both providers the planner's
per-process concurrency cap + retry/backoff as call volume grows (per-provider rate
limits and cost become the ceiling).

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

## Multi-agent orchestration (Step 17)

The `orchestrate` step fans one step into several sequential LLM calls (researcher →
summarizer → reviewer × N rounds), so it's the most call-intensive unit of work.
Controls that keep that bounded:

- **Config-driven fan-out** — `agent_review_rounds` caps reviewer passes; each round
  trades LLM cost/latency for quality, so the fan-out is a knob, not a surprise.
- **Shared concurrency cap** — the Claude orchestrator uses the same per-process
  `llm_max_concurrency` semaphore as the planner, so many concurrent orchestrations
  can't exhaust the worker or overrun provider rate limits (backpressure over collapse).
- **Runs on the worker** — orchestration executes inside the async run path (Celery),
  off the request thread, so long agent chains never block the API; scale throughput
  by adding workers.
- **Provider-swappable** — the deterministic fake team runs offline at zero
  cost/latency for dev/tests; live is a config flip. Same interface pattern as every
  other component, so it inherits the horizontal-scaling story above.
- **Future levers**: run independent agents in parallel where the pipeline allows,
  cache research for identical topics, and stream reviewer output for long digests.

## Deployment & delivery

How the topology maps onto the scaling strategy above (details in [deployment.md](deployment.md)).
The app deploys free on **Render** today, but the design is platform-agnostic — the same
containers scale on any host:

- **Stateless services scale horizontally** — api and frontend are independent web
  services; the api can run behind a load balancer with multiple replicas. On the free
  tier they run single-instance with runs executing inline.
- **Config & secrets are injected, not baked** — env vars (Render/host secrets) per the
  dev/prod separation principle; the same image runs in every environment.
- **Migrations run on API start** (`alembic upgrade head`), so a deploy always matches its
  schema. (For a multi-replica scale-out, move this to a one-off pre-deploy job to avoid
  concurrent migration races.)
- **Scheduling scales without a singleton scheduler** — an external cron hits a stateless
  tick endpoint; the "fire exactly once" window replaces a dedicated Beat process.
- **Optional async path** — enabling Celery worker + Redis lets long runs execute off the
  request thread and scale by queue depth (worker replicas); beat stays a singleton.
- **CI is the quality gate at scale** — lint, tests (incl. integration + pgvector), and the
  eval/grounding gate must pass on every push, so regressions can't ship.

## Evaluation harness (Step 19)

The harness is how quality *stays* scalable as the system grows — it catches
regressions before they ship rather than after they degrade production:

- **Offline + deterministic by default** — with the fake providers it runs with no
  network/API cost, so it's cheap enough to gate every CI run; the LLM path is opt-in
  for periodic deeper evals.
- **Cheap grounding proxy** — the anti-hallucination score is O(tokens) set overlap,
  not an LLM call, so scoring thousands of cases stays fast; the `Evaluator` interface
  lets a costlier LLM-grader slot in only where warranted.
- **Data-driven scale-out** — cases come from a JSON dataset (`EVAL_DATASET_PATH`),
  so the suite grows without code changes and can be sharded across CI workers; the
  Step 18 feedback corpus is a natural source of new cases.
- **CI gate, not a dashboard** — a single pass-rate threshold (`EVAL_MIN_PASS_RATE`)
  turns quality into a build-breaking signal, which is what keeps it enforced at scale.

## Feedback loop (Step 18)

Capturing feedback and feeding it back into planning adds a read+write path around
every suggestion. Kept cheap and bounded:

- **Bounded few-shot context** — only the top `planner_example_limit` recent positive
  exemplars are injected, capping the prompt-token growth (cost/latency) no matter how
  much feedback accumulates. `0` disables the loop entirely.
- **Indexed, self-contained reads** — exemplars come from a single indexed query
  (`rating`, `created_at`), and each row snapshots its own task+plan, so building the
  few-shot set never fans out into workflow/step joins.
- **Durable corpus** — feedback survives workflow deletes (`ON DELETE SET NULL`), so
  the learning corpus isn't coupled to workflow lifecycle; it can later feed offline
  fine-tuning or an eval set (Step 19) without a migration.
- **Future levers**: embed tasks and retrieve the *most similar* approved exemplars
  (not just the most recent) via pgvector; per-user exemplar scoping; aggregate
  negative feedback into planner guardrails.

## Reliability & observability (Step 16)

Hardening the execution path so failures degrade gracefully instead of cascading:

- **Step retries with backoff** — a transiently-failing step retries up to
  `step_max_retries` with exponential backoff (`step_retry_backoff_seconds`,
  `2**attempt`), so a brief provider blip self-heals instead of failing a whole run.
  Errors flagged non-retryable (bad config, not a transient fault) fail fast — retries
  are spent only where they can help, not amplifying deterministic failures into load.
- **Correlated structured logs** — JSON logs carry `request_id` and, within a run,
  `run_id` + per-step fields. Across many stateless API/worker replicas this is what
  makes a single run traceable in aggregation, and it's the raw signal for deciding
  *what* to scale (per-step latency, retry rates).
- **Uniform error responses** — unhandled exceptions become a safe `500` at the
  middleware boundary; this keeps clients (and retrying callers/LBs) seeing a
  predictable contract and never leaks internals under load or in debug mode.

## When we revisit this

Each new component's step will note its entry in the table above and any new bottleneck
it introduces. See [architecture.md](architecture.md) for the component map and
[decisions.md](decisions.md) for the infra choices these strategies build on.
