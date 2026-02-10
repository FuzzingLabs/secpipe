"""Module resources for FuzzForge MCP."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastmcp import FastMCP
from fastmcp.exceptions import ResourceError

from fuzzforge_mcp.dependencies import get_runner

if TYPE_CHECKING:
    from fuzzforge_runner import Runner
    from fuzzforge_runner.runner import ModuleInfo


mcp: FastMCP = FastMCP()


@mcp.resource("fuzzforge://modules/")
async def list_modules() -> list[dict[str, Any]]:
    """List all available FuzzForge modules.

    Returns information about modules that can be executed,
    including their identifiers and availability status.

    :return: List of module information dictionaries.

    """
    runner: Runner = get_runner()

    try:
        modules: list[ModuleInfo] = runner.list_modules()

        return [
            {
                "identifier": module.identifier,
                "description": module.description,
                "version": module.version,
                "available": module.available,
            }
            for module in modules
        ]

    except Exception as exception:
        message: str = f"Failed to list modules: {exception}"
        raise ResourceError(message) from exception


@mcp.resource("fuzzforge://modules/{module_identifier}")
async def get_module(module_identifier: str) -> dict[str, Any]:
    """Get information about a specific module.

    :param module_identifier: The identifier of the module to retrieve.
    :return: Module information dictionary.

    """
    runner: Runner = get_runner()

    try:
        module: ModuleInfo | None = runner.get_module_info(module_identifier)

        if module is None:
            raise ResourceError(f"Module not found: {module_identifier}")

        return {
            "identifier": module.identifier,
            "description": module.description,
            "version": module.version,
            "available": module.available,
        }

    except ResourceError:
        raise
    except Exception as exception:
        message: str = f"Failed to get module: {exception}"
        raise ResourceError(message) from exception

