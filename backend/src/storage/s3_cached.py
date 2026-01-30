"""
S3-compatible storage backend with local caching.

Works with MinIO (dev/prod) or AWS S3 (cloud).
"""

import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError

from .base import StorageBackend, StorageError

logger = logging.getLogger(__name__)


class S3CachedStorage(StorageBackend):
    """
    S3-compatible storage with local caching.

    Features:
    - Upload targets to S3/MinIO
    - Download with local caching (LRU eviction)
    - Lifecycle management (auto-cleanup old files)
    - Metadata tracking
    """

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        bucket: str = "targets",
        region: str = "us-east-1",
        use_ssl: bool = False,
        cache_dir: Optional[Path] = None,
        cache_max_size_gb: int = 10
    ):
        """
        Initialize S3 storage backend.

        Args:
            endpoint_url: S3 endpoint (None = AWS S3, or MinIO URL)
            access_key: S3 access key (None = from env)
            secret_key: S3 secret key (None = from env)
            bucket: S3 bucket name
            region: AWS region
            use_ssl: Use HTTPS
            cache_dir: Local cache directory
            cache_max_size_gb: Maximum cache size in GB
        """
        # Use environment variables as defaults
        self.endpoint_url = endpoint_url or os.getenv('S3_ENDPOINT', 'http://minio:9000')
        self.access_key = access_key or os.getenv('S3_ACCESS_KEY', 'fuzzforge')
        self.secret_key = secret_key or os.getenv('S3_SECRET_KEY', 'fuzzforge123')
        self.bucket = bucket or os.getenv('S3_BUCKET', 'targets')
        self.region = region or os.getenv('S3_REGION', 'us-east-1')
        self.use_ssl = use_ssl or os.getenv('S3_USE_SSL', 'false').lower() == 'true'

        # Cache configuration
        self.cache_dir = cache_dir or Path(os.getenv('CACHE_DIR', '/tmp/fuzzforge-cache'))
        self.cache_max_size = cache_max_size_gb * (1024 ** 3)  # Convert to bytes

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Initialize S3 client
        try:
            self.s3_client = boto3.client(
                's3',
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
                use_ssl=self.use_ssl
            )
            logger.info(f"Initialized S3 storage: {self.endpoint_url}/{self.bucket}")
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            raise StorageError(f"S3 initialization failed: {e}")

    async def upload_target(
        self,
        file_path: Path,
        user_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Upload target file to S3/MinIO."""
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Generate unique target ID
        target_id = str(uuid4())

        # Prepare metadata
        upload_metadata = {
            'user_id': user_id,
            'uploaded_at': datetime.now().isoformat(),
            'filename': file_path.name,
            'size': str(file_path.stat().st_size)
        }
        if metadata:
            upload_metadata.update(metadata)

        # Upload to S3
        s3_key = f'{target_id}/target'
        try:
            logger.info(f"Uploading target to s3://{self.bucket}/{s3_key}")

            self.s3_client.upload_file(
                str(file_path),
                self.bucket,
                s3_key,
                ExtraArgs={
                    'Metadata': upload_metadata
                }
            )

            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            logger.info(
                f"✓ Uploaded target {target_id} "
                f"({file_path.name}, {file_size_mb:.2f} MB)"
            )

            return target_id

        except ClientError as e:
            logger.error(f"S3 upload failed: {e}", exc_info=True)
            raise StorageError(f"Failed to upload target: {e}")
        except Exception as e:
            logger.error(f"Upload failed: {e}", exc_info=True)
            raise StorageError(f"Upload error: {e}")

    async def get_target(self, target_id: str) -> Path:
        """Get target from cache or download from S3/MinIO."""
        # Check cache first
        cache_path = self.cache_dir / target_id
        cached_file = cache_path / "target"

        if cached_file.exists():
            # Update access time for LRU
            cached_file.touch()
            logger.info(f"Cache HIT: {target_id}")
            return cached_file

        # Cache miss - download from S3
        logger.info(f"Cache MISS: {target_id}, downloading from S3...")

        try:
            # Create cache directory
            cache_path.mkdir(parents=True, exist_ok=True)

            # Download from S3
            s3_key = f'{target_id}/target'
            logger.info(f"Downloading s3://{self.bucket}/{s3_key}")

            self.s3_client.download_file(
                self.bucket,
                s3_key,
                str(cached_file)
            )

            # Verify download
            if not cached_file.exists():
                raise StorageError(f"Downloaded file not found: {cached_file}")

            file_size_mb = cached_file.stat().st_size / (1024 * 1024)
            logger.info(f"✓ Downloaded target {target_id} ({file_size_mb:.2f} MB)")

            return cached_file

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code in ['404', 'NoSuchKey']:
                logger.error(f"Target not found: {target_id}")
                raise FileNotFoundError(f"Target {target_id} not found in storage")
            else:
                logger.error(f"S3 download failed: {e}", exc_info=True)
                raise StorageError(f"Download failed: {e}")
        except Exception as e:
            logger.error(f"Download error: {e}", exc_info=True)
            # Cleanup partial download
            if cache_path.exists():
                shutil.rmtree(cache_path, ignore_errors=True)
            raise StorageError(f"Download error: {e}")

    async def delete_target(self, target_id: str) -> None:
        """Delete target from S3/MinIO."""
        try:
            s3_key = f'{target_id}/target'
            logger.info(f"Deleting s3://{self.bucket}/{s3_key}")

            self.s3_client.delete_object(
                Bucket=self.bucket,
                Key=s3_key
            )

            # Also delete from cache if present
            cache_path = self.cache_dir / target_id
            if cache_path.exists():
                shutil.rmtree(cache_path, ignore_errors=True)
                logger.info(f"✓ Deleted target {target_id} from S3 and cache")
            else:
                logger.info(f"✓ Deleted target {target_id} from S3")

        except ClientError as e:
            logger.error(f"S3 delete failed: {e}", exc_info=True)
            # Don't raise error if object doesn't exist
            if e.response.get('Error', {}).get('Code') not in ['404', 'NoSuchKey']:
                raise StorageError(f"Delete failed: {e}")
        except Exception as e:
            logger.error(f"Delete error: {e}", exc_info=True)
            raise StorageError(f"Delete error: {e}")

    async def upload_results(
        self,
        workflow_id: str,
        results: Dict[str, Any],
        results_format: str = "json"
    ) -> str:
        """Upload workflow results to S3/MinIO."""
        try:
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
                content = json.dumps(results, indent=2).encode('utf-8')
                content_type = 'application/json'
                file_ext = 'json'

            # Upload to results bucket
            results_bucket = 'results'
            s3_key = f'{workflow_id}/results.{file_ext}'

            logger.info(f"Uploading results to s3://{results_bucket}/{s3_key}")

            self.s3_client.put_object(
                Bucket=results_bucket,
                Key=s3_key,
                Body=content,
                ContentType=content_type,
                Metadata={
                    'workflow_id': workflow_id,
                    'format': results_format,
                    'uploaded_at': datetime.now().isoformat()
                }
            )

            # Construct URL
            results_url = f"{self.endpoint_url}/{results_bucket}/{s3_key}"
            logger.info(f"✓ Uploaded results: {results_url}")

            return results_url

        except Exception as e:
            logger.error(f"Results upload failed: {e}", exc_info=True)
            raise StorageError(f"Results upload failed: {e}")

    async def get_results(self, workflow_id: str) -> Dict[str, Any]:
        """Get workflow results from S3/MinIO."""
        try:
            results_bucket = 'results'
            s3_key = f'{workflow_id}/results.json'

            logger.info(f"Downloading results from s3://{results_bucket}/{s3_key}")

            response = self.s3_client.get_object(
                Bucket=results_bucket,
                Key=s3_key
            )

            content = response['Body'].read().decode('utf-8')
            results = json.loads(content)

            logger.info(f"✓ Downloaded results for workflow {workflow_id}")
            return results

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code in ['404', 'NoSuchKey']:
                logger.error(f"Results not found: {workflow_id}")
                raise FileNotFoundError(f"Results for workflow {workflow_id} not found")
            else:
                logger.error(f"Results download failed: {e}", exc_info=True)
                raise StorageError(f"Results download failed: {e}")
        except Exception as e:
            logger.error(f"Results download error: {e}", exc_info=True)
            raise StorageError(f"Results download error: {e}")

    async def list_targets(
        self,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> list[Dict[str, Any]]:
        """List uploaded targets."""
        try:
            targets = []
            paginator = self.s3_client.get_paginator('list_objects_v2')

            for page in paginator.paginate(Bucket=self.bucket, PaginationConfig={'MaxItems': limit}):
                for obj in page.get('Contents', []):
                    # Get object metadata
                    try:
                        metadata_response = self.s3_client.head_object(
                            Bucket=self.bucket,
                            Key=obj['Key']
                        )
                        metadata = metadata_response.get('Metadata', {})

                        # Filter by user_id if specified
                        if user_id and metadata.get('user_id') != user_id:
                            continue

                        targets.append({
                            'target_id': obj['Key'].split('/')[0],
                            'key': obj['Key'],
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'].isoformat(),
                            'metadata': metadata
                        })

                    except Exception as e:
                        logger.warning(f"Failed to get metadata for {obj['Key']}: {e}")
                        continue

            logger.info(f"Listed {len(targets)} targets (user_id={user_id})")
            return targets

        except Exception as e:
            logger.error(f"List targets failed: {e}", exc_info=True)
            raise StorageError(f"List targets failed: {e}")

    async def cleanup_cache(self) -> int:
        """Clean up local cache using LRU eviction."""
        try:
            cache_files = []
            total_size = 0

            # Gather all cached files with metadata
            for cache_file in self.cache_dir.rglob('*'):
                if cache_file.is_file():
                    try:
                        stat = cache_file.stat()
                        cache_files.append({
                            'path': cache_file,
                            'size': stat.st_size,
                            'atime': stat.st_atime  # Last access time
                        })
                        total_size += stat.st_size
                    except Exception as e:
                        logger.warning(f"Failed to stat {cache_file}: {e}")
                        continue

            # Check if cleanup is needed
            if total_size <= self.cache_max_size:
                logger.info(
                    f"Cache size OK: {total_size / (1024**3):.2f} GB / "
                    f"{self.cache_max_size / (1024**3):.2f} GB"
                )
                return 0

            # Sort by access time (oldest first)
            cache_files.sort(key=lambda x: x['atime'])

            # Remove files until under limit
            removed_count = 0
            for file_info in cache_files:
                if total_size <= self.cache_max_size:
                    break

                try:
                    file_info['path'].unlink()
                    total_size -= file_info['size']
                    removed_count += 1
                    logger.debug(f"Evicted from cache: {file_info['path']}")
                except Exception as e:
                    logger.warning(f"Failed to delete {file_info['path']}: {e}")
                    continue

            logger.info(
                f"✓ Cache cleanup: removed {removed_count} files, "
                f"new size: {total_size / (1024**3):.2f} GB"
            )
            return removed_count

        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}", exc_info=True)
            raise StorageError(f"Cache cleanup failed: {e}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        try:
            total_size = 0
            file_count = 0

            for cache_file in self.cache_dir.rglob('*'):
                if cache_file.is_file():
                    total_size += cache_file.stat().st_size
                    file_count += 1

            return {
                'total_size_bytes': total_size,
                'total_size_gb': total_size / (1024 ** 3),
                'file_count': file_count,
                'max_size_gb': self.cache_max_size / (1024 ** 3),
                'usage_percent': (total_size / self.cache_max_size) * 100
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {'error': str(e)}
