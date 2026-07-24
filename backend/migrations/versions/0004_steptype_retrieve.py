"""add 'retrieve' to steptype enum

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-24
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction block.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE steptype ADD VALUE IF NOT EXISTS 'retrieve' AFTER 'scrape'")


def downgrade() -> None:
    # Removing an enum value requires recreating the type; not supported here.
    pass
