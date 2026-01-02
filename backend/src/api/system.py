# Copyright (c) 2025 FuzzingLabs
#
# Licensed under the Business Source License 1.1 (BSL). See the LICENSE file
# at the root of this repository for details.
#
# After the Change Date (four years from publication), this version of the
# Licensed Work will be made available under the Apache License, Version 2.0.
# See the LICENSE-APACHE file or http://www.apache.org/licenses/LICENSE-2.0
#
# Additional attribution and requirements are provided in the NOTICE file.

"""
System information endpoints for FuzzForge API.

Provides system configuration and filesystem paths to CLI for worker management.
"""

import os
from typing import Dict

from fastapi import APIRouter

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/info")
async def get_system_info() -> Dict[str, str]:
    """
    Get system information including host filesystem paths.

    This endpoint exposes paths needed by the CLI to manage workers via docker-compose.
    The FUZZFORGE_HOST_ROOT environment variable is set by docker-compose and points
    to the FuzzForge installation directory on the host machine.

    Returns:
        Dictionary containing:
        - host_root: Absolute path to FuzzForge root on host
        - docker_compose_path: Path to docker-compose.yml on host
        - workers_dir: Path to workers directory on host
    """
    host_root = os.getenv("FUZZFORGE_HOST_ROOT", "")

    return {
        "host_root": host_root,
        "docker_compose_path": f"{host_root}/docker-compose.yml" if host_root else "",
        "workers_dir": f"{host_root}/workers" if host_root else "",
    }


@router.get("/storage/health")
async def get_storage_health() -> Dict:
    """
    Get MinIO storage health and usage statistics.
    
    Returns:
        Dictionary containing:
        - status: 'healthy', 'warning', or 'critical' based on usage
        - buckets: Per-bucket statistics (objects count, size)
        - total_size_gb: Total storage used across all buckets
        - lifecycle_policies_active: Whether lifecycle cleanup is working
    """
    from src.storage import S3CachedStorage
    
    try:
        storage = S3CachedStorage()
        stats = await storage.get_storage_stats()
        
        # Add cache stats
        cache_stats = storage.get_cache_stats()
        
        return {
            "status": stats.get("status", "unknown"),
            "storage": {
                "buckets": stats.get("buckets", {}),
                "total_objects": stats.get("total_objects", 0),
                "total_size_gb": stats.get("total_size_gb", 0),
            },
            "cache": {
                "size_gb": cache_stats.get("total_size_gb", 0),
                "file_count": cache_stats.get("file_count", 0),
                "max_size_gb": cache_stats.get("max_size_gb", 10),
                "usage_percent": cache_stats.get("usage_percent", 0),
            },
            "lifecycle_policies_active": True,  # Assumed if MinIO is responding
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "storage": {},
            "cache": {},
            "lifecycle_policies_active": False,
        }


@router.post("/storage/cleanup")
async def cleanup_storage(
    bucket: str = "targets",
    days_old: int = 7,
    dry_run: bool = True
) -> Dict:
    """
    Clean up old objects from MinIO storage.
    
    Args:
        bucket: Bucket to clean ('targets', 'results', or 'cache')
        days_old: Delete objects older than this many days
        dry_run: If True, only report what would be deleted
        
    Returns:
        Cleanup results including objects found, size to free, and deleted count
    """
    from src.storage import S3CachedStorage
    
    if bucket not in ["targets", "results", "cache"]:
        return {"error": f"Invalid bucket: {bucket}. Must be 'targets', 'results', or 'cache'"}
    
    try:
        storage = S3CachedStorage()
        result = await storage.cleanup_old_objects(
            bucket=bucket,
            days_old=days_old,
            dry_run=dry_run
        )
        return result
    except Exception as e:
        return {
            "error": str(e),
            "bucket": bucket,
            "deleted": 0
        }

