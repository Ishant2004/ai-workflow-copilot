"""Evaluation harness — core types.

The harness runs the planner (and executor) over a dataset of cases and scores the
results with a set of **evaluators** — quality and hallucination checks — producing
a structured report. Evaluators sit behind an interface (like every other provider
here) so heuristic offline checks can later be swapped for LLM-graded ones without
touching the runner.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field

from app.llm.schemas import WorkflowPlan
from app.models.run import Run


@dataclass(frozen=True)
class EvalCase:
    """One scenario to evaluate: a task, plus optional expectations."""

    name: str
    task_description: str
    # Step types the plan is expected to contain (subset check), if specified.
    expect_step_types: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvalContext:
    """What a produced run gives an evaluator to score."""

    case: EvalCase
    plan: WorkflowPlan
    run: Run


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    score: float  # 0.0–1.0
    detail: str = ""


@dataclass
class CaseReport:
    case_name: str
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)


@dataclass
class EvalReport:
    cases: list[CaseReport] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.cases)

    @property
    def passed_count(self) -> int:
        return sum(1 for c in self.cases if c.passed)

    @property
    def pass_rate(self) -> float:
        return self.passed_count / self.total if self.total else 1.0

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "passed": self.passed_count,
            "pass_rate": round(self.pass_rate, 4),
            "cases": [
                {
                    "case": c.case_name,
                    "passed": c.passed,
                    "checks": [
                        {
                            "name": chk.name,
                            "passed": chk.passed,
                            "score": round(chk.score, 4),
                            "detail": chk.detail,
                        }
                        for chk in c.checks
                    ],
                }
                for c in self.cases
            ],
        }


class Evaluator(abc.ABC):
    """Scores one produced run against its case."""

    name: str

    @abc.abstractmethod
    def evaluate(self, ctx: EvalContext) -> CheckResult:
        raise NotImplementedError
