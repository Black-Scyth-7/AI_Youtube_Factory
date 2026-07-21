"""SQLAlchemy declarative base.

All ORM models inherit from :class:`Base`, which supplies a naming convention
for constraints (so Alembic autogenerates stable, predictable names) and a
default snake-case table name derived from the class name.
"""

from __future__ import annotations

import re

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase, declared_attr

# Deterministic constraint naming keeps Alembic migrations stable across runs.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

_CAMEL_TO_SNAKE = re.compile(r"(?<!^)(?=[A-Z])")


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    @declared_attr.directive
    def __tablename__(cls) -> str:  # noqa: N805
        """Derive a snake_case table name from the class name."""
        return _CAMEL_TO_SNAKE.sub("_", cls.__name__).lower()
