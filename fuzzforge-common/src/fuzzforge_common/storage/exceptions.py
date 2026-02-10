from fuzzforge_common.exceptions import FuzzForgeError


class FuzzForgeStorageError(FuzzForgeError):
    """Base exception for all storage-related errors.

    Raised when storage operations (upload, download, connection) fail
    during workflow execution.

    """


class StorageConnectionError(FuzzForgeStorageError):
    """Failed to connect to storage service.

    :param endpoint: The storage endpoint that failed to connect.
    :param reason: The underlying exception message.

    """

    def __init__(self, endpoint: str, reason: str) -> None:
        """Initialize storage connection error.

        :param endpoint: The storage endpoint that failed to connect.
        :param reason: The underlying exception message.

        """
        FuzzForgeStorageError.__init__(
            self,
            f"Failed to connect to storage at {endpoint}: {reason}",
        )
        self.endpoint = endpoint
        self.reason = reason


class StorageUploadError(FuzzForgeStorageError):
    """Failed to upload object to storage.

    :param bucket: The target bucket name.
    :param object_key: The target object key.
    :param reason: The underlying exception message.

    """

    def __init__(self, bucket: str, object_key: str, reason: str) -> None:
        """Initialize storage upload error.

        :param bucket: The target bucket name.
        :param object_key: The target object key.
        :param reason: The underlying exception message.

        """
        FuzzForgeStorageError.__init__(
            self,
            f"Failed to upload to {bucket}/{object_key}: {reason}",
        )
        self.bucket = bucket
        self.object_key = object_key
        self.reason = reason


class StorageDownloadError(FuzzForgeStorageError):
    """Failed to download object from storage.

    :param bucket: The source bucket name.
    :param object_key: The source object key.
    :param reason: The underlying exception message.

    """

    def __init__(self, bucket: str, object_key: str, reason: str) -> None:
        """Initialize storage download error.

        :param bucket: The source bucket name.
        :param object_key: The source object key.
        :param reason: The underlying exception message.

        """
        FuzzForgeStorageError.__init__(
            self,
            f"Failed to download from {bucket}/{object_key}: {reason}",
        )
        self.bucket = bucket
        self.object_key = object_key
        self.reason = reason


class StorageDeletionError(FuzzForgeStorageError):
    """Failed to delete bucket from storage.

    :param bucket: The bucket name that failed to delete.
    :param reason: The underlying exception message.

    """

    def __init__(self, bucket: str, reason: str) -> None:
        """Initialize storage deletion error.

        :param bucket: The bucket name that failed to delete.
        :param reason: The underlying exception message.

        """
        FuzzForgeStorageError.__init__(
            self,
            f"Failed to delete bucket {bucket}: {reason}",
        )
        self.bucket = bucket
        self.reason = reason
