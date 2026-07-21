"""Storage provider abstraction layer."""

from app.core.storage.factory import create_storage_client, register_storage
from app.core.storage.interfaces import (
    StorageClient,
    StorageProvider,
    StoredObject,
)

__all__ = [
    "StorageClient",
    "StorageProvider",
    "StoredObject",
    "create_storage_client",
    "register_storage",
]
