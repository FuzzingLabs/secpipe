"""
Storage abstraction layer for FuzzForge.

Provides unified interface for storing and retrieving targets and results.
"""

from .base import StorageBackend
from .s3_cached import S3CachedStorage

__all__ = ["StorageBackend", "S3CachedStorage"]
