"""FuzzForge storage abstractions.

Storage class requires boto3. Import it explicitly:
    from fuzzforge_common.storage.s3 import Storage
"""

from fuzzforge_common.storage.exceptions import (
    FuzzForgeStorageError,
    StorageConnectionError,
    StorageDownloadError,
    StorageUploadError,
)

__all__ = [
    "FuzzForgeStorageError",
    "StorageConnectionError",
    "StorageDownloadError",
    "StorageUploadError",
]
