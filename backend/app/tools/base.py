"""Tool interface.

A Tool executes one workflow step. Tools are isolated behind this interface so
implementations are swappable (deterministic fakes for dev/tests, real providers
in production) and the executor stays provider-agnostic.

The ``context`` dict carries outputs from earlier steps (keyed by step-type value),
letting a step consume upstream results — e.g. ``summarize`` reads the prior
``web_search`` output. Tools return a JSON-serializable output dict that is stored
on the step's result and merged into the context for later steps.
"""

from __future__ import annotations

import abc
from typing import Any

from app.models.workflow import Step

# A step's structured output. Must be JSON-serializable (stored in JSONB).
ToolOutput = dict[str, Any]
ExecutionContext = dict[str, Any]


class ToolError(RuntimeError):
    """Raised when a tool cannot complete its step."""


class Tool(abc.ABC):
    @abc.abstractmethod
    async def run(self, step: Step, context: ExecutionContext) -> ToolOutput:
        """Execute ``step`` and return its output.

        Raises:
            ToolError: if the step cannot be completed.
        """
        raise NotImplementedError
