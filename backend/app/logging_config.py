"""Structured JSON logging.

Observability is a scalability concern: to know *what* to scale we must measure it.
Logs are emitted as single-line JSON with a per-request ``request_id`` so they can be
aggregated and traced across replicas in production.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar

# Set per request by RequestIDMiddleware; read by the log formatter.
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")
# Set by the executor while a run executes, so all logs in a run carry its id.
run_id_ctx: ContextVar[str | None] = ContextVar("run_id", default=None)

# LogRecord attributes we never treat as user-supplied "extra" fields.
_STANDARD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """Format log records as compact single-line JSON.

    Includes the request/run correlation ids and any structured ``extra=`` fields
    passed to the logger, so logs can be filtered by run/step in aggregation.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_ctx.get(),
        }
        run_id = run_id_ctx.get()
        if run_id is not None:
            payload["run_id"] = run_id
        # Merge caller-provided structured fields (logger.info(..., extra={...})).
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger to emit JSON to stdout."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # Route uvicorn's loggers through our handler for consistent output.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True
