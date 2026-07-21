"""Application dependency-injection container.

Wires shared singletons — settings, the database engine + session factory, and
the infrastructure services (cache, event bus, storage, task queue) — using
``dependency-injector``. Request-scoped objects (repositories, services that need
a session) are constructed per request from the session dependency, not here.
"""

from __future__ import annotations

from dependency_injector import containers, providers

from app.config import Settings, get_settings
from app.core.cache import get_cache
from app.core.events import get_event_bus
from app.core.storage import get_storage
from app.core.tasks import get_task_queue
from app.db.session import create_engine, create_session_factory


class Container(containers.DeclarativeContainer):
    """Root DI container for the backend."""

    wiring_config = containers.WiringConfiguration(
        packages=["app.api", "app.services", "app.dependencies"]
    )

    settings: providers.Provider[Settings] = providers.Singleton(get_settings)

    engine = providers.Singleton(create_engine, settings=settings)
    session_factory = providers.Singleton(create_session_factory, engine=engine)

    # Infrastructure singletons (each has its own module-level accessor too).
    cache = providers.Singleton(get_cache)
    event_bus = providers.Singleton(get_event_bus)
    storage = providers.Singleton(get_storage)
    task_queue = providers.Singleton(get_task_queue)


def build_container() -> Container:
    """Instantiate and return a fully-initialised container."""
    return Container()
