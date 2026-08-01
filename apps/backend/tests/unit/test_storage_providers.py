"""Unit tests for the storage provider layer.

These never touch a network: they cover registry wiring, key handling, error
translation and the optional-dependency guards. Real S3 round trips live in
``tests/integration/test_storage_s3.py``, which runs against MinIO.
"""

from __future__ import annotations

import pytest
from app.core.storage import (
    AzureStorageProvider,
    GCSStorageProvider,
    LocalStorageProvider,
    S3StorageProvider,
    StorageProvider,
    create_storage_client,
)
from app.core.storage.interfaces import S3_COMPATIBLE, StorageClient
from app.exceptions.base import StorageError

pytestmark = pytest.mark.asyncio


# -- Registry / configuration -------------------------------------------------
async def test_every_configurable_backend_is_registered() -> None:
    """Settings accept a set of backends; each must actually construct.

    ``storage_backend`` previously allowed "gcs" and "azure" while the enum had
    no such members, so configuring either passed validation and then raised a
    ValueError at first use.
    """
    from typing import get_args

    from app.config.settings import Settings

    allowed = get_args(Settings.model_fields["storage_backend"].annotation)
    for value in allowed:
        provider = StorageProvider(value)  # must not raise
        client = create_storage_client(provider)
        assert client is not None


async def test_provider_enum_covers_settings_literal() -> None:
    from typing import get_args

    from app.config.settings import Settings

    allowed = set(get_args(Settings.model_fields["storage_backend"].annotation))
    assert allowed == {p.value for p in StorageProvider}


async def test_s3_compatible_set() -> None:
    expected = {StorageProvider.S3, StorageProvider.MINIO, StorageProvider.R2}
    assert expected == S3_COMPATIBLE


@pytest.mark.parametrize(
    ("provider", "expected"),
    [
        (StorageProvider.LOCAL, LocalStorageProvider),
        (StorageProvider.S3, S3StorageProvider),
        (StorageProvider.MINIO, S3StorageProvider),
        (StorageProvider.R2, S3StorageProvider),
        (StorageProvider.GCS, GCSStorageProvider),
        (StorageProvider.AZURE, AzureStorageProvider),
    ],
)
async def test_factory_returns_the_right_class(
    provider: StorageProvider, expected: type
) -> None:
    assert isinstance(create_storage_client(provider), expected)


@pytest.mark.parametrize(
    "provider",
    [StorageProvider.S3, StorageProvider.MINIO, StorageProvider.R2, StorageProvider.GCS],
)
async def test_providers_satisfy_the_protocol(provider: StorageProvider) -> None:
    assert isinstance(create_storage_client(provider), StorageClient)


async def test_minio_uses_path_style_addressing() -> None:
    """MinIO cannot serve virtual-host style buckets; AWS defaults to it."""
    minio = create_storage_client(StorageProvider.MINIO)
    aws = create_storage_client(StorageProvider.S3)
    assert minio._force_path_style is True
    assert aws._force_path_style is False


# -- Key handling -------------------------------------------------------------
@pytest.mark.parametrize(
    "provider_cls", [S3StorageProvider, GCSStorageProvider, AzureStorageProvider]
)
def test_leading_slashes_are_stripped(provider_cls: type) -> None:
    assert provider_cls._normalise("/a/b.txt") == "a/b.txt"
    assert provider_cls._normalise("a/b.txt") == "a/b.txt"


@pytest.mark.parametrize(
    "provider_cls", [S3StorageProvider, GCSStorageProvider, AzureStorageProvider]
)
@pytest.mark.parametrize("bad", ["", "/", "///"])
def test_empty_keys_are_rejected(provider_cls: type, bad: str) -> None:
    with pytest.raises(StorageError):
        provider_cls._normalise(bad)


# -- Error translation --------------------------------------------------------
@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("NoSuchKey", True),
        ("NoSuchBucket", True),
        ("404", True),
        ("NotFound", True),
        ("AccessDenied", False),
        ("InternalError", False),
    ],
)
def test_s3_missing_object_detection(code: str, expected: bool) -> None:
    exc = Exception()
    exc.response = {"Error": {"Code": code}}  # type: ignore[attr-defined]
    assert S3StorageProvider._is_missing(exc) is expected


def test_s3_missing_detection_tolerates_a_plain_exception() -> None:
    """A non-botocore error must not be mistaken for a 404."""
    assert S3StorageProvider._is_missing(ValueError("boom")) is False


def test_azure_missing_object_detection() -> None:
    class ResourceNotFoundError(Exception):
        pass

    assert AzureStorageProvider._is_missing(ResourceNotFoundError()) is True
    assert AzureStorageProvider._is_missing(ValueError()) is False


# -- Optional dependency guards ----------------------------------------------
def test_missing_sdk_gives_an_actionable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Absent extras must explain the fix, not raise ModuleNotFoundError."""
    import builtins

    from app.core.storage import azure as azure_mod
    from app.core.storage import gcs as gcs_mod
    from app.core.storage import s3 as s3_mod

    real_import = builtins.__import__

    def blocked(name: str, *args: object, **kwargs: object) -> object:
        if name.split(".")[0] in {"aioboto3", "google", "azure"}:
            raise ModuleNotFoundError(name)
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", blocked)

    for require, extra in (
        (s3_mod._require_aioboto3, "s3"),
        (gcs_mod._require_gcs, "gcs"),
        (azure_mod._require_azure, "azure"),
    ):
        with pytest.raises(StorageError) as info:
            require()
        assert f'".[{extra}]"' in str(info.value)


async def test_azure_reports_the_missing_sdk_before_anything_else() -> None:
    """With no extra installed, that is the blocker worth reporting first."""
    provider = AzureStorageProvider(account_url=None, connection_string=None)
    with pytest.raises(StorageError) as info:
        provider._service()
    message = str(info.value)
    assert 'pip install -e ".[azure]"' in message or "STORAGE_AZURE" in message


async def test_azure_without_credentials_is_a_clear_error() -> None:
    """Only meaningful once the SDK is present, so skip when it is not."""
    pytest.importorskip("azure.storage.blob")
    provider = AzureStorageProvider(account_url=None, connection_string=None)
    with pytest.raises(StorageError, match="STORAGE_AZURE"):
        provider._service()


# -- Health checks fail closed ------------------------------------------------
@pytest.mark.parametrize(
    "provider", [StorageProvider.S3, StorageProvider.GCS, StorageProvider.AZURE]
)
async def test_health_check_reports_false_when_unreachable(
    provider: StorageProvider,
) -> None:
    """An unconfigured cloud backend must report unhealthy, not raise."""
    client = create_storage_client(provider)
    assert await client.health_check() is False
