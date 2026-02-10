from pydantic import BaseModel

from fuzzforge_common.storage.s3 import Storage


class StorageConfiguration(BaseModel):
    """TODO."""

    #: S3 endpoint URL (e.g., "http://localhost:9000" for MinIO).
    endpoint: str

    #: S3 access key ID for authentication.
    access_key: str

    #: S3 secret access key for authentication.
    secret_key: str

    def into_storage(self) -> Storage:
        """TODO."""
        return Storage(endpoint=self.endpoint, access_key=self.access_key, secret_key=self.secret_key)
