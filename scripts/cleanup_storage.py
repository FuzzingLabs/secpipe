#!/usr/bin/env python3
"""
MinIO Storage Cleanup Utility for FuzzForge AI

This script provides manual and automated cleanup of MinIO storage to prevent
"out of free storage" errors. It can be run directly or scheduled via cron.

Usage:
    python scripts/cleanup_storage.py --dry-run         # Show what would be deleted
    python scripts/cleanup_storage.py                   # Delete old files
    python scripts/cleanup_storage.py --all-buckets     # Clean all buckets
    python scripts/cleanup_storage.py --force           # Delete all objects (DANGEROUS)

Environment Variables:
    S3_ENDPOINT     - MinIO endpoint (default: http://localhost:9000)
    S3_ACCESS_KEY   - MinIO access key (default: fuzzforge)
    S3_SECRET_KEY   - MinIO secret key (default: fuzzforge123)
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timezone, timedelta

import boto3
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default retention periods (days)
DEFAULT_RETENTION = {
    'targets': 7,
    'results': 30,
    'cache': 3
}


def get_s3_client():
    """Initialize S3 client for MinIO."""
    return boto3.client(
        's3',
        endpoint_url=os.getenv('S3_ENDPOINT', 'http://localhost:9000'),
        aws_access_key_id=os.getenv('S3_ACCESS_KEY', 'fuzzforge'),
        aws_secret_access_key=os.getenv('S3_SECRET_KEY', 'fuzzforge123'),
        region_name=os.getenv('S3_REGION', 'us-east-1'),
        use_ssl=os.getenv('S3_USE_SSL', 'false').lower() == 'true'
    )


def get_storage_stats(s3_client):
    """Get storage statistics for all buckets."""
    stats = {
        'buckets': {},
        'total_objects': 0,
        'total_size_bytes': 0
    }
    
    for bucket_name in DEFAULT_RETENTION.keys():
        try:
            bucket_stats = {'objects': 0, 'size_bytes': 0}
            paginator = s3_client.get_paginator('list_objects_v2')
            
            for page in paginator.paginate(Bucket=bucket_name):
                for obj in page.get('Contents', []):
                    bucket_stats['objects'] += 1
                    bucket_stats['size_bytes'] += obj.get('Size', 0)
            
            bucket_stats['size_mb'] = bucket_stats['size_bytes'] / (1024 ** 2)
            bucket_stats['size_gb'] = bucket_stats['size_bytes'] / (1024 ** 3)
            stats['buckets'][bucket_name] = bucket_stats
            stats['total_objects'] += bucket_stats['objects']
            stats['total_size_bytes'] += bucket_stats['size_bytes']
            
        except ClientError as e:
            if e.response.get('Error', {}).get('Code') == 'NoSuchBucket':
                logger.warning(f"Bucket '{bucket_name}' does not exist")
                stats['buckets'][bucket_name] = {'error': 'Bucket not found'}
            else:
                logger.error(f"Error accessing bucket '{bucket_name}': {e}")
                stats['buckets'][bucket_name] = {'error': str(e)}
    
    stats['total_size_mb'] = stats['total_size_bytes'] / (1024 ** 2)
    stats['total_size_gb'] = stats['total_size_bytes'] / (1024 ** 3)
    
    return stats


def cleanup_bucket(s3_client, bucket: str, days_old: int, dry_run: bool = True, force: bool = False):
    """
    Clean up old objects from a bucket.
    
    Args:
        s3_client: Boto3 S3 client
        bucket: Bucket name
        days_old: Delete objects older than this many days
        dry_run: If True, only show what would be deleted
        force: If True, delete ALL objects regardless of age
    
    Returns:
        Dictionary with cleanup results
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
    objects_to_delete = []
    total_size = 0
    
    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        
        for page in paginator.paginate(Bucket=bucket):
            for obj in page.get('Contents', []):
                last_modified = obj.get('LastModified')
                
                # Force mode deletes everything, otherwise check age
                if force or (last_modified and last_modified < cutoff_date):
                    objects_to_delete.append({
                        'Key': obj['Key'],
                        'Size': obj.get('Size', 0),
                        'LastModified': last_modified.isoformat() if last_modified else 'unknown'
                    })
                    total_size += obj.get('Size', 0)
        
        result = {
            'bucket': bucket,
            'days_old': days_old if not force else 'ALL',
            'objects_found': len(objects_to_delete),
            'total_size_bytes': total_size,
            'total_size_mb': total_size / (1024 ** 2),
            'dry_run': dry_run,
            'deleted': 0
        }
        
        if not objects_to_delete:
            logger.info(f"[{bucket}] No objects to delete")
            return result
        
        if dry_run:
            logger.info(f"[{bucket}] DRY RUN: Would delete {len(objects_to_delete)} objects ({result['total_size_mb']:.2f} MB)")
            for obj in objects_to_delete[:10]:
                logger.info(f"  - {obj['Key']} ({obj['Size'] / 1024:.1f} KB, modified: {obj['LastModified']})")
            if len(objects_to_delete) > 10:
                logger.info(f"  ... and {len(objects_to_delete) - 10} more")
            return result
        
        # Actually delete objects
        logger.info(f"[{bucket}] Deleting {len(objects_to_delete)} objects ({result['total_size_mb']:.2f} MB)...")
        
        # Delete in batches of 1000 (S3 limit)
        for i in range(0, len(objects_to_delete), 1000):
            batch = objects_to_delete[i:i + 1000]
            delete_request = {
                'Objects': [{'Key': obj['Key']} for obj in batch],
                'Quiet': True
            }
            s3_client.delete_objects(Bucket=bucket, Delete=delete_request)
            result['deleted'] += len(batch)
            logger.info(f"  Deleted batch {i // 1000 + 1}: {len(batch)} objects")
        
        logger.info(f"[{bucket}] ✓ Deleted {result['deleted']} objects ({result['total_size_mb']:.2f} MB freed)")
        return result
        
    except ClientError as e:
        if e.response.get('Error', {}).get('Code') == 'NoSuchBucket':
            logger.warning(f"[{bucket}] Bucket does not exist, skipping")
            return {'bucket': bucket, 'error': 'Bucket not found'}
        else:
            logger.error(f"[{bucket}] Error: {e}")
            raise


def main():
    parser = argparse.ArgumentParser(
        description='MinIO Storage Cleanup Utility for FuzzForge AI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --dry-run                    Show what would be deleted
  %(prog)s                              Delete old files from 'targets' bucket
  %(prog)s --all-buckets                Clean all buckets with default retention
  %(prog)s --bucket results --days 7    Clean results older than 7 days
  %(prog)s --force --bucket cache       Delete ALL objects in cache bucket (DANGEROUS)
        """
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Only show what would be deleted, do not actually delete'
    )
    parser.add_argument(
        '--bucket',
        choices=['targets', 'results', 'cache'],
        default='targets',
        help='Bucket to clean (default: targets)'
    )
    parser.add_argument(
        '--all-buckets',
        action='store_true',
        help='Clean all buckets with their default retention periods'
    )
    parser.add_argument(
        '--days',
        type=int,
        help='Delete objects older than this many days (overrides default)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Delete ALL objects regardless of age (DANGEROUS!)'
    )
    parser.add_argument(
        '--stats-only',
        action='store_true',
        help='Only show storage statistics, do not delete anything'
    )
    
    args = parser.parse_args()
    
    # Safety check for force mode
    if args.force and not args.dry_run:
        confirm = input("WARNING: --force will delete ALL objects. Type 'yes' to confirm: ")
        if confirm.lower() != 'yes':
            logger.info("Aborted.")
            sys.exit(0)
    
    try:
        s3_client = get_s3_client()
        logger.info(f"Connected to MinIO: {os.getenv('S3_ENDPOINT', 'http://localhost:9000')}")
        
        # Show storage stats
        logger.info("\n=== Storage Statistics ===")
        stats = get_storage_stats(s3_client)
        
        for bucket_name, bucket_stats in stats['buckets'].items():
            if 'error' in bucket_stats:
                logger.info(f"  {bucket_name}: {bucket_stats['error']}")
            else:
                logger.info(
                    f"  {bucket_name}: {bucket_stats['objects']} objects, "
                    f"{bucket_stats['size_mb']:.2f} MB ({bucket_stats['size_gb']:.2f} GB)"
                )
        
        logger.info(
            f"\n  TOTAL: {stats['total_objects']} objects, "
            f"{stats['total_size_mb']:.2f} MB ({stats['total_size_gb']:.2f} GB)"
        )
        
        if args.stats_only:
            sys.exit(0)
        
        # Clean up
        logger.info("\n=== Cleanup ===")
        
        if args.all_buckets:
            buckets_to_clean = DEFAULT_RETENTION.keys()
        else:
            buckets_to_clean = [args.bucket]
        
        total_deleted = 0
        total_freed_mb = 0
        
        for bucket in buckets_to_clean:
            days = args.days if args.days else DEFAULT_RETENTION.get(bucket, 7)
            result = cleanup_bucket(
                s3_client,
                bucket,
                days_old=days,
                dry_run=args.dry_run,
                force=args.force
            )
            if 'deleted' in result:
                total_deleted += result['deleted']
                total_freed_mb += result.get('total_size_mb', 0) if not args.dry_run else 0
        
        # Summary
        logger.info("\n=== Summary ===")
        if args.dry_run:
            logger.info(f"DRY RUN: Would delete {total_deleted} objects")
        else:
            logger.info(f"Deleted {total_deleted} objects, freed {total_freed_mb:.2f} MB")
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
