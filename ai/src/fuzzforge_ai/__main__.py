# ruff: noqa: E402  # Imports delayed for environment/logging setup
"""
FuzzForge A2A Server
Run this to expose FuzzForge as an A2A-compatible agent
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


import os
import warnings
import logging
from dotenv import load_dotenv

from fuzzforge_ai.config_bridge import ProjectConfigManager

# Suppress warnings
warnings.filterwarnings("ignore")
logging.getLogger("google.adk").setLevel(logging.ERROR)
logging.getLogger("google.adk.tools.base_authenticated_tool").setLevel(logging.ERROR)

# Load .env from .fuzzforge directory first, then fallback
from pathlib import Path

# Ensure Cognee logs stay inside the project workspace
project_root = Path.cwd()
default_log_dir = project_root / ".fuzzforge" / "logs"
default_log_dir.mkdir(parents=True, exist_ok=True)
log_path = default_log_dir / "cognee.log"
os.environ.setdefault("COGNEE_LOG_PATH", str(log_path))
fuzzforge_env = Path.cwd() / ".fuzzforge" / ".env"
if fuzzforge_env.exists():
    load_dotenv(fuzzforge_env, override=True)
else:
    load_dotenv(override=True)

# Ensure Cognee uses the project-specific storage paths when available
try:
    project_config = ProjectConfigManager()
    project_config.setup_cognee_environment()
except Exception:
    # Project may not be initialized; fall through with default settings
    pass

# Check configuration
if not os.getenv('LITELLM_MODEL'):
    print("[ERROR] LITELLM_MODEL not set in .env file")
    print("Please set LITELLM_MODEL to your desired model (e.g., gpt-4o-mini)")
    exit(1)

from .agent import get_fuzzforge_agent
from .a2a_server import create_a2a_app as create_custom_a2a_app


def create_a2a_app():
    """Create the A2A application"""
    # Get configuration
    port = int(os.getenv('FUZZFORGE_PORT', 10100))
    
    # Get the FuzzForge agent
    fuzzforge = get_fuzzforge_agent()
    
    # Print ASCII banner
    print("\033[95m")  # Purple color
    print(" ███████╗██╗   ██╗███████╗███████╗███████╗ ██████╗ ██████╗  ██████╗ ███████╗     █████╗ ██╗")
    print(" ██╔════╝██║   ██║╚══███╔╝╚══███╔╝██╔════╝██╔═══██╗██╔══██╗██╔════╝ ██╔════╝    ██╔══██╗██║")
    print(" █████╗  ██║   ██║  ███╔╝   ███╔╝ █████╗  ██║   ██║██████╔╝██║  ███╗█████╗      ███████║██║")
    print(" ██╔══╝  ██║   ██║ ███╔╝   ███╔╝  ██╔══╝  ██║   ██║██╔══██╗██║   ██║██╔══╝      ██╔══██║██║")
    print(" ██║     ╚██████╔╝███████╗███████╗██║     ╚██████╔╝██║  ██║╚██████╔╝███████╗    ██║  ██║██║")
    print(" ╚═╝      ╚═════╝ ╚══════╝╚══════╝╚═╝      ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝    ╚═╝  ╚═╝╚═╝")
    print("\033[0m")  # Reset color
    
    # Create A2A app
    print("🚀 Starting FuzzForge A2A Server")
    print(f"   Model: {fuzzforge.model}")
    if fuzzforge.cognee_url:
        print(f"   Memory: Cognee at {fuzzforge.cognee_url}")
    print(f"   Port: {port}")
    
    app = create_custom_a2a_app(fuzzforge.adk_agent, port=port, executor=fuzzforge.executor)
    
    print("\n✅ FuzzForge A2A Server ready!")
    print(f"   Agent card: http://localhost:{port}/.well-known/agent-card.json")
    print(f"   A2A endpoint: http://localhost:{port}/")
    print(f"\n📡 Other agents can register FuzzForge at: http://localhost:{port}")
    
    return app


def main():
    """Start the A2A server using uvicorn."""
    import uvicorn

    app = create_a2a_app()
    port = int(os.getenv('FUZZFORGE_PORT', 10100))

    print("\n🎯 Starting server with uvicorn...")
    uvicorn.run(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
