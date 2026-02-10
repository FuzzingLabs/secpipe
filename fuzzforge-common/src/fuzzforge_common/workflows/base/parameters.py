from pydantic import BaseModel

from fuzzforge_common.sandboxes.engines.docker.configuration import (
    DockerConfiguration,  # noqa: TC001 (required by pydantic at runtime)
)
from fuzzforge_common.sandboxes.engines.podman.configuration import (
    PodmanConfiguration,  # noqa: TC001 (required by pydantic at runtime)
)
from fuzzforge_common.storage.configuration import StorageConfiguration  # noqa: TC001 (required by pydantic at runtime)


class TemporalWorkflowParameters(BaseModel):
    """Base parameters for Temporal workflows.

    Provides common configuration shared across all workflow types,
    including sandbox engine and storage backend instances.

    """

    #: Sandbox engine for container operations (Docker or Podman).
    engine_configuration: PodmanConfiguration | DockerConfiguration

    #: Storage backend for uploading/downloading execution artifacts.
    storage_configuration: StorageConfiguration
