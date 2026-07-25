"""Eval dataset — the built-in cases plus a JSON loader.

Cases are intentionally small and offline-runnable so the harness is a fast CI
gate. Point ``EVAL_DATASET_PATH`` at a JSON file to evaluate a custom suite:

    [{"name": "...", "task_description": "...", "expect_step_types": ["web_search"]}]
"""

from __future__ import annotations

import json
from pathlib import Path

from app.eval.base import EvalCase

DEFAULT_CASES: tuple[EvalCase, ...] = (
    EvalCase(
        name="news_digest",
        task_description="Collect AI startup news, summarize it, and Slack me a digest",
        expect_step_types=("web_search", "summarize"),
    ),
    EvalCase(
        name="competitor_watch",
        task_description="Track competitor product launches weekly and email me a summary",
        expect_step_types=("web_search", "summarize"),
    ),
    EvalCase(
        name="research_brief",
        task_description="Research the state of battery recycling and write a brief",
        expect_step_types=("web_search",),
    ),
)


def load_cases(path: str | None) -> list[EvalCase]:
    """Load cases from a JSON file, or return the built-in defaults when unset."""
    if not path:
        return list(DEFAULT_CASES)
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        EvalCase(
            name=item["name"],
            task_description=item["task_description"],
            expect_step_types=tuple(item.get("expect_step_types", ())),
        )
        for item in raw
    ]
