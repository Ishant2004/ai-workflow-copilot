"""Concrete evaluators: plan quality, run success, and grounding (hallucination)."""

from __future__ import annotations

from app.eval.base import CheckResult, EvalContext, Evaluator
from app.eval.grounding import grounding_score
from app.models.enums import StepResultStatus, StepType

# Step types that gather material a later step can build on.
_SOURCE_TYPES = frozenset(
    {StepType.web_search.value, StepType.scrape.value, StepType.retrieve.value}
)
# Step types that produce a deliverable digest.
_DIGEST_TYPES = frozenset({StepType.summarize.value, StepType.orchestrate.value})
# Step types with external side effects that deliver a digest.
_NOTIFY_TYPES = frozenset({StepType.notify_slack.value, StepType.notify_email.value})
# Config keys each step type requires to be executable.
_REQUIRED_CONFIG = {
    StepType.web_search.value: "query",
    StepType.scrape.value: "query",
    StepType.retrieve.value: "query",
    StepType.notify_email.value: "to",
}


def _outputs_by_type(ctx: EvalContext) -> dict[str, dict]:
    """Map step-type → output, pairing plan steps with executed results by order."""
    outputs: dict[str, dict] = {}
    for step, result in zip(ctx.plan.steps, ctx.run.step_results, strict=False):
        if result.output is not None:
            outputs[step.type.value] = result.output
    return outputs


class PlanStructureEvaluator(Evaluator):
    """Quality: the plan is non-empty, ordered sanely, and executable."""

    name = "plan_structure"

    def evaluate(self, ctx: EvalContext) -> CheckResult:
        steps = ctx.plan.steps
        problems: list[str] = []

        if not steps:
            return CheckResult(self.name, passed=False, score=0.0, detail="plan has no steps")

        seen_source = False
        seen_digest = False
        for i, step in enumerate(steps):
            type_value = step.type.value
            if type_value in _SOURCE_TYPES:
                seen_source = True
            if type_value == StepType.summarize.value and not seen_source:
                problems.append(f"step {i} summarize has no preceding source step")
            if type_value in _DIGEST_TYPES:
                seen_digest = True
            if type_value in _NOTIFY_TYPES and not (seen_digest or seen_source):
                problems.append(f"step {i} notify has nothing to deliver")
            required = _REQUIRED_CONFIG.get(type_value)
            if required and not step.config.get(required):
                problems.append(f"step {i} {type_value} missing config '{required}'")

        expected = set(ctx.case.expect_step_types)
        present = {s.type.value for s in steps}
        missing = expected - present
        if missing:
            problems.append(f"missing expected step types: {sorted(missing)}")

        passed = not problems
        return CheckResult(
            self.name,
            passed=passed,
            score=1.0 if passed else 0.0,
            detail="; ".join(problems) or "ok",
        )


class RunSuccessEvaluator(Evaluator):
    """Quality: executing the plan produced no failed steps."""

    name = "run_success"

    def evaluate(self, ctx: EvalContext) -> CheckResult:
        results = ctx.run.step_results
        failed = [r for r in results if r.status is StepResultStatus.failed]
        total = len(results) or 1
        score = 1.0 - len(failed) / total
        detail = "ok" if not failed else f"{len(failed)} step(s) failed: {failed[0].error}"
        return CheckResult(self.name, passed=not failed, score=score, detail=detail)


class GroundingEvaluator(Evaluator):
    """Hallucination: the produced digest is supported by its source material."""

    name = "grounding"

    def __init__(self, threshold: float) -> None:
        self._threshold = threshold

    def evaluate(self, ctx: EvalContext) -> CheckResult:
        outputs = _outputs_by_type(ctx)

        digest = ""
        orchestrate = outputs.get(StepType.orchestrate.value)
        summarize = outputs.get(StepType.summarize.value)
        if orchestrate:
            digest = str(orchestrate.get("final", ""))
        elif summarize:
            digest = str(summarize.get("summary", ""))

        if not digest:
            return CheckResult(
                self.name, passed=True, score=1.0, detail="no digest produced; nothing to ground"
            )

        sources = self._collect_sources(outputs)
        score = grounding_score(digest, sources)
        passed = score >= self._threshold
        return CheckResult(
            self.name,
            passed=passed,
            score=score,
            detail=f"{score:.2f} of digest supported by sources (threshold {self._threshold})",
        )

    @staticmethod
    def _collect_sources(outputs: dict[str, dict]) -> list[str]:
        sources: list[str] = []

        search = outputs.get(StepType.web_search.value) or {}
        for result in search.get("results", []):
            sources.append(str(result.get("snippet") or result.get("title") or ""))

        retrieved = outputs.get(StepType.retrieve.value) or {}
        for chunk in retrieved.get("chunks", []):
            sources.append(str(chunk.get("content") or ""))

        scraped = outputs.get(StepType.scrape.value) or {}
        if scraped.get("content"):
            sources.append(str(scraped["content"]))

        # The orchestrator's own researcher turn is source material for its digest.
        orchestrate = outputs.get(StepType.orchestrate.value) or {}
        for turn in orchestrate.get("turns", []):
            if turn.get("role") == "researcher":
                sources.append(str(turn.get("output") or ""))

        return [s for s in sources if s]
