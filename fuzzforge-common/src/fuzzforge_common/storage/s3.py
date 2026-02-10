from __future__ import annotations

from pathlib import Path, PurePath
from tarfile import TarInfo
from tarfile import open as Archive  # noqa: N812
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Any, cast

from botocore.exceptions import ClientError

from fuzzforge_common.storage.exceptions import StorageDeletionError, StorageDownloadError, StorageUploadError

if TYPE_CHECKING:
    from botocore.client import BaseClient
    from structlog.stdlib import BoundLogger


def get_logger() -> BoundLogger:
    """Get structlog logger instance.

    Uses deferred import pattern required by Temporal for serialization.

    :returns: Configured structlog logger.

    """
    from structlog import get_logger  # noqa: PLC0415 (required by temporal)

    return cast("BoundLogger", get_logger())


class Storage:
    """S3-compatible storage backend implementation using boto3.

    Supports MinIO, AWS S3, and other S3-compatible storage services.
    Uses error-driven approach (EAFP) to handle bucket creation and
    avoid race conditions.

    """

    #: S3 endpoint URL (e.g., "http://localhost:9000" for MinIO).
    __endpoint: str

    #: S3 access key ID for authentication.
    __access_key: str

    #: S3 secret access key for authentication.
    __secret_key: str

    def __init__(self, endpoint: str, access_key: str, secret_key: str) -> None:
        """Initialize an instance of the class.

        :param endpoint: TODO.
        :param access_key: TODO.
        :param secret_key: TODO.

        """
        self.__endpoint = endpoint
        self.__access_key = access_key
        self.__secret_key = secret_key

    def _get_client(self) -> BaseClient:
        """Create boto3 S3 client with configured credentials.

        Uses deferred import pattern required by Temporal for serialization.

        :returns: Configured boto3 S3 client.

        """
        import boto3  # noqa: PLC0415 (required by temporal)

        return boto3.client(
            "s3",
            endpoint_url=self.__endpoint,
            aws_access_key_id=self.__access_key,
            aws_secret_access_key=self.__secret_key,
        )

    def create_bucket(self, bucket: str) -> None:
        """Create the S3 bucket if it does not already exist.

        Idempotent operation - succeeds if bucket already exists and is owned by you.
        Fails if bucket exists but is owned by another account.

        :raise ClientError: If bucket creation fails (permissions, name conflicts, etc.).

        """
        logger = get_logger()
        client = self._get_client()

        logger.debug("creating_bucket", bucket=bucket)

        try:
            client.create_bucket(Bucket=bucket)
            logger.info("bucket_created", bucket=bucket)

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")

            # Bucket already exists and we own it - this is fine
            if error_code in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
                logger.debug(
                    "bucket_already_exists",
                    bucket=bucket,
                    error_code=error_code,
                )
                return

            # Other errors are actual failures
            logger.exception(
                "bucket_creation_failed",
                bucket=bucket,
                error_code=error_code,
            )
            raise

    def delete_bucket(self, bucket: str) -> None:
        """Delete an S3 bucket and all its contents.

        Idempotent operation - succeeds if bucket doesn't exist.
        Handles pagination for buckets with many objects.

        :param bucket: The name of the bucket to delete.
        :raises StorageDeletionError: If bucket deletion fails.

        """
        logger = get_logger()
        client = self._get_client()

        logger.debug("deleting_bucket", bucket=bucket)

        try:
            # S3 requires bucket to be empty before deletion
            # Delete all objects first with pagination support
            continuation_token = None

            while True:
                # List objects (up to 1000 per request)
                list_params = {"Bucket": bucket}
                if continuation_token:
                    list_params["ContinuationToken"] = continuation_token

                response = client.list_objects_v2(**list_params)

                # Delete objects if any exist (max 1000 per delete_objects call)
                if "Contents" in response:
                    objects = [{"Key": obj["Key"]} for obj in response["Contents"]]
                    client.delete_objects(Bucket=bucket, Delete={"Objects": objects})
                    logger.debug("deleted_objects", bucket=bucket, count=len(objects))

                # Check if more objects exist
                if not response.get("IsTruncated", False):
                    break

                continuation_token = response.get("NextContinuationToken")

            # Now delete the empty bucket
            client.delete_bucket(Bucket=bucket)
            logger.info("bucket_deleted", bucket=bucket)

        except ClientError as error:
            error_code = error.response.get("Error", {}).get("Code")

            # Idempotent - bucket already doesn't exist
            if error_code == "NoSuchBucket":
                logger.debug("bucket_does_not_exist", bucket=bucket)
                return

            # Other errors are actual failures
            logger.exception(
                "bucket_deletion_failed",
                bucket=bucket,
                error_code=error_code,
            )
            raise StorageDeletionError(bucket=bucket, reason=str(error)) from error

    def upload_file(
        self,
        bucket: str,
        file: Path,
        key: str,
    ) -> None:
        """Upload archive file to S3 storage at specified object key.

        Assumes bucket exists. Fails gracefully if bucket or other resources missing.

        :param bucket: TODO.
        :param file: Local path to the archive file to upload.
        :param key: Object key (path) in S3 where file should be uploaded.
        :raise StorageUploadError: If upload operation fails.

        """
        from boto3.exceptions import S3UploadFailedError  # noqa: PLC0415 (required by 'temporal' at runtime)

        logger = get_logger()
        client = self._get_client()

        logger.debug(
            "uploading_archive_to_storage",
            bucket=bucket,
            object_key=key,
            archive_path=str(file),
        )

        try:
            client.upload_file(
                Filename=str(file),
                Bucket=bucket,
                Key=key,
            )
            logger.info(
                "archive_uploaded_successfully",
                bucket=bucket,
                object_key=key,
            )

        except S3UploadFailedError as e:
            # Check if this is a NoSuchBucket error - create bucket and retry
            if "NoSuchBucket" in str(e):
                logger.info(
                    "bucket_does_not_exist_creating",
                    bucket=bucket,
                )
                self.create_bucket(bucket=bucket)
                # Retry upload after creating bucket
                try:
                    client.upload_file(
                        Filename=str(file),
                        Bucket=bucket,
                        Key=key,
                    )
                    logger.info(
                        "archive_uploaded_successfully_after_bucket_creation",
                        bucket=bucket,
                        object_key=key,
                    )
                except S3UploadFailedError as retry_error:
                    logger.exception(
                        "upload_failed_after_bucket_creation",
                        bucket=bucket,
                        object_key=key,
                    )
                    raise StorageUploadError(
                        bucket=bucket,
                        object_key=key,
                        reason=str(retry_error),
                    ) from retry_error
            else:
                logger.exception(
                    "upload_failed",
                    bucket=bucket,
                    object_key=key,
                )
                raise StorageUploadError(
                    bucket=bucket,
                    object_key=key,
                    reason=str(e),
                ) from e

    def download_file(self, bucket: str, key: PurePath) -> Path:
        """Download a single file from S3 storage.

        Downloads the file to a temporary location and returns the path.

        :param bucket: S3 bucket name.
        :param key: Object key (path) in S3 to download.
        :returns: Path to the downloaded file.
        :raise StorageDownloadError: If download operation fails.

        """
        logger = get_logger()
        client = self._get_client()

        logger.debug(
            "downloading_file_from_storage",
            bucket=bucket,
            object_key=str(key),
        )

        try:
            # Create temporary file for download
            with NamedTemporaryFile(delete=False, suffix=".tar.gz") as temp_file:
                temp_path = Path(temp_file.name)

            # Download object to temp file
            client.download_file(
                Bucket=bucket,
                Key=str(key),
                Filename=str(temp_path),
            )

            logger.info(
                "file_downloaded_successfully",
                bucket=bucket,
                object_key=str(key),
                local_path=str(temp_path),
            )

            return temp_path

        except ClientError as error:
            error_code = error.response.get("Error", {}).get("Code")
            logger.exception(
                "download_failed",
                bucket=bucket,
                object_key=str(key),
                error_code=error_code,
            )
            raise StorageDownloadError(
                bucket=bucket,
                object_key=str(key),
                reason=f"{error_code}: {error!s}",
            ) from error

    def download_directory(self, bucket: str, directory: PurePath) -> Path:
        """TODO.

        :param bucket: TODO.
        :param directory: TODO.
        :returns: TODO.

        """
        with NamedTemporaryFile(delete=False) as file:
            path: Path = Path(file.name)
        # end-with
        client: Any = self._get_client()
        with Archive(name=str(path), mode="w:gz") as archive:
            paginator = client.get_paginator("list_objects_v2")
            try:
                pages = paginator.paginate(Bucket=bucket, Prefix=str(directory))
            except ClientError as exception:
                raise StorageDownloadError(
                    bucket=bucket,
                    object_key=str(directory),
                    reason=exception.response["Error"]["Code"],
                ) from exception
            for page in pages:
                for entry in page.get("Contents", []):
                    key: str = entry["Key"]
                    try:
                        response: dict[str, Any] = client.get_object(Bucket=bucket, Key=key)
                    except ClientError as exception:
                        raise StorageDownloadError(
                            bucket=bucket,
                            object_key=key,
                            reason=exception.response["Error"]["Code"],
                        ) from exception
                    archive.addfile(TarInfo(name=key), fileobj=response["Body"])
                # end-for
            # end-for
        # end-with
        return path
