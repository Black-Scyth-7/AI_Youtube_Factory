"""Application dependency-injection container.

Wires shared singletons (settings, engine, session factory) using
``dependency-injector``. Route handlers and services resolve their dependencies
from this container rather than importing globals directly, which keeps the
object graph explicit and testable (providers can be overridden in tests).
"""

from __future__ import annotations

from dependency_injector import containers, providers

from app.config import Settings, get_settings
from app.db.session import create_engine, create_session_factory


class Container(containers.DeclarativeContainer):
    """Root DI container for the backend."""

    wiring_config = containers.WiringConfiguration(
        packages=["app.api", "app.services", "app.dependencies"]
    )

    settings: providers.Provider[Settings] = providers.Singleton(get_settings)

    engine = providers.Singleton(create_engine, settings=settings)

    session_factory = providers.Singleton(create_session_factory, engine=engine)


def build_container() -> Container:
    """Instantiate and return a fully-initialised container."""
    container = Container()
    return container
