"""initial schema: workflows, steps, runs, step_results

Revision ID: 0001
Revises:
Create Date: 2026-07-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Enum value sets are snapshotted here (migrations are self-contained).
WORKFLOW_STATUS = ("draft", "active", "archived")
STEP_TYPE = ("web_search", "scrape", "summarize", "notify_slack", "notify_email")
RUN_STATUS = ("pending", "running", "awaiting_review", "succeeded", "failed", "rejected")
STEP_RESULT_STATUS = ("pending", "running", "succeeded", "failed", "skipped")

_NOW = sa.text("now()")


def upgrade() -> None:
    # pgvector extension — embeddings (Phase 2 RAG) live in the same database.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "workflows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(*WORKFLOW_STATUS, name="workflowstatus"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=_NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=_NOW, nullable=False),
    )
    op.create_index("ix_workflows_status", "workflows", ["status"])

    op.create_table(
        "steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workflow_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("type", postgresql.ENUM(*STEP_TYPE, name="steptype"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "config",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=_NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=_NOW, nullable=False),
    )
    op.create_index("ix_steps_workflow_id", "steps", ["workflow_id"])

    op.create_table(
        "runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workflow_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(*RUN_STATUS, name="runstatus"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=_NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=_NOW, nullable=False),
    )
    op.create_index("ix_runs_workflow_id", "runs", ["workflow_id"])
    op.create_index("ix_runs_status", "runs", ["status"])

    op.create_table(
        "step_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "step_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("steps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(*STEP_RESULT_STATUS, name="stepresultstatus"),
            nullable=False,
        ),
        sa.Column("output", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=_NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=_NOW, nullable=False),
    )
    op.create_index("ix_step_results_run_id", "step_results", ["run_id"])
    op.create_index("ix_step_results_step_id", "step_results", ["step_id"])


def downgrade() -> None:
    op.drop_table("step_results")
    op.drop_table("runs")
    op.drop_table("steps")
    op.drop_table("workflows")
    for enum_name in ("stepresultstatus", "runstatus", "steptype", "workflowstatus"):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
