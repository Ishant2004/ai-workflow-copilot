"""Domain enums shared across models.

Kept as ``str`` enums so values serialize cleanly to JSON/API responses.
"""

from __future__ import annotations

import enum


class WorkflowStatus(str, enum.Enum):
    draft = "draft"  # created, not yet activated
    active = "active"  # eligible to run / be scheduled
    archived = "archived"  # retired, kept for history


class StepType(str, enum.Enum):
    """Typed unit of work. Extend as new tools are added."""

    web_search = "web_search"
    scrape = "scrape"
    summarize = "summarize"
    notify_slack = "notify_slack"
    notify_email = "notify_email"


class RunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    awaiting_review = "awaiting_review"  # human-in-the-loop gate
    succeeded = "succeeded"
    failed = "failed"
    rejected = "rejected"


class StepResultStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    skipped = "skipped"
