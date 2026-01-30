"""ASGI entrypoint for containerized deployments."""

from pathlib import Path

from google.adk.cli.fast_api import get_fast_api_app

AGENT_DIR = Path(__file__).resolve().parent

app = get_fast_api_app(
    agents_dir=str(AGENT_DIR),
    web=False,
    a2a=True,
)
