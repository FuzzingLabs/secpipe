"""Custom A2A wiring so we can access task store and queue manager."""
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


from __future__ import annotations

import logging
from typing import Optional, Union

from starlette.applications import Starlette
from starlette.responses import Response, FileResponse

from google.adk.a2a.executor.a2a_agent_executor import A2aAgentExecutor
from google.adk.a2a.utils.agent_card_builder import AgentCardBuilder
from google.adk.a2a.experimental import a2a_experimental
from google.adk.agents.base_agent import BaseAgent
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.auth.credential_service.in_memory_credential_service import InMemoryCredentialService
from google.adk.cli.utils.logs import setup_adk_logger
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers.default_request_handler import DefaultRequestHandler
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.server.events.in_memory_queue_manager import InMemoryQueueManager
from a2a.types import AgentCard

from .agent_executor import FuzzForgeExecutor


import json


async def serve_artifact(request):
    """Serve artifact files via HTTP for A2A agents"""
    artifact_id = request.path_params["artifact_id"]
    
    # Try to get the executor instance to access artifact cache
    # We'll store a reference to it during app creation
    executor = getattr(serve_artifact, '_executor', None)
    if not executor:
        return Response("Artifact service not available", status_code=503)
    
    try:
        # Look in the artifact cache directory
        artifact_cache_dir = executor._artifact_cache_dir
        artifact_dir = artifact_cache_dir / artifact_id
        
        if not artifact_dir.exists():
            return Response("Artifact not found", status_code=404)
            
        # Find the artifact file (should be only one file in the directory)
        artifact_files = list(artifact_dir.glob("*"))
        if not artifact_files:
            return Response("Artifact file not found", status_code=404)
            
        artifact_file = artifact_files[0]  # Take the first (and should be only) file
        
        # Determine mime type from file extension or default to octet-stream
        import mimetypes
        mime_type, _ = mimetypes.guess_type(str(artifact_file))
        if not mime_type:
            mime_type = 'application/octet-stream'
            
        return FileResponse(
            path=str(artifact_file),
            media_type=mime_type,
            filename=artifact_file.name
        )

    except Exception as e:
        return Response(f"Error serving artifact: {str(e)}", status_code=500)


async def knowledge_query(request):
    """Expose knowledge graph search over HTTP for external agents."""
    executor = getattr(knowledge_query, '_executor', None)
    if not executor:
        return Response("Knowledge service not available", status_code=503)

    try:
        payload = await request.json()
    except Exception:
        return Response("Invalid JSON body", status_code=400)

    query = payload.get("query")
    if not query:
        return Response("'query' is required", status_code=400)

    search_type = payload.get("search_type", "INSIGHTS")
    dataset = payload.get("dataset")

    result = await executor.query_project_knowledge_api(
        query=query,
        search_type=search_type,
        dataset=dataset,
    )

    status = 200 if not isinstance(result, dict) or "error" not in result else 400
    return Response(
        json.dumps(result, default=str),
        status_code=status,
        media_type="application/json",
    )


async def create_file_artifact(request):
    """Create an artifact from a project file via HTTP."""
    executor = getattr(create_file_artifact, '_executor', None)
    if not executor:
        return Response("File service not available", status_code=503)

    try:
        payload = await request.json()
    except Exception:
        return Response("Invalid JSON body", status_code=400)

    path = payload.get("path")
    if not path:
        return Response("'path' is required", status_code=400)

    result = await executor.create_project_file_artifact_api(path)
    status = 200 if not isinstance(result, dict) or "error" not in result else 400
    return Response(
        json.dumps(result, default=str),
        status_code=status,
        media_type="application/json",
    )


def _load_agent_card(agent_card: Optional[Union[AgentCard, str]]) -> Optional[AgentCard]:
    if agent_card is None:
        return None
    if isinstance(agent_card, AgentCard):
        return agent_card

    import json
    from pathlib import Path

    path = Path(agent_card)
    with path.open('r', encoding='utf-8') as handle:
        data = json.load(handle)
    return AgentCard(**data)


@a2a_experimental
def create_a2a_app(
    agent: BaseAgent,
    *,
    host: str = "localhost",
    port: int = 8000,
    protocol: str = "http",
    agent_card: Optional[Union[AgentCard, str]] = None,
    executor=None,  # Accept executor reference
) -> Starlette:
    """Variant of google.adk.a2a.utils.to_a2a that exposes task-store handles."""

    setup_adk_logger(logging.INFO)

    async def create_runner() -> Runner:
        return Runner(
            agent=agent,
            app_name=agent.name or "fuzzforge",
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
            credential_service=InMemoryCredentialService(),
        )

    task_store = InMemoryTaskStore()
    queue_manager = InMemoryQueueManager()

    agent_executor = A2aAgentExecutor(runner=create_runner)
    request_handler = DefaultRequestHandler(
        agent_executor=agent_executor,
        task_store=task_store,
        queue_manager=queue_manager,
    )

    rpc_url = f"{protocol}://{host}:{port}/"
    provided_card = _load_agent_card(agent_card)

    card_builder = AgentCardBuilder(agent=agent, rpc_url=rpc_url)

    app = Starlette()

    async def setup() -> None:
        if provided_card is not None:
            final_card = provided_card
        else:
            final_card = await card_builder.build()

        a2a_app = A2AStarletteApplication(
            agent_card=final_card,
            http_handler=request_handler,
        )
        a2a_app.add_routes_to_app(app)
        
        # Add artifact serving route
        app.router.add_route("/artifacts/{artifact_id}", serve_artifact, methods=["GET"])
        app.router.add_route("/graph/query", knowledge_query, methods=["POST"])
        app.router.add_route("/project/files", create_file_artifact, methods=["POST"])

    app.add_event_handler("startup", setup)

    # Expose handles so the executor can emit task updates later
    FuzzForgeExecutor.task_store = task_store
    FuzzForgeExecutor.queue_manager = queue_manager
    
    # Store reference to executor for artifact serving
    serve_artifact._executor = executor
    knowledge_query._executor = executor
    create_file_artifact._executor = executor

    return app


__all__ = ["create_a2a_app"]
