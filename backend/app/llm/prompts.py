"""Planner prompt and tool schema.

We use Claude's *tool use* (function calling) with a single forced tool,
``emit_workflow_plan``. Forcing the tool guarantees the model responds with
structured arguments we can validate against ``WorkflowPlan`` — this is the
reliable way to get typed output, and it exercises the tool-use concept the
project is built to demonstrate.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from app.models.enums import StepType

if TYPE_CHECKING:
    from app.llm.schemas import PlanExample

PLANNER_TOOL_NAME = "emit_workflow_plan"

_STEP_TYPE_VALUES = [t.value for t in StepType]

SYSTEM_PROMPT = f"""\
You are the planning component of a Workflow AI Copilot. The user describes a \
repetitive task in plain English. Break it into an ordered list of concrete, \
executable steps.

Rules:
- Use ONLY these step types: {", ".join(_STEP_TYPE_VALUES)}.
- Order steps so each can use the outputs of earlier ones (e.g. search or scrape \
before summarizing; summarize before notifying).
- Put tool parameters in each step's `config` object (for example, a search query \
under "query", or a Slack channel under "channel"). Keep keys lowercase snake_case.
- Prefer the fewest steps that fully accomplish the task.
- Always respond by calling the {PLANNER_TOOL_NAME} tool. Do not answer in prose.
"""


def build_examples_block(examples: Sequence[PlanExample] | None) -> str:
    """Render approved (task → plan) exemplars as a few-shot guidance block.

    Appended to the system prompt so the planner mirrors shapes users have rated
    positively (Step 18 feedback loop). Empty string when there are no examples.
    """
    if not examples:
        return ""
    rendered = []
    for ex in examples:
        steps = [{"type": s.type.value, "name": s.name, "config": s.config} for s in ex.plan.steps]
        rendered.append(f'Task: "{ex.task_description}"\nApproved plan: {json.dumps(steps)}')
    joined = "\n\n".join(rendered)
    return (
        "\n\nThe user has previously approved these plans. Prefer similar structure "
        f"and step choices when they fit the new task:\n\n{joined}"
    )


def build_planner_tool() -> dict[str, Any]:
    """JSON-schema tool definition for the planner's structured output."""
    return {
        "name": PLANNER_TOOL_NAME,
        "description": ("Emit the structured, ordered workflow plan derived from the user's task."),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short human-readable title for the workflow.",
                },
                "summary": {
                    "type": "string",
                    "description": "One or two sentences describing what the workflow does.",
                },
                "steps": {
                    "type": "array",
                    "description": "Ordered steps to execute.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": _STEP_TYPE_VALUES,
                                "description": "The typed action this step performs.",
                            },
                            "name": {
                                "type": "string",
                                "description": "Short label for the step.",
                            },
                            "description": {
                                "type": "string",
                                "description": "What this step does, in plain English.",
                            },
                            "config": {
                                "type": "object",
                                "description": "Tool parameters for this step.",
                            },
                        },
                        "required": ["type", "name", "description"],
                    },
                },
            },
            "required": ["title", "summary", "steps"],
        },
    }
