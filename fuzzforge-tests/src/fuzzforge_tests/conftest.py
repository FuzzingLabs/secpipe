"""Pytest configuration for shared fixtures.

This conftest.py makes fixtures available to any test that imports from
fuzzforge_tests. Test packages should add 'pytest_plugins = ["fuzzforge_tests.fixtures"]'
to their conftest.py to use these shared fixtures.

"""

# Import fixtures to make them available
from fuzzforge_tests.fixtures import (
    minio_container,
    random_module_execution_identifier,
    random_project_identifier,
    storage_configuration,
)

__all__ = [
    "minio_container",
    "random_module_execution_identifier",
    "random_project_identifier",
    "storage_configuration",
]
