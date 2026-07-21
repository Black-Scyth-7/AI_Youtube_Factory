"""Storage provider abstraction layer.

Registers the built-in local provider on import. Cloud providers (S3, MinIO, R2,
GCS, Azure) register their own factories behind the same interface.
"""

from app.core.storage.factory import (
    create_storage_client,
    register_storage,
)
from app.core.storage.interfaces import (
    StorageClient,
    StorageProvider,
    StoredObject,
)
from app.core.storage.local import LocalStorageProvider, create_local_storage
from app.core.storage.media import (
    ALLOWED_MIME_TYPES,
    compute_sha256,
    guess_mime_type,
    validate_mime_type,
)

# Register the local provider so it is available out of the box.
register_storage(StorageProvider.LOCAL, create_local_storage)


def get_storage() -> StorageClient:
    """Return a storage client for the configured backend."""
    from typing import cast

    from app.config import settings

    return cast(
        StorageClient,
        create_storage_client(StorageProvider(settings.storage_backend)),
    )


__all__ = [
    "ALLOWED_MIME_TYPES",
    "LocalStorageProvider",
    "StorageClient",
    "StorageProvider",
    "StoredObject",
    "compute_sha256",
    "create_local_storage",
    "create_storage_client",
    "get_storage",
    "guess_mime_type",
    "register_storage",
    "validate_mime_type",
]
