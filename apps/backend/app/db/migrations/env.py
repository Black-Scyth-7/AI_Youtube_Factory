"""Alembic migration environment.

Runs migrations against the database configured in application settings. Uses the
synchronous psycopg DSN (``settings.sync_database_url``) so migrations do not
require an event loop. ``target_metadata`` points at the ORM ``Base`` so
autogenerate can diff models against the live schema.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.models import Base

# Alembic Config object, providing access to values within alembic.ini.
config = context.config

# Application settings are the default source of the URL, but a caller that set
# one explicitly wins — that is how the migration tests point this at a scratch
# database without mutating the environment, and how an operator can migrate a
# database other than the configured one.
if not config.get_main_option("sqlalchemy.url", None):
    config.set_main_option("sqlalchemy.url", settings.sync_database_url)

if config.config_file_name is not None:
    # disable_existing_loggers defaults to True, which silences every logger
    # already configured. That is harmless for `alembic upgrade` in its own
    # process and destructive for anything that migrates in-process — an
    # application that migrates at startup would log nothing afterwards.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (emits SQL)."""
    context.configure(
        # The resolved URL, not the settings one, so `--sql` describes the same
        # database the online path would migrate.
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
