"""Base storage backend interface.

All storage implementations must implement this interface.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class StorageBackend(ABC):
    """Abstract base class for storage backends.

    Implementations handle storage and retrieval of:
    - Uploaded targets (code, binaries, etc.)
    - Workflow results
    - Temporary files
    """

    @abstractmethod
    async def upload_target(
        self,
        file_path: Path,
        user_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Upload a target file to storage.

        Args:
            file_path: Local path to file to upload
            user_id: ID of user uploading the file
            metadata: Optional metadata to store with file

        Returns:
            Target ID (unique identifier for retrieval)

        Raises:
            FileNotFoundError: If file_path doesn't exist
            StorageError: If upload fails

        """

    @abstractmethod
    async def get_target(self, target_id: str) -> Path:
        """Get target file from storage.

        Args:
            target_id: Unique identifier from upload_target()

        Returns:
            Local path to cached file

        Raises:
            FileNotFoundError: If target doesn't exist
            StorageError: If download fails

        """

    @abstractmethod
    async def delete_target(self, target_id: str) -> None:
        """Delete target from storage.

        Args:
            target_id: Unique identifier to delete

        Raises:
            StorageError: If deletion fails (doesn't raise if not found)

        """

    @abstractmethod
    async def upload_results(
        self,
        workflow_id: str,
        results: dict[str, Any],
        results_format: str = "json",
    ) -> str:
        """Upload workflow results to storage.

        Args:
            workflow_id: Workflow execution ID
            results: Results dictionary
            results_format: Format (json, sarif, etc.)

        Returns:
            URL to uploaded results

        Raises:
            StorageError: If upload fails

        """

    @abstractmethod
    async def get_results(self, workflow_id: str) -> dict[str, Any]:
        """Get workflow results from storage.

        Args:
            workflow_id: Workflow execution ID

        Returns:
            Results dictionary

        Raises:
            FileNotFoundError: If results don't exist
            StorageError: If download fails

        """

    @abstractmethod
    async def list_targets(
        self,
        user_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List uploaded targets.

        Args:
            user_id: Filter by user ID (None = all users)
            limit: Maximum number of results

        Returns:
            List of target metadata dictionaries

        Raises:
            StorageError: If listing fails

        """

    @abstractmethod
    async def cleanup_cache(self) -> int:
        """Clean up local cache (LRU eviction).

        Returns:
            Number of files removed

        Raises:
            StorageError: If cleanup fails

        """


class StorageError(Exception):
    """Base exception for storage operations."""
