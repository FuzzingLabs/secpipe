"""TODO."""

from typing import TYPE_CHECKING

import pytest
from fastmcp import Client

from fuzzforge_mcp.application import mcp

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable

    from fastmcp.client import FastMCPTransport
    from fuzzforge_types import FuzzForgeProjectIdentifier

pytest_plugins = ["fuzzforge_tests.fixtures"]


@pytest.fixture(autouse=True)
def environment(
    monkeypatch: pytest.MonkeyPatch,
    random_project_identifier: Callable[[], FuzzForgeProjectIdentifier],
) -> None:
    """TODO."""
    monkeypatch.setenv("FUZZFORGE_PROJECT_IDENTIFIER", str(random_project_identifier()))
    monkeypatch.setenv("FUZZFORGE_API_HOST", "127.0.0.1")
    monkeypatch.setenv("FUZZFORGE_API_PORT", "8000")


@pytest.fixture
async def mcp_client() -> AsyncGenerator[Client[FastMCPTransport]]:
    """TODO."""
    async with Client(transport=mcp) as client:
        yield client
