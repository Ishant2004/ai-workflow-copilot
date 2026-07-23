# Backend — Workflow AI Copilot

FastAPI service. Stateless and config-driven so it scales horizontally (see
[../docs/scalability.md](../docs/scalability.md)).

## Layout

```
app/
├── main.py            # create_app() application factory + entrypoint
├── config.py          # Pydantic settings from environment (12-factor)
├── logging_config.py  # structured JSON logging + request-id context
├── middleware.py      # X-Request-ID correlation middleware
└── api/routes/
    └── health.py      # /health, /health/live, /health/ready
tests/
└── test_health.py     # smoke tests
```

## Run locally

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Then:
- API docs (Swagger): http://localhost:8000/docs
- Health: http://localhost:8000/health

Scale out with multiple workers (each process is independent, no shared state):

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Test

```bash
source .venv/bin/activate
pytest -q
```

## Notes

- **Python 3.12–3.14** supported (deps pinned to versions with 3.14 wheels).
- **Endpoints:** `/health` (identity + status), `/health/live` (liveness probe),
  `/health/ready` (readiness probe — will check DB/Redis in later steps).
- **Config:** all via env vars — see [.env.example](.env.example).
