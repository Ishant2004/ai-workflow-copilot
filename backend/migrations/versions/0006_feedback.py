"""feedback table (suggestion-improvement loop)

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Enum value set snapshotted here (migrations are self-contained).
FEEDBACK_RATING = ("positive", "negative")

_NOW = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workflow_id",
            postgresql.UUID(as_uuid=True),
            # Nulled (not cascaded) on delete so the snapshot survives as an exemplar.
            sa.ForeignKey("workflows.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "rating",
            postgresql.ENUM(*FEEDBACK_RATING, name="feedbackrating"),
            nullable=False,
        ),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("task_description", sa.Text(), nullable=False),
        sa.Column("plan", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=_NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=_NOW, nullable=False),
    )
    op.create_index("ix_feedback_workflow_id", "feedback", ["workflow_id"])
    op.create_index("ix_feedback_rating", "feedback", ["rating"])


def downgrade() -> None:
    op.drop_index("ix_feedback_rating", table_name="feedback")
    op.drop_index("ix_feedback_workflow_id", table_name="feedback")
    op.drop_table("feedback")
    op.execute("DROP TYPE IF EXISTS feedbackrating")
