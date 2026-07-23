"""Declarative base and shared model mixins."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base; all models' metadata lives here (used by Alembic)."""


class UUIDMixin:
    """UUID primary key generated app-side (safe across replicas, no sequence contention)."""

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    """Server-managed created/updated timestamps for auditing and history."""

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )
