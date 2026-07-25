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
    retrieve = "retrieve"  # RAG: fetch relevant chunks from uploaded documents
    summarize = "summarize"
    orchestrate = "orchestrate"  # multi-agent: researcher → summarizer → reviewer
    notify_slack = "notify_slack"
    notify_email = "notify_email"


class FeedbackRating(str, enum.Enum):
    """User's verdict on a generated workflow suggestion."""

    positive = "positive"  # good suggestion — reuse as a planning exemplar
    negative = "negative"  # poor suggestion — do not learn from it


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
