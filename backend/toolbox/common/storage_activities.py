"""
FuzzForge Common Storage Activities

Activities for interacting with MinIO storage:
- get_target_activity: Download target from MinIO to local cache
- cleanup_cache_activity: Remove target from local cache
- upload_results_activity: Upload workflow results to MinIO
"""

import logging
import os
import shutil
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from temporalio import activity

# Configure logging
logger = logging.getLogger(__name__)

# Initialize S3 client (MinIO)
s3_client = boto3.client(
    's3',
    endpoint_url=os.getenv('S3_ENDPOINT', 'http://minio:9000'),
    aws_access_key_id=os.getenv('S3_ACCESS_KEY', 'fuzzforge'),
    aws_secret_access_key=os.getenv('S3_SECRET_KEY', 'fuzzforge123'),
    region_name=os.getenv('S3_REGION', 'us-east-1'),
    use_ssl=os.getenv('S3_USE_SSL', 'false').lower() == 'true'
)

# Configuration
S3_BUCKET = os.getenv('S3_BUCKET', 'targets')
CACHE_DIR = Path(os.getenv('CACHE_DIR', '/cache'))
CACHE_MAX_SIZE_GB = int(os.getenv('CACHE_MAX_SIZE', '10').rstrip('GB'))


@activity.defn(name="get_target")
async def get_target_activity(
    target_id: str,
    run_id: str = None,
    workspace_isolation: str = "isolated"
) -> str:
    """
    Download target from MinIO to local cache.

    Args:
        target_id: UUID of the uploaded target
        run_id: Workflow run ID for isolation (required for isolated mode)
        workspace_isolation: Isolation mode - "isolated" (default), "shared", or "copy-on-write"

    Returns:
        Local path to the cached target workspace

    Raises:
        FileNotFoundError: If target doesn't exist in MinIO
        ValueError: If run_id not provided for isolated mode
        Exception: For other download errors
    """
    logger.info(
        f"Activity: get_target (target_id={target_id}, run_id={run_id}, "
        f"isolation={workspace_isolation})"
    )

    # Validate isolation mode
    valid_modes = ["isolated", "shared", "copy-on-write"]
    if workspace_isolation not in valid_modes:
        raise ValueError(
            f"Invalid workspace_isolation mode: {workspace_isolation}. "
            f"Must be one of: {valid_modes}"
        )

    # Require run_id for isolated and copy-on-write modes
    if workspace_isolation in ["isolated", "copy-on-write"] and not run_id:
        raise ValueError(
            f"run_id is required for workspace_isolation='{workspace_isolation}'"
        )

    # Define cache paths based on isolation mode
    if workspace_isolation == "isolated":
        # Each run gets its own isolated workspace
        cache_path = CACHE_DIR / target_id / run_id
        cached_file = cache_path / "target"
    elif workspace_isolation == "shared":
        # All runs share the same workspace (legacy behavior)
        cache_path = CACHE_DIR / target_id
        cached_file = cache_path / "target"
    else:  # copy-on-write
        # Shared download, run-specific copy
        shared_cache_path = CACHE_DIR / target_id / "shared"
        cache_path = CACHE_DIR / target_id / run_id
        cached_file = shared_cache_path / "target"

    # Handle copy-on-write mode
    if workspace_isolation == "copy-on-write":
        # Check if shared cache exists
        if cached_file.exists():
            logger.info(f"Copy-on-write: Shared cache HIT for {target_id}")

            # Copy shared workspace to run-specific path
            shared_workspace = shared_cache_path / "workspace"
            run_workspace = cache_path / "workspace"

            if shared_workspace.exists():
                logger.info(f"Copying workspace to isolated run path: {run_workspace}")
                cache_path.mkdir(parents=True, exist_ok=True)
                shutil.copytree(shared_workspace, run_workspace)
                return str(run_workspace)
            else:
                # Shared file exists but not extracted (non-tarball)
                run_file = cache_path / "target"
                cache_path.mkdir(parents=True, exist_ok=True)
                shutil.copy2(cached_file, run_file)
                return str(run_file)
        # If shared cache doesn't exist, fall through to download

    # Check if target is already cached (isolated or shared mode)
    elif cached_file.exists():
        # Update access time for LRU
        cached_file.touch()
        logger.info(f"Cache HIT: {target_id} (mode: {workspace_isolation})")

        # Check if workspace directory exists (extracted tarball)
        workspace_dir = cache_path / "workspace"
        if workspace_dir.exists() and workspace_dir.is_dir():
            logger.info(f"Returning cached workspace: {workspace_dir}")
            return str(workspace_dir)
        else:
            # Return cached file (not a tarball)
            return str(cached_file)

    # Cache miss - download from MinIO
    logger.info(
        f"Cache MISS: {target_id} (mode: {workspace_isolation}), "
        f"downloading from MinIO..."
    )

    try:
        # Create cache directory
        cache_path.mkdir(parents=True, exist_ok=True)

        # Download from S3/MinIO
        s3_key = f'{target_id}/target'
        logger.info(f"Downloading s3://{S3_BUCKET}/{s3_key} -> {cached_file}")

        s3_client.download_file(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Filename=str(cached_file)
        )

        # Verify file was downloaded
        if not cached_file.exists():
            raise FileNotFoundError(f"Downloaded file not found: {cached_file}")

        file_size = cached_file.stat().st_size
        logger.info(
            f"✓ Downloaded target {target_id} "
            f"({file_size / 1024 / 1024:.2f} MB)"
        )

        # Extract tarball if it's an archive
        import tarfile
        workspace_dir = cache_path / "workspace"

        if tarfile.is_tarfile(str(cached_file)):
            logger.info(f"Extracting tarball to {workspace_dir}...")
            workspace_dir.mkdir(parents=True, exist_ok=True)

            with tarfile.open(str(cached_file), 'r:*') as tar:
                tar.extractall(path=workspace_dir)

            logger.info(f"✓ Extracted tarball to {workspace_dir}")

            # For copy-on-write mode, copy to run-specific path
            if workspace_isolation == "copy-on-write":
                run_cache_path = CACHE_DIR / target_id / run_id
                run_workspace = run_cache_path / "workspace"
                logger.info(f"Copy-on-write: Copying to {run_workspace}")
                run_cache_path.mkdir(parents=True, exist_ok=True)
                shutil.copytree(workspace_dir, run_workspace)
                return str(run_workspace)

            return str(workspace_dir)
        else:
            # Not a tarball
            if workspace_isolation == "copy-on-write":
                # Copy file to run-specific path
                run_cache_path = CACHE_DIR / target_id / run_id
                run_file = run_cache_path / "target"
                logger.info(f"Copy-on-write: Copying file to {run_file}")
                run_cache_path.mkdir(parents=True, exist_ok=True)
                shutil.copy2(cached_file, run_file)
                return str(run_file)

            return str(cached_file)

    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404' or error_code == 'NoSuchKey':
            logger.error(f"Target not found in MinIO: {target_id}")
            raise FileNotFoundError(f"Target {target_id} not found in storage")
        else:
            logger.error(f"S3/MinIO error downloading target: {e}", exc_info=True)
            raise

    except Exception as e:
        logger.error(f"Failed to download target {target_id}: {e}", exc_info=True)
        # Cleanup partial download
        if cache_path.exists():
            shutil.rmtree(cache_path, ignore_errors=True)
        raise


@activity.defn(name="cleanup_cache")
async def cleanup_cache_activity(
    target_path: str,
    workspace_isolation: str = "isolated"
) -> None:
    """
    Remove target from local cache after workflow completes.

    Args:
        target_path: Path to the cached target workspace (from get_target_activity)
        workspace_isolation: Isolation mode used - determines cleanup scope

    Notes:
        - "isolated" mode: Removes the entire run-specific directory
        - "copy-on-write" mode: Removes run-specific directory, keeps shared cache
        - "shared" mode: Does NOT remove cache (shared across runs)
    """
    logger.info(
        f"Activity: cleanup_cache (path={target_path}, "
        f"isolation={workspace_isolation})"
    )

    try:
        target = Path(target_path)

        # For shared mode, don't clean up (cache is shared across runs)
        if workspace_isolation == "shared":
            logger.info(
                f"Skipping cleanup for shared workspace (mode={workspace_isolation})"
            )
            return

        # For isolated and copy-on-write modes, clean up run-specific directory
        # Navigate up to the run-specific directory: /cache/{target_id}/{run_id}/
        if target.name == "workspace":
            # Path is .../workspace, go up one level to run directory
            run_dir = target.parent
        else:
            # Path is a file, go up one level to run directory
            run_dir = target.parent

        # Validate it's in cache and looks like a run-specific path
        if run_dir.exists() and run_dir.is_relative_to(CACHE_DIR):
            # Check if parent is target_id directory (validate structure)
            target_id_dir = run_dir.parent
            if target_id_dir.is_relative_to(CACHE_DIR):
                shutil.rmtree(run_dir)
                logger.info(
                    f"✓ Cleaned up run-specific directory: {run_dir} "
                    f"(mode={workspace_isolation})"
                )
            else:
                logger.warning(
                    f"Unexpected cache structure, skipping cleanup: {run_dir}"
                )
        else:
            logger.warning(
                f"Cache path not in CACHE_DIR or doesn't exist: {run_dir}"
            )

    except Exception as e:
        # Don't fail workflow if cleanup fails
        logger.error(
            f"Failed to cleanup cache {target_path}: {e}",
            exc_info=True
        )


@activity.defn(name="upload_results")
async def upload_results_activity(
    workflow_id: str,
    results: dict,
    results_format: str = "json"
) -> str:
    """
    Upload workflow results to MinIO.

    Args:
        workflow_id: Workflow execution ID
        results: Results dictionary to upload
        results_format: Format for results (json, sarif, etc.)

    Returns:
        S3 URL to the uploaded results
    """
    logger.info(
        f"Activity: upload_results "
        f"(workflow_id={workflow_id}, format={results_format})"
    )

    try:
        import json

        # Prepare results content
        if results_format == "json":
            content = json.dumps(results, indent=2).encode('utf-8')
            content_type = 'application/json'
            file_ext = 'json'
        elif results_format == "sarif":
            content = json.dumps(results, indent=2).encode('utf-8')
            content_type = 'application/sarif+json'
            file_ext = 'sarif'
        else:
            # Default to JSON
            content = json.dumps(results, indent=2).encode('utf-8')
            content_type = 'application/json'
            file_ext = 'json'

        # Upload to MinIO
        s3_key = f'{workflow_id}/results.{file_ext}'
        logger.info(f"Uploading results to s3://results/{s3_key}")

        s3_client.put_object(
            Bucket='results',
            Key=s3_key,
            Body=content,
            ContentType=content_type,
            Metadata={
                'workflow_id': workflow_id,
                'format': results_format
            }
        )

        # Construct S3 URL
        s3_endpoint = os.getenv('S3_ENDPOINT', 'http://minio:9000')
        s3_url = f"{s3_endpoint}/results/{s3_key}"

        logger.info(f"✓ Uploaded results: {s3_url}")
        return s3_url

    except Exception as e:
        logger.error(
            f"Failed to upload results for workflow {workflow_id}: {e}",
            exc_info=True
        )
        raise


def _check_cache_size():
    """Check total cache size and log warning if exceeding limit"""
    try:
        total_size = 0
        for item in CACHE_DIR.rglob('*'):
            if item.is_file():
                total_size += item.stat().st_size

        total_size_gb = total_size / (1024 ** 3)
        if total_size_gb > CACHE_MAX_SIZE_GB:
            logger.warning(
                f"Cache size ({total_size_gb:.2f} GB) exceeds "
                f"limit ({CACHE_MAX_SIZE_GB} GB). Consider cleanup."
            )

    except Exception as e:
        logger.error(f"Failed to check cache size: {e}")
