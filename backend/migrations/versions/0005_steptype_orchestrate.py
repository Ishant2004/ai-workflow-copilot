"""add 'orchestrate' to steptype enum

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-25
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction block.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE steptype ADD VALUE IF NOT EXISTS 'orchestrate' AFTER 'summarize'")


def downgrade() -> None:
    # Removing an enum value requires recreating the type; not supported here.
    pass
