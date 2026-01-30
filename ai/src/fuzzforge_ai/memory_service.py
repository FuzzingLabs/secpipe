"""
FuzzForge Memory Service
Implements ADK MemoryService pattern for conversational memory
Separate from Cognee which will be used for RAG/codebase analysis
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
from typing import Dict, Any
import logging

# ADK Memory imports
from google.adk.memory import InMemoryMemoryService, BaseMemoryService
from google.adk.memory.base_memory_service import SearchMemoryResponse

# Optional VertexAI Memory Bank
try:
    from google.adk.memory import VertexAiMemoryBankService
    VERTEX_AVAILABLE = True
except ImportError:
    VERTEX_AVAILABLE = False

logger = logging.getLogger(__name__)


class FuzzForgeMemoryService:
    """
    Manages conversational memory using ADK patterns
    This is separate from Cognee which will handle RAG/codebase
    """
    
    def __init__(self, memory_type: str = "inmemory", **kwargs):
        """
        Initialize memory service
        
        Args:
            memory_type: "inmemory" or "vertexai"
            **kwargs: Additional args for specific memory service
                     For vertexai: project, location, agent_engine_id
        """
        self.memory_type = memory_type
        self.service = self._create_service(memory_type, **kwargs)
        
    def _create_service(self, memory_type: str, **kwargs) -> BaseMemoryService:
        """Create the appropriate memory service"""
        
        if memory_type == "inmemory":
            # Use ADK's InMemoryMemoryService for local development
            logger.info("Using InMemory MemoryService for conversational memory")
            return InMemoryMemoryService()
            
        elif memory_type == "vertexai" and VERTEX_AVAILABLE:
            # Use VertexAI Memory Bank for production
            project = kwargs.get('project') or os.getenv('GOOGLE_CLOUD_PROJECT')
            location = kwargs.get('location') or os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
            agent_engine_id = kwargs.get('agent_engine_id') or os.getenv('AGENT_ENGINE_ID')
            
            if not all([project, location, agent_engine_id]):
                logger.warning("VertexAI config missing, falling back to InMemory")
                return InMemoryMemoryService()
            
            logger.info(f"Using VertexAI MemoryBank: {agent_engine_id}")
            return VertexAiMemoryBankService(
                project=project,
                location=location,
                agent_engine_id=agent_engine_id
            )
        else:
            # Default to in-memory
            logger.info("Defaulting to InMemory MemoryService")
            return InMemoryMemoryService()
    
    async def add_session_to_memory(self, session: Any) -> None:
        """
        Add a completed session to long-term memory
        This extracts meaningful information from the conversation
        
        Args:
            session: The session object to process
        """
        try:
            # Let the underlying service handle the ingestion
            # It will extract relevant information based on the implementation
            await self.service.add_session_to_memory(session)
            
            logger.debug(f"Added session {session.id} to {self.memory_type} memory")
            
        except Exception as e:
            logger.error(f"Failed to add session to memory: {e}")
    
    async def search_memory(self, 
                          query: str,
                          app_name: str = "fuzzforge",
                          user_id: str = None,
                          max_results: int = 10) -> SearchMemoryResponse:
        """
        Search long-term memory for relevant information
        
        Args:
            query: The search query
            app_name: Application name for filtering
            user_id: User ID for filtering (optional)
            max_results: Maximum number of results
            
        Returns:
            SearchMemoryResponse with relevant memories
        """
        try:
            # Search the memory service
            results = await self.service.search_memory(
                app_name=app_name,
                user_id=user_id,
                query=query
            )
            
            logger.debug(f"Memory search for '{query}' returned {len(results.memories)} results")
            return results
            
        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            # Return empty results on error
            return SearchMemoryResponse(memories=[])
    
    async def ingest_completed_sessions(self, session_service) -> int:
        """
        Batch ingest all completed sessions into memory
        Useful for initial memory population
        
        Args:
            session_service: The session service containing sessions
            
        Returns:
            Number of sessions ingested
        """
        ingested = 0
        
        try:
            # Get all sessions from the session service
            sessions = await session_service.list_sessions(app_name="fuzzforge")
            
            for session_info in sessions:
                # Load full session
                session = await session_service.load_session(
                    app_name="fuzzforge",
                    user_id=session_info.get('user_id'),
                    session_id=session_info.get('id')
                )
                
                if session and len(session.get_events()) > 0:
                    await self.add_session_to_memory(session)
                    ingested += 1
                    
            logger.info(f"Ingested {ingested} sessions into {self.memory_type} memory")
            
        except Exception as e:
            logger.error(f"Failed to batch ingest sessions: {e}")
            
        return ingested
    
    def get_status(self) -> Dict[str, Any]:
        """Get memory service status"""
        return {
            "type": self.memory_type,
            "active": self.service is not None,
            "vertex_available": VERTEX_AVAILABLE,
            "details": {
                "inmemory": "Non-persistent, keyword search",
                "vertexai": "Persistent, semantic search with LLM extraction"
            }.get(self.memory_type, "Unknown")
        }


class HybridMemoryManager:
    """
    Manages both ADK MemoryService (conversational) and Cognee (RAG/codebase)
    Provides unified interface for both memory systems
    """
    
    def __init__(self, 
                 memory_service: FuzzForgeMemoryService = None,
                 cognee_tools = None):
        """
        Initialize with both memory systems
        
        Args:
            memory_service: ADK-pattern memory for conversations
            cognee_tools: Cognee MCP tools for RAG/codebase
        """
        # ADK memory for conversations
        self.memory_service = memory_service or FuzzForgeMemoryService()
        
        # Cognee for knowledge graphs and RAG (future)
        self.cognee_tools = cognee_tools
        
    async def search_conversational_memory(self, query: str) -> SearchMemoryResponse:
        """Search past conversations using ADK memory"""
        return await self.memory_service.search_memory(query)
    
    async def search_knowledge_graph(self, query: str, search_type: str = "GRAPH_COMPLETION"):
        """Search Cognee knowledge graph (for RAG/codebase in future)"""
        if not self.cognee_tools:
            return None
            
        try:
            # Use Cognee's graph search
            return await self.cognee_tools.search(
                query=query,
                search_type=search_type
            )
        except Exception as e:
            logger.debug(f"Cognee search failed: {e}")
            return None
    
    async def store_in_graph(self, content: str):
        """Store in Cognee knowledge graph (for codebase analysis later)"""
        if not self.cognee_tools:
            return None
            
        try:
            # Use cognify to create graph structures
            return await self.cognee_tools.cognify(content)
        except Exception as e:
            logger.debug(f"Cognee store failed: {e}")
            return None
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of both memory systems"""
        return {
            "conversational_memory": self.memory_service.get_status(),
            "knowledge_graph": {
                "active": self.cognee_tools is not None,
                "purpose": "RAG/codebase analysis (future)"
            }
        }