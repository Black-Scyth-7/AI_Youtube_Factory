"""Storage provider abstraction layer.

Every provider is registered on import. Cloud SDKs are optional dependencies and
are imported only when an operation actually runs, so registering a provider
whose extra is not installed is harmless — the error surfaces on first use, with
the install command in the message.
"""

from app.core.storage.azure import AzureStorageProvider, create_azure_storage
from app.core.storage.factory import (
    create_storage_client,
    register_storage,
)
from app.core.storage.gcs import GCSStorageProvider, create_gcs_storage
from app.core.storage.interfaces import (
    S3_COMPATIBLE,
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
from app.core.storage.s3 import (
    S3StorageProvider,
    create_minio_storage,
    create_r2_storage,
    create_s3_storage,
)

register_storage(StorageProvider.LOCAL, create_local_storage)
register_storage(StorageProvider.S3, create_s3_storage)
register_storage(StorageProvider.MINIO, create_minio_storage)
register_storage(StorageProvider.R2, create_r2_storage)
register_storage(StorageProvider.GCS, create_gcs_storage)
register_storage(StorageProvider.AZURE, create_azure_storage)


def get_storage() -> StorageClient:
    """Return an instrumented storage client for the configured backend.

    Instrumentation is added here rather than in the factory so that
    ``create_storage_client`` keeps returning the concrete provider type.
    """
    from typing import cast

    from app.config import settings
    from app.core.storage.metered import MeteredStorageClient

    backend = StorageProvider(settings.storage_backend)
    return cast(
        StorageClient,
        MeteredStorageClient(create_storage_client(backend), backend.value),
    )


__all__ = [
    "ALLOWED_MIME_TYPES",
    "S3_COMPATIBLE",
    "AzureStorageProvider",
    "GCSStorageProvider",
    "LocalStorageProvider",
    "S3StorageProvider",
    "StorageClient",
    "StorageProvider",
    "StoredObject",
    "compute_sha256",
    "create_azure_storage",
    "create_gcs_storage",
    "create_local_storage",
    "create_minio_storage",
    "create_r2_storage",
    "create_s3_storage",
    "create_storage_client",
    "get_storage",
    "guess_mime_type",
    "register_storage",
    "validate_mime_type",
]
