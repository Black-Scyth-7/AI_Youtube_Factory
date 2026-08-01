# Storage

Object storage sits behind one `StorageClient` Protocol, so application code
never knows which backend it is talking to. Five providers implement it: the
local filesystem, any S3-compatible service, Google Cloud Storage and Azure Blob
Storage.

## Choosing a backend

```bash
STORAGE_BACKEND=local   # local | s3 | minio | r2 | gcs | azure
```

Cloud SDKs are **optional dependencies** — the default local backend needs none
of them, and a deployment installs only what it uses:

```bash
pip install -e ".[s3]"       # AWS S3, MinIO, Cloudflare R2
pip install -e ".[gcs]"      # Google Cloud Storage
pip install -e ".[azure]"    # Azure Blob Storage
pip install -e ".[storage]"  # all of them
```

Providers register at import, but their SDKs load only when an operation runs.
Selecting a backend whose extra is missing therefore fails on first use with the
install command in the message, rather than at startup.

## The contract

Every provider implements:

| Method                              | Behaviour                                      |
| ----------------------------------- | ---------------------------------------------- |
| `put(key, data, content_type)`      | Store bytes, return `StoredObject` metadata    |
| `get(key)`                          | Return bytes; raises `NotFoundError` if absent |
| `delete(key)`                       | Delete; **absent objects are not an error**    |
| `presign_url(key, expires_in=3600)` | Temporary download URL                         |
| `exists(key)`                       | Boolean                                        |
| `health_check()`                    | Boolean; never raises                          |

Keys are normalised the same way everywhere: a leading `/` is stripped, so
`/a/b.txt` and `a/b.txt` address the same object. An empty key raises
`StorageError`.

## S3-compatible (S3 · MinIO · R2)

One implementation serves all three — they differ only in endpoint and
addressing style.

```bash
STORAGE_BACKEND=minio
STORAGE_BUCKET=ai-youtube-factory
STORAGE_ENDPOINT_URL=http://localhost:9000   # blank for AWS
STORAGE_ACCESS_KEY=minioadmin
STORAGE_SECRET_KEY=minioadmin
STORAGE_FORCE_PATH_STYLE=true                # MinIO only
```

`STORAGE_FORCE_PATH_STYLE` matters: MinIO cannot serve virtual-host style bucket
addressing, while AWS and R2 expect it. The `minio` backend sets it by default.

For **R2**, point `STORAGE_ENDPOINT_URL` at
`https://<account-id>.r2.cloudflarestorage.com` and leave path style off.

A MinIO service ships in `docker-compose.yml` (API on `:9000`, console on
`:9001`) so local development needs no cloud account.

## Google Cloud Storage

```bash
STORAGE_BACKEND=gcs
STORAGE_BUCKET=ai-youtube-factory
STORAGE_GCS_PROJECT=my-project
STORAGE_GCS_CREDENTIALS_PATH=/secrets/gcs.json   # omit to use ADC
```

`google-cloud-storage` is synchronous, so every call runs in a worker thread —
the event loop is never blocked on network I/O. Signed URLs use v4 signing and
require a service-account key; Application Default Credentials alone cannot sign.

## Azure Blob Storage

```bash
STORAGE_BACKEND=azure
STORAGE_AZURE_CONTAINER=ai-youtube-factory
STORAGE_AZURE_CONNECTION_STRING=...            # or:
STORAGE_AZURE_ACCOUNT_URL=https://acct.blob.core.windows.net
```

Uses the SDK's native async client, so no thread offloading is needed. With a
connection string, `presign_url` returns a SAS URL. With `ACCOUNT_URL` plus
managed identity there is no account key to sign with, so the plain blob URL is
returned and access is governed by the container's own policy — set the
container private and front it with your own signing service if that matters.

## Adding a provider

1. Implement the `StorageClient` methods in `app/core/storage/<name>.py`.
2. Add the identifier to `StorageProvider` **and** to the
   `Settings.storage_backend` literal — a value in one but not the other passes
   configuration validation and then fails when the client is constructed.
   `test_provider_enum_covers_settings_literal` enforces this.
3. Register the factory in `app/core/storage/__init__.py`.
4. Keep the SDK import inside the operation, not at module import.

## Testing

Unit tests (`tests/unit/test_storage_providers.py`) cover registry wiring, key
handling, error translation and the dependency guards. They never touch a
network and always run.

Integration tests (`tests/integration/test_storage_s3.py`) exercise a real S3
round trip and are skipped unless an endpoint is configured:

```bash
docker compose up -d minio
STORAGE_ENDPOINT_URL=http://localhost:9000 \
STORAGE_ACCESS_KEY=minioadmin STORAGE_SECRET_KEY=minioadmin \
pytest tests/integration/test_storage_s3.py
```

They verify byte-exact round trips, overwrite semantics, `NotFoundError` on a
missing key, delete-absent being a no-op, and that a presigned URL is genuinely
fetchable over HTTP without credentials.
