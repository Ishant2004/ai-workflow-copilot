"""Alembic environment.

The DB URL comes from application settings (DATABASE_URL). Migrations run with a
synchronous psycopg engine — no async needed for schema changes — using the same
``postgresql+psycopg://`` URL as the app.
"""

from __future__ import annotations

from logging.config import fileConfig

# Import settings, Base, and all models so target_metadata is complete.
import app.models  # noqa: F401 - registers models on Base.metadata
from alembic import context
from app.config import get_settings
from app.db.base import Base
from sqlalchemy import create_engine, pool

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    url = get_settings().database_url
    if not url:
        raise RuntimeError("DATABASE_URL is not configured for migrations")
    return url


def run_migrations_offline() -> None:
    """Emit SQL without a DB connection (`alembic upgrade head --sql`)."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_database_url(), poolclass=pool.NullPool, future=True)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
