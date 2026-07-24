"""Structured JSON logging tests."""

import json
import logging

import pytest
from app.logging_config import JsonFormatter, run_id_ctx

pytestmark = pytest.mark.unit


def _record(msg: str, **extra) -> logging.LogRecord:
    rec = logging.LogRecord("app", logging.INFO, "f.py", 1, msg, None, None)
    for k, v in extra.items():
        setattr(rec, k, v)
    return rec


def test_formatter_includes_run_id_and_extra_fields():
    token = run_id_ctx.set("run-123")
    try:
        out = json.loads(JsonFormatter().format(_record("step started", step="Search", attempt=2)))
    finally:
        run_id_ctx.reset(token)
    assert out["message"] == "step started"
    assert out["run_id"] == "run-123"
    assert out["step"] == "Search"
    assert out["attempt"] == 2
    assert out["request_id"] == "-"  # unset default


def test_formatter_omits_run_id_when_unset():
    out = json.loads(JsonFormatter().format(_record("hello")))
    assert "run_id" not in out
