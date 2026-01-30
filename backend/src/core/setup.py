"""
Setup utilities for FuzzForge infrastructure
"""

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

import logging

logger = logging.getLogger(__name__)


async def setup_result_storage():
    """
    Setup result storage (MinIO).

    MinIO is used for both target upload and result storage.
    This is a placeholder for any MinIO-specific setup if needed.
    """
    logger.info("Result storage (MinIO) configured")
    # MinIO is configured via environment variables in docker-compose
    # No additional setup needed here
    return True


async def validate_infrastructure():
    """
    Validate all required infrastructure components.

    This should be called during startup to ensure everything is ready.
    """
    logger.info("Validating infrastructure...")

    # Setup storage (MinIO)
    await setup_result_storage()

    logger.info("Infrastructure validation completed")
