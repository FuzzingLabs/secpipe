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
