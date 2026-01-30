"""MCP resource tests for FuzzForge OSS.

Note: The OSS version uses a different architecture than the enterprise version.
These tests are placeholders - the actual MCP tools are tested through integration tests.
"""

import pytest


@pytest.mark.skip(reason="OSS uses different architecture - no HTTP API")
async def test_placeholder() -> None:
    """Placeholder test - OSS MCP doesn't use HTTP resources."""
    pass
