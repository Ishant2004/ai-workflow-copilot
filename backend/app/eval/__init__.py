"""Evaluation harness package (Step 19).

Quality + hallucination checks over planner/executor output. Run as a CLI CI gate:

    python -m app.eval
"""

from app.eval.base import (
    CaseReport,
    CheckResult,
    EvalCase,
    EvalContext,
    EvalReport,
    Evaluator,
)
from app.eval.runner import EvalHarness, build_harness, run_eval

__all__ = [
    "CaseReport",
    "CheckResult",
    "EvalCase",
    "EvalContext",
    "EvalHarness",
    "EvalReport",
    "Evaluator",
    "build_harness",
    "run_eval",
]
