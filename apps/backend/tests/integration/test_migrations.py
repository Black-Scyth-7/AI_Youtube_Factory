"""Tests that the migrations describe the schema the models expect.

The rest of the suite builds its database with ``Base.metadata.create_all``,
which means nothing else here executes a migration at all. That is how these
rotted: every migration called ``create_all`` itself, so a fresh database always
matched the models, while a deployed one silently never received a change —
``create_all`` only creates missing tables and cannot alter an existing one.

These run against a scratch SQLite file, so they need no infrastructure. The
DDL is dialect-neutral; a PostgreSQL run is available too and is skipped unless
``MIGRATION_TEST_DATABASE_URL`` names a reachable server.
"""

from __future__ import annotations

import logging
import os
import pathlib
import re
import tempfile
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from app.models import Base
from sqlalchemy import create_engine, inspect

BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[2]
VERSIONS = BACKEND_ROOT / "app" / "db" / "migrations" / "versions"


def _config(url: str) -> Config:
    """An Alembic config pointed at ``url`` rather than the app's database."""
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "app/db/migrations"))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture()
def sqlite_url() -> Iterator[str]:
    with tempfile.TemporaryDirectory() as tmp:
        yield f"sqlite:///{(pathlib.Path(tmp) / 'migrations.sqlite').as_posix()}"


def _table_names(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return {t for t in inspect(engine).get_table_names() if t != "alembic_version"}
    finally:
        engine.dispose()


# -- The schema migrations produce --------------------------------------------


def test_migrations_create_every_table_the_models_declare(sqlite_url: str) -> None:
    command.upgrade(_config(sqlite_url), "head")
    assert _table_names(sqlite_url) == set(Base.metadata.tables)


def test_migrations_create_every_column_the_models_declare(sqlite_url: str) -> None:
    """The failure mode that matters: a model gains a column and no migration
    adds it. Under the old ``create_all`` scheme this was invisible, because a
    fresh database was built from the models themselves."""
    command.upgrade(_config(sqlite_url), "head")

    engine = create_engine(sqlite_url)
    try:
        inspector = inspect(engine)
        missing: list[str] = []
        extra: list[str] = []
        for name, table in Base.metadata.tables.items():
            migrated = {c["name"] for c in inspector.get_columns(name)}
            declared = {c.name for c in table.columns}
            missing.extend(f"{name}.{c}" for c in sorted(declared - migrated))
            extra.extend(f"{name}.{c}" for c in sorted(migrated - declared))
    finally:
        engine.dispose()

    assert not missing, f"columns in the models but not in any migration: {missing}"
    assert not extra, f"columns in the migrations but not in the models: {extra}"


def test_every_revision_applies_and_reverts(sqlite_url: str) -> None:
    """Each revision must stand alone: upgrade one at a time, then unwind."""
    config = _config(sqlite_url)
    revisions = [s.revision for s in ScriptDirectory.from_config(config).walk_revisions()]
    revisions.reverse()

    seen = 0
    for revision in revisions:
        command.upgrade(config, revision)
        count = len(_table_names(sqlite_url))
        assert count > seen, f"{revision} added no tables; is it a no-op?"
        seen = count

    command.downgrade(config, "base")
    assert _table_names(sqlite_url) == set()


def test_head_is_a_single_revision() -> None:
    """Two heads mean a branch nobody meant to create, and `upgrade head` fails."""
    heads = ScriptDirectory.from_config(_config("sqlite://")).get_heads()
    assert len(heads) == 1, f"expected one head, found {heads}"


# -- The regression itself ----------------------------------------------------


def test_no_migration_builds_its_schema_from_the_orm_metadata() -> None:
    """A migration must describe a fixed schema, not whatever the models say now.

    ``Base.metadata.create_all()`` in a migration makes the revision mean
    something different depending on when it runs, and silently skips any table
    that already exists — so no such migration can ever alter one.
    """
    offenders = []
    for path in sorted(VERSIONS.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        # Ignore the docstrings, which explain precisely this.
        code = re.sub(r'"""[\s\S]*?"""', "", source)
        for pattern in ("create_all", "drop_all", "Base.metadata"):
            if pattern in code:
                offenders.append(f"{path.name}: {pattern}")
    assert not offenders, f"migrations must use explicit DDL: {offenders}"


def test_every_migration_has_a_downgrade() -> None:
    for path in sorted(VERSIONS.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        assert "def downgrade()" in source, f"{path.name} has no downgrade"
        body = source.split("def downgrade()", 1)[1]
        assert "op." in body, f"{path.name}'s downgrade does nothing"


def test_running_a_migration_does_not_silence_application_logging(
    sqlite_url: str,
) -> None:
    """Alembic's env.py calls logging.config.fileConfig, whose default is
    disable_existing_loggers=True. That flips ``disabled`` on every logger
    already configured, so anything migrating in-process — a startup hook, a
    management command, this test suite — logged nothing afterwards.

    Checked with a handler of its own rather than ``caplog``: fileConfig also
    replaces the root handlers, which removes pytest's capturing one, so caplog
    would report silence whether or not the bug were present.
    """
    import io as _io

    from app.logging import get_logger

    logger = get_logger("app.migrations.probe")
    command.upgrade(_config(sqlite_url), "head")

    assert logger.disabled is False, "fileConfig disabled a pre-existing logger"

    stream = _io.StringIO()
    handler = logging.StreamHandler(stream)
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    try:
        logger.warning("still.audible")
    finally:
        logger.removeHandler(handler)
    assert "still.audible" in stream.getvalue()


# -- Full fidelity, on the real engine ----------------------------------------


@pytest.mark.skipif(
    not os.getenv("MIGRATION_TEST_DATABASE_URL"),
    reason="set MIGRATION_TEST_DATABASE_URL to a scratch PostgreSQL to run",
)
def test_postgres_schema_matches_the_models_exactly() -> None:
    """Types, defaults, and indexes too — SQLite reflection cannot check those.

    Destructive: it drops and recreates the public schema, so point it only at
    a throwaway database.
    """
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from sqlalchemy import text

    url = os.environ["MIGRATION_TEST_DATABASE_URL"]
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))

        command.upgrade(_config(url), "head")

        with engine.connect() as conn:
            context = MigrationContext.configure(
                conn, opts={"compare_type": True, "compare_server_default": True}
            )
            differences = compare_metadata(context, Base.metadata)
    finally:
        engine.dispose()

    assert differences == [], f"migrated schema differs from the models: {differences}"
