# ruff: noqa: E402  # Imports delayed for environment/logging setup
"""FuzzForge Agent Executor - orchestrates workflows and delegation."""
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


import asyncio
import time
import uuid
import json
from typing import Dict, Any, List, Union
from datetime import datetime
import os
import warnings
import logging
from pathlib import Path
import mimetypes
import hashlib
import tempfile

# Suppress warnings
warnings.filterwarnings("ignore")
logging.getLogger("google.adk").setLevel(logging.ERROR)
logging.getLogger("google.adk.tools.base_authenticated_tool").setLevel(logging.ERROR)
logging.getLogger("agentops").setLevel(logging.ERROR)

from google.genai import types
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService, InMemorySessionService
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.artifacts.gcs_artifact_service import GcsArtifactService
from google.adk.events.event import Event
from google.adk.events.event_actions import EventActions
from google.adk.tools import FunctionTool
from google.adk.tools.long_running_tool import LongRunningFunctionTool
from google.adk.tools.tool_context import ToolContext

# Optional AgentOps
try:
    import agentops
    AGENTOPS_AVAILABLE = True
except ImportError:
    AGENTOPS_AVAILABLE = False

# MCP functionality removed - keeping direct Cognee integration only

from google.genai.types import Part
from a2a.types import (
    Task,
    TaskStatus,
    TaskState,
    TaskStatusUpdateEvent,
    Message,
    Part as A2APart,
)

from .remote_agent import RemoteAgentConnection
from .config_bridge import ProjectConfigManager


class FuzzForgeExecutor:
    """Executes tasks for FuzzForge - the brain of the operation"""

    task_store = None
    queue_manager = None

    def __init__(
        self,
        model: str = None,
        cognee_url: str = None,
        debug: bool = False,
        memory_service=None,
        session_persistence: str = None,
        fuzzforge_mcp_url: str = None,
    ):
        """Initialize the executor with configuration"""
        self.model = model or os.getenv('LITELLM_MODEL', 'gpt-5-mini')
        self.cognee_url = cognee_url or os.getenv('COGNEE_MCP_URL')
        self.debug = debug
        self.memory_service = memory_service  # ADK memory service
        self.session_persistence = session_persistence or os.getenv('SESSION_PERSISTENCE', 'inmemory')
        self.fuzzforge_mcp_url = fuzzforge_mcp_url or os.getenv('FUZZFORGE_MCP_URL')
        self._background_tasks: set[asyncio.Task] = set()
        self.pending_runs: Dict[str, Dict[str, Any]] = {}
        self.session_metadata: Dict[str, Dict[str, Any]] = {}
        self._artifact_cache_dir = Path(os.getenv('FUZZFORGE_ARTIFACT_DIR', Path.cwd() / '.fuzzforge' / 'artifacts'))
        self._knowledge_integration = None

        # Initialize Cognee service if available
        self.cognee_service = None
        self._cognee_initialized = False

        # Agent registry - stores registered agents
        self.agents: Dict[str, Dict[str, Any]] = {}
        
        # Session management
        self.sessions: Dict[str, Any] = {}
        self.session_lookup: Dict[str, str] = {}
        
        # Create session service based on persistence setting
        self.session_service = self._create_session_service()
        
        # Initialize artifact service (A2A compliant)
        self.artifact_service = self._create_artifact_service()
        # Local artifact cache for quick access
        self.artifacts: Dict[str, List[Dict[str, Any]]] = {}
        
        # Initialize AgentOps if available
        self.agentops_trace = None
        if AGENTOPS_AVAILABLE and os.getenv('AGENTOPS_API_KEY'):
            try:
                agentops.init(api_key=os.getenv('AGENTOPS_API_KEY'))
                self.agentops_trace = agentops.start_trace()
                if self.debug:
                    print("[DEBUG] AgentOps tracking enabled")
            except Exception as e:
                if self.debug:
                    print(f"[DEBUG] AgentOps init failed: {e}")
        
        # Initialize the core agent
        self._initialize_agent()

        # Auto-register agents from config
        self._auto_register_agents()

        # Ensure task store/queue manager exist for CLI usage even without A2A server
        if getattr(FuzzForgeExecutor, "task_store", None) is None:
            try:
                from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
                FuzzForgeExecutor.task_store = InMemoryTaskStore()
            except Exception:
                FuzzForgeExecutor.task_store = None
        if getattr(FuzzForgeExecutor, "queue_manager", None) is None:
            try:
                from a2a.server.events.in_memory_queue_manager import InMemoryQueueManager
                FuzzForgeExecutor.queue_manager = InMemoryQueueManager()
            except Exception:
                FuzzForgeExecutor.queue_manager = None

        self.task_store = FuzzForgeExecutor.task_store
        self.queue_manager = FuzzForgeExecutor.queue_manager
    
    def _auto_register_agents(self):
        """Auto-register agents from config file"""
        try:
            from .config_manager import ConfigManager
            config_mgr = ConfigManager()
            registered = config_mgr.get_registered_agents()
            
            if registered and self.debug:
                print(f"[DEBUG] Auto-registering {len(registered)} agents from config")
            
            for agent_config in registered:
                url = agent_config.get('url')
                name = agent_config.get('name', '')
                if url:
                    # Register silently (don't wait for async)
                    import asyncio
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # Schedule for later if loop is already running
                            asyncio.create_task(self._register_agent_async(url, name))
                        else:
                            # Run now if no loop is running
                            loop.run_until_complete(self._register_agent_async(url, name))
                    except Exception:
                        # Ignore auto-registration failures
                        pass
        except Exception as e:
            if self.debug:
                print(f"[DEBUG] Auto-registration failed: {e}")
    
    async def _register_agent_async(self, url: str, name: str):
        """Async helper for auto-registration"""
        try:
            result = await self.register_agent(url)
            if self.debug:
                if result.get('success'):
                    print(f"[DEBUG] Auto-registered: {name or result.get('name')} at {url} as RemoteA2aAgent sub-agent")
                else:
                    print(f"[DEBUG] Failed to auto-register {url}: {result.get('error')}")
        except Exception as e:
            if self.debug:
                print(f"[DEBUG] Auto-registration error for {url}: {e}")
    
    def _create_artifact_service(self):
        """Create artifact service based on configuration"""
        artifact_storage = os.getenv('ARTIFACT_STORAGE', 'inmemory')
        
        if artifact_storage.lower() == 'gcs':
            # Use Google Cloud Storage for artifacts
            bucket_name = os.getenv('GCS_ARTIFACT_BUCKET', 'fuzzforge-artifacts')
            if self.debug:
                print(f"[DEBUG] Using GCS artifact storage: {bucket_name}")
            try:
                return GcsArtifactService(bucket_name=bucket_name)
            except Exception as e:
                if self.debug:
                    print(f"[DEBUG] GCS artifact service failed: {e}, falling back to in-memory")
                return InMemoryArtifactService()
        else:
            # Default to in-memory artifacts
            if self.debug:
                print("[DEBUG] Using in-memory artifact service")
            return InMemoryArtifactService()

    def _prepare_artifact_cache_dir(self) -> Path:
        """Ensure a shared directory exists for delegated artifacts."""
        try:
            self._artifact_cache_dir.mkdir(parents=True, exist_ok=True)
            return self._artifact_cache_dir
        except Exception:
            fallback = Path(tempfile.gettempdir()) / "fuzzforge_artifacts"
            fallback.mkdir(parents=True, exist_ok=True)
            self._artifact_cache_dir = fallback
            if self.debug:
                print(f"[DEBUG] Falling back to artifact cache dir {fallback}")
            return fallback

    def _register_artifact_bytes(
        self,
        *,
        name: str,
        data: bytes,
        mime_type: str,
        sha256_digest: str,
        size: int,
        artifact_id: str = None,  # Optional: use provided ID instead of generating new one
    ) -> Dict[str, Any]:
        """Persist artifact bytes to cache directory and return metadata."""
        base_dir = self._prepare_artifact_cache_dir()
        if artifact_id is None:
            artifact_id = uuid.uuid4().hex
        artifact_dir = base_dir / artifact_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        file_path = artifact_dir / name
        file_path.write_bytes(data)
        
        # Create HTTP URL for A2A artifact serving instead of file:// URI
        port = int(os.getenv('FUZZFORGE_PORT', 10100))
        http_uri = f"http://127.0.0.1:{port}/artifacts/{artifact_id}"
        
        return {
            "id": artifact_id,
            "file_uri": http_uri,
            "path": str(file_path),
            "name": name,
            "mime_type": mime_type,
            "sha256": sha256_digest,
            "size": size,
        }
    
    def _create_session_service(self):
        """Create session service based on persistence setting"""
        if self.session_persistence.lower() == 'sqlite':
            # Use SQLite for persistent sessions
            db_path = os.getenv('SESSION_DB_PATH', './fuzzforge_sessions.db')
            # Convert to absolute path for SQLite URL
            abs_db_path = os.path.abspath(db_path)
            db_url = f"sqlite:///{abs_db_path}"
            if self.debug:
                print(f"[DEBUG] Using SQLite session persistence: {db_url}")
            return DatabaseSessionService(db_url=db_url)
        else:
            # Default to in-memory sessions
            if self.debug:
                print("[DEBUG] Using in-memory session service (non-persistent)")
            return InMemorySessionService()
    
    async def _get_cognee_service(self):
        """Get or initialize shared Cognee service"""
        if self.cognee_service is None or not self._cognee_initialized:
            try:
                from .cognee_service import CogneeService

                config = ProjectConfigManager()
                if not config.is_initialized():
                    raise ValueError("FuzzForge project not initialized. Run 'fuzzforge init' first.")

                self.cognee_service = CogneeService(config)
                await self.cognee_service.initialize()
                self._cognee_initialized = True
                
                if self.debug:
                    print("[DEBUG] Shared Cognee service initialized")
                    
            except Exception as e:
                if self.debug:
                    print(f"[DEBUG] Failed to initialize Cognee service: {e}")
                raise

        return self.cognee_service

    async def _get_knowledge_integration(self):
        """Get reusable Cognee project integration for structured queries."""
        if self._knowledge_integration is not None:
            return self._knowledge_integration

        try:
            from .cognee_integration import CogneeProjectIntegration

            integration = CogneeProjectIntegration()
            initialised = await integration.initialize()
            if not initialised:
                if self.debug:
                    print("[DEBUG] CogneeProjectIntegration initialization failed")
                return None

            self._knowledge_integration = integration
            return integration
        except Exception as exc:
            if self.debug:
                print(f"[DEBUG] Knowledge integration unavailable: {exc}")
            return None
        
    def _initialize_agent(self):
        """Initialize the LLM agent with tools"""
        # Build tools list
        tools = []
        
        # Add custom function tools for Cognee operations (making it callable as a tool)
        
        # Define Cognee tool functions
        async def cognee_add(text: str) -> str:
            """Add information to Cognee knowledge graph memory"""
            try:
                if self.cognee_service:
                    result = await self.cognee_service.add_to_memory(text)
                    return f"Added to Cognee: {result}"
                return "Cognee service not available"
            except Exception as e:
                return f"Error adding to Cognee: {e}"
        
        async def cognee_search(query: str) -> str:
            """Search Cognee knowledge graph memory"""
            try:
                if self.cognee_service:
                    results = await self.cognee_service.search_memory(query)
                    return f"Cognee search results: {results}"
                return "Cognee service not available"
            except Exception as e:
                return f"Error searching Cognee: {e}"
        
        # Add Cognee project integration tools
        async def search_project_knowledge(query: str, dataset: str, search_type: str) -> str:
            """Search the project's knowledge graph (codebase, documentation, specs, etc.)
            
            Args:
                query: Search query  
                dataset: Specific dataset to search (optional, searches all if empty)
                search_type: Type of search - any SearchType: INSIGHTS, CHUNKS, GRAPH_COMPLETION, CODE, SUMMARIES, RAG_COMPLETION, NATURAL_LANGUAGE, etc.
            """
            try:
                from cognee.modules.search.types import SearchType
                
                # Use shared cognee service
                cognee_service = await self._get_cognee_service()
                config = cognee_service.config
                
                # Get SearchType enum value dynamically
                try:
                    search_type_enum = getattr(SearchType, search_type.upper())
                except AttributeError:
                    # Fallback to INSIGHTS if invalid search type
                    search_type_enum = SearchType.INSIGHTS
                    search_type = "INSIGHTS"
                
                # Handle empty/default values
                if not dataset:
                    dataset = None
                if not search_type:
                    search_type = "INSIGHTS"
                    search_type_enum = SearchType.INSIGHTS
                
                # Use direct cognee import like ingest command
                import cognee
                
                # Set up user context
                try:
                    from cognee.modules.users.methods import get_user
                    user_email = f"project_{config.get_project_context()['project_id']}@fuzzforge.example"
                    user = await get_user(user_email)
                    cognee.set_user(user)
                except Exception:
                    pass  # User context not critical
                
                # Use cognee search directly for maximum flexibility
                search_kwargs = {
                    "query_type": search_type_enum,
                    "query_text": query
                }
                
                if dataset:
                    search_kwargs["datasets"] = [dataset]
                
                results = await cognee.search(**search_kwargs)
                
                if not results:
                    return f"No results found for '{query}'" + (f" in dataset '{dataset}'" if dataset else "")
                
                project_context = config.get_project_context()
                output = f"Search results for '{query}' in project {project_context['project_name']} (search_type: {search_type}):\n\n"
                
                for i, result in enumerate(results[:5], 1):  # Top 5 results
                    if isinstance(result, str):
                        preview = result[:200] + "..." if len(result) > 200 else result
                        output += f"{i}. {preview}\n\n"
                    else:
                        output += f"{i}. {str(result)[:200]}...\n\n"
                
                return output
                
            except Exception as e:
                return f"Error searching project knowledge: {e}"
        
        async def list_project_knowledge() -> str:
            """List available knowledge and datasets in the project's knowledge graph"""
            try:
                import logging
                logger = logging.getLogger(__name__)
                
                # Use shared cognee service
                cognee_service = await self._get_cognee_service()
                config = cognee_service.config
                
                project_context = config.get_project_context()
                result = f"Available knowledge in project {project_context['project_name']}:\n\n"
                
                # Use direct cognee import like ingest command does
                try:
                    import cognee
                    from cognee.modules.search.types import SearchType
                    
                    # Set up user context like ingest command  
                    try:
                        from cognee.modules.users.methods import create_user, get_user
                        
                        user_email = f"project_{project_context['project_id']}@fuzzforge.example"
                        user_tenant = project_context['tenant_id']
                        
                        try:
                            user = await get_user(user_email)
                            logger.info(f"Using existing user: {user_email}")
                        except Exception:
                            try:
                                user = await create_user(user_email, user_tenant)
                                logger.info(f"Created new user: {user_email}")
                            except Exception:
                                user = None
                        
                        if user:
                            cognee.set_user(user)
                    except Exception as e:
                        logger.warning(f"User context setup failed: {e}")
                    
                    # List available datasets
                    datasets = await cognee.datasets.list_datasets()
                    logger.info(f"Found datasets: {datasets}")
                    
                    if datasets and len(datasets) > 0:
                        dataset_name = f"{project_context['project_name']}_codebase"
                        
                        # Try to search for some basic info to show data exists
                        try:
                            sample_results = await cognee.search(
                                query_type=SearchType.INSIGHTS,
                                query_text="project overview files functions",
                                datasets=[dataset_name]
                            )
                            
                            if sample_results:
                                data = [f"Dataset '{dataset_name}' contains {len(sample_results)} insights"] + sample_results[:3]
                            else:
                                data = [f"Dataset '{dataset_name}' exists but no insights found"]
                        except Exception as search_e:
                            logger.info(f"Search failed: {search_e}")
                            data = [f"Dataset '{dataset_name}' exists in: {[str(ds) for ds in datasets]}"]
                    else:
                        data = None
                        
                except Exception as e:
                    data = None  
                    logger.warning(f"Error accessing cognee: {e}")
                
                if not data:
                    result += "No data available in knowledge graph\n"
                    result += "Use 'fuzzforge ingest' to ingest code, documentation, or other project files\n"
                else:
                    # Extract datasets from data
                    datasets = set()
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and 'dataset_name' in item:
                                datasets.add(item['dataset_name'])
                    
                    if datasets:
                        result += f"Available Datasets ({len(datasets)}):\n"
                        for i, dataset in enumerate(sorted(datasets), 1):
                            result += f"  {i}. {dataset}\n"
                        result += "\n"
                    
                    result += f"Total data items: {len(data)}\n"
                    
                    # Show sample of available data
                    result += "\nSample content:\n"
                    for i, item in enumerate(data[:3], 1):
                        if isinstance(item, dict):
                            item_str = str(item)[:100] + "..." if len(str(item)) > 100 else str(item)
                            result += f"  {i}. {item_str}\n"
                        else:
                            item_str = str(item)[:100] + "..." if len(str(item)) > 100 else str(item)
                            result += f"  {i}. {item_str}\n"
                
                return result
                
            except Exception as e:
                return f"Error listing knowledge: {e}"
        
        async def ingest_to_dataset(content: str, dataset: str) -> str:
            """Ingest text content (code, documentation, notes) into a specific project dataset
            
            Args:
                content: Text content to ingest (code, docs, specs, research, etc.)
                dataset: Dataset name to ingest into
            """
            try:
                # Use shared cognee service
                cognee_service = await self._get_cognee_service()
                config = cognee_service.config
                
                # Ingest the content
                success = await cognee_service.ingest_text(content, dataset)
                
                if success:
                    project_context = config.get_project_context()
                    return f"Successfully ingested {len(content)} characters into dataset '{dataset}' for project {project_context['project_name']}"
                else:
                    return f"Failed to ingest content into dataset '{dataset}'"
                    
            except Exception as e:
                return f"Error ingesting to dataset: {e}"
        
        async def cognify_information(text: str) -> str:
            """Transform information into knowledge graph format"""
            try:
                from .cognee_integration import CogneeProjectIntegration
                integration = CogneeProjectIntegration()
                result = await integration.cognify_text(text)
                
                if "error" in result:
                    return f"Error cognifying information: {result['error']}"
                
                project = result.get('project', 'Unknown')
                return f"Successfully transformed information into knowledge graph for project {project}"
            except Exception as e:
                return f"Error cognifying information: {e}"

        tools.extend([
            FunctionTool(search_project_knowledge),
            FunctionTool(list_project_knowledge), 
            FunctionTool(ingest_to_dataset),
            FunctionTool(cognify_information),
            FunctionTool(self.query_project_knowledge_api)
        ])
        
        # Add project-local filesystem tools
        async def list_project_files(path: str, pattern: str) -> str:
            """List files in the current project directory with optional pattern
            
            Args:
                path: Relative path within project (e.g. '.' for root, 'src', 'tests')
                pattern: Glob pattern (e.g. '*.py', '**/*.js', '') 
            """
            try:

                # Get project root from config
                config = ProjectConfigManager()
                if not config.is_initialized():
                    return "Project not initialized. Run 'fuzzforge init' first."

                project_root = config.config_path.parent  # Parent of .fuzzforge
                requested_path = project_root / path
                
                # Security check - ensure we stay within project
                try:
                    requested_path = requested_path.resolve()
                    project_root = project_root.resolve()
                    requested_path.relative_to(project_root)
                except ValueError:
                    return f"Access denied: Path '{path}' is outside project directory"
                
                if not requested_path.exists():
                    return f"Path does not exist: {path}"
                
                if not requested_path.is_dir():
                    return f"Not a directory: {path}"
                
                # List contents
                if not pattern:
                    # Simple directory listing
                    items = []
                    for item in sorted(requested_path.iterdir()):
                        relative = item.relative_to(project_root)
                        if item.is_dir():
                            items.append(f"📁 {relative}/")
                        else:
                            size = item.stat().st_size
                            size_str = f"({size} bytes)" if size < 1024 else f"({size//1024}KB)"
                            items.append(f"📄 {relative} {size_str}")
                    
                    return f"Project files in '{path}':\n" + "\n".join(items) if items else "Empty directory"
                else:
                    # Pattern matching
                    matches = list(requested_path.glob(pattern))
                    if matches:
                        files = []
                        for f in sorted(matches):
                            if f.is_file():
                                relative = f.relative_to(project_root)
                                size = f.stat().st_size
                                size_str = f" ({size//1024}KB)" if size >= 1024 else f" ({size}B)"
                                files.append(f"📄 {relative}{size_str}")
                        
                        return f"Found {len(files)} files matching '{pattern}' in project:\n" + "\n".join(files[:100])
                    else:
                        return f"No files found matching '{pattern}' in project path '{path}'"
                        
            except Exception as e:
                return f"Error listing project files: {e}"

        async def read_project_file(file_path: str, max_lines: int) -> str:
            """Read a file from the current project

            Args:
                file_path: Relative path to file within project
                max_lines: Maximum lines to read (0 for all, default 200 for large files)
            """
            try:

                # Get project root from config
                config = ProjectConfigManager()
                if not config.is_initialized():
                    return "Project not initialized. Run 'fuzzforge init' first."

                project_root = config.config_path.parent
                requested_file = project_root / file_path
                
                # Security check - ensure we stay within project  
                try:
                    requested_file = requested_file.resolve()
                    project_root = project_root.resolve()
                    requested_file.relative_to(project_root)
                except ValueError:
                    return f"Access denied: File '{file_path}' is outside project directory"
                
                if not requested_file.exists():
                    return f"File does not exist: {file_path}"
                    
                if not requested_file.is_file():
                    return f"Not a file: {file_path}"
                
                # Check file size
                size_mb = requested_file.stat().st_size / (1024 * 1024)
                if size_mb > 5:
                    return f"File too large ({size_mb:.1f} MB). Use max_lines parameter to read portions."
                
                # Set reasonable default for max_lines
                if max_lines == 0:
                    max_lines = 200 if size_mb > 0.1 else 0  # Default limit for larger files
                
                with open(requested_file, 'r', encoding='utf-8', errors='replace') as f:
                    if max_lines == 0:
                        content = f.read()
                    else:
                        lines = []
                        for i, line in enumerate(f, 1):
                            if i > max_lines:
                                lines.append(f"... (truncated at {max_lines} lines)")
                                break
                            lines.append(f"{i:4d}: {line.rstrip()}")
                        content = "\n".join(lines)
                
                relative_path = requested_file.relative_to(project_root)
                return f"Contents of {relative_path}:\n{content}"
                
            except UnicodeDecodeError:
                return f"Cannot read file (binary or encoding issue): {file_path}"
            except Exception as e:
                return f"Error reading file: {e}"

        async def search_project_files(search_pattern: str, file_pattern: str, path: str) -> str:
            """Search for text patterns in project files
            
            Args:
                search_pattern: Text/regex pattern to find
                file_pattern: File pattern to search in (e.g. '*.py', '**/*.js')
                path: Relative project path to search in (e.g. '.', 'src')
            """
            try:
                import re

                # Get project root from config
                config = ProjectConfigManager()
                if not config.is_initialized():
                    return "Project not initialized. Run 'fuzzforge init' first."
                
                project_root = config.config_path.parent
                search_path = project_root / path
                
                # Security check
                try:
                    search_path = search_path.resolve()
                    project_root = project_root.resolve()
                    search_path.relative_to(project_root)
                except ValueError:
                    return f"Access denied: Path '{path}' is outside project directory"
                
                if not search_path.exists():
                    return f"Search path does not exist: {path}"
                
                matches = []
                files_searched = 0
                
                # Search in files
                for file_path in search_path.glob(file_pattern):
                    if file_path.is_file():
                        files_searched += 1
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                                for line_num, line in enumerate(f, 1):
                                    if re.search(search_pattern, line, re.IGNORECASE):
                                        relative = file_path.relative_to(project_root)
                                        matches.append(f"{relative}:{line_num}: {line.strip()}")
                                        if len(matches) >= 50:  # Limit results
                                            break
                        except (PermissionError, OSError):
                            continue
                    
                    if len(matches) >= 50:
                        break
                
                if matches:
                    result = f"Found '{search_pattern}' in {len(matches)} locations (searched {files_searched} files):\n"
                    result += "\n".join(matches[:50])
                    if len(matches) >= 50:
                        result += "\n... (showing first 50 matches)"
                    return result
                else:
                    return f"No matches found for '{search_pattern}' in {files_searched} files matching '{file_pattern}'"
                    
            except Exception as e:
                return f"Error searching project files: {e}"
        
        tools.extend([
            FunctionTool(list_project_files),
            FunctionTool(read_project_file), 
            FunctionTool(search_project_files),
            FunctionTool(self.create_project_file_artifact_api)
        ])

        async def send_file_to_agent(agent_name: str, file_path: str, note: str, tool_context: ToolContext) -> str:
            """Send a local file to a registered agent (agent_name, file_path, note)."""
            # Handle empty note parameter
            if not note:
                note = ""
            
            session = None
            context_id = None
            if tool_context and getattr(tool_context, "invocation_context", None):
                invocation = tool_context.invocation_context
                session = invocation.session
                context_id = self.session_lookup.get(getattr(session, 'id', None))
            return await self.delegate_file_to_agent(agent_name, file_path, note, session=session, context_id=context_id)

        tools.append(FunctionTool(send_file_to_agent))

        if self.debug:
            print("[DEBUG] Added Cognee project integration tools")

        # Add FuzzForge backend workflow tools if MCP endpoint configured
        if self.fuzzforge_mcp_url:
            if self.debug:
                print(f"[DEBUG] FuzzForge MCP endpoint configured at {self.fuzzforge_mcp_url}")

            async def _call_fuzzforge_mcp(tool_name: str, payload: Dict[str, Any] | None = None) -> Any:
                return await self._call_mcp_generic(tool_name, payload or {})

            async def list_fuzzforge_workflows(tool_context: ToolContext | None = None) -> Any:
                return await _call_fuzzforge_mcp("list_workflows_mcp")

            async def get_fuzzforge_workflow_metadata(workflow_name: str, tool_context: ToolContext | None = None) -> Any:
                return await _call_fuzzforge_mcp("get_workflow_metadata_mcp", {"workflow_name": workflow_name})

            async def get_fuzzforge_workflow_parameters(workflow_name: str, tool_context: ToolContext | None = None) -> Any:
                return await _call_fuzzforge_mcp("get_workflow_parameters_mcp", {"workflow_name": workflow_name})

            async def get_fuzzforge_workflow_schema(tool_context: ToolContext | None = None) -> Any:
                return await _call_fuzzforge_mcp("get_workflow_metadata_schema_mcp")

            async def list_fuzzforge_runs(
                limit: int = 10,
                workflow_name: str = "",
                states: str = "",
                tool_context: ToolContext | None = None,
            ) -> Any:
                payload: Dict[str, Any] = {"limit": limit}
                workflow_name = (workflow_name or "").strip()
                if workflow_name:
                    payload["workflow_name"] = workflow_name

                state_tokens = [
                    token.strip()
                    for token in (states or "").split(",")
                    if token.strip()
                ]
                if state_tokens:
                    payload["states"] = state_tokens
                return await _call_fuzzforge_mcp("list_recent_runs_mcp", payload)

            async def submit_security_scan_mcp(
                workflow_name: str,
                target_path: str = "",
                volume_mode: str = "",
                parameters: Dict[str, Any] | None = None,
                tool_context: ToolContext | None = None,
            ) -> Any:
                # Normalise volume mode to supported values
                normalised_mode = (volume_mode or "ro").strip().lower().replace("-", "_")
                if normalised_mode in {"read_only", "readonly", "ro"}:
                    normalised_mode = "ro"
                elif normalised_mode in {"read_write", "readwrite", "rw"}:
                    normalised_mode = "rw"
                else:
                    # Fall back to read-only if we can't recognise the input
                    normalised_mode = "ro"

                # Resolve the target path to an absolute path for validation
                resolved_path = target_path or "."
                try:
                    resolved_path = str(Path(resolved_path).expanduser().resolve())
                except Exception:
                    # If resolution fails, use the raw value
                    resolved_path = target_path

                # Ensure configuration objects default to dictionaries instead of None
                cleaned_parameters: Dict[str, Any] = {}
                if parameters:
                    for key, value in parameters.items():
                        if isinstance(key, str) and key.endswith("_config") and value is None:
                            cleaned_parameters[key] = {}
                        else:
                            cleaned_parameters[key] = value

                # Merge in default parameter schema for known workflows to avoid missing dicts
                try:
                    param_info = await get_fuzzforge_workflow_parameters(workflow_name)
                    if isinstance(param_info, dict):
                        defaults = param_info.get("defaults") or {}
                        if isinstance(defaults, dict):
                            for key, value in defaults.items():
                                if key.endswith("_config") and key not in cleaned_parameters:
                                    cleaned_parameters[key] = value or {}
                except Exception:
                    # Defaults fetch is best-effort – continue with whatever we have
                    pass

                # Final pass – replace any lingering None configs with empty dicts
                for key, value in list(cleaned_parameters.items()):
                    if isinstance(key, str) and key.endswith("_config") and value is None:
                        cleaned_parameters[key] = {}

                payload = {
                    "workflow_name": workflow_name,
                    "target_path": resolved_path,
                    "volume_mode": normalised_mode,
                    "parameters": cleaned_parameters,
                }
                result = await _call_fuzzforge_mcp("submit_security_scan_mcp", payload)

                if isinstance(result, dict):
                    run_id = result.get("run_id") or result.get("id")
                    if run_id and tool_context:
                        context_id = tool_context.invocation_context.session.id
                        session_meta = self.session_metadata.get(context_id, {})
                        self.pending_runs[run_id] = {
                            "context_id": context_id,
                            "session_id": session_meta.get("session_id"),
                            "user_id": session_meta.get("user_id"),
                            "app_name": session_meta.get("app_name", "fuzzforge"),
                            "workflow_name": workflow_name,
                            "submitted_at": datetime.now().isoformat(),
                        }
                        tool_context.actions.state_delta[
                            f"fuzzforge.run.{run_id}.status"
                        ] = "submitted"
                        await self._publish_task_pending(run_id, context_id, workflow_name)
                        self._schedule_run_followup(run_id)

                return result

            async def get_fuzzforge_run_status(run_id: str, tool_context: ToolContext | None = None) -> Any:
                return await _call_fuzzforge_mcp("get_run_status_mcp", {"run_id": run_id})

            async def get_fuzzforge_summary(run_id: str, tool_context: ToolContext | None = None) -> Any:
                return await _call_fuzzforge_mcp("get_comprehensive_scan_summary", {"run_id": run_id})

            async def get_fuzzforge_findings(run_id: str, tool_context: ToolContext | None = None) -> Any:
                return await _call_fuzzforge_mcp("get_run_findings_mcp", {"run_id": run_id})

            async def get_fuzzforge_fuzzing_stats(run_id: str, tool_context: ToolContext | None = None) -> Any:
                return await _call_fuzzforge_mcp("get_fuzzing_stats_mcp", {"run_id": run_id})

            tools.extend([
                FunctionTool(list_fuzzforge_workflows),
                FunctionTool(get_fuzzforge_workflow_metadata),
                FunctionTool(get_fuzzforge_workflow_parameters),
                FunctionTool(get_fuzzforge_workflow_schema),
                FunctionTool(list_fuzzforge_runs),
                LongRunningFunctionTool(submit_security_scan_mcp),
                FunctionTool(get_fuzzforge_run_status),
                FunctionTool(get_fuzzforge_summary),
                FunctionTool(get_fuzzforge_findings),
                FunctionTool(get_fuzzforge_fuzzing_stats),
            ])
        
        # Add agent introspection tools
        async def get_agent_capabilities(agent_name: str) -> str:
            """Get detailed capabilities and tools of a registered agent"""
            # Handle empty agent_name
            if not agent_name or agent_name.strip() == "":
                # List all agents with their capabilities
                if not self.agents:
                    return "No agents are currently registered"
                
                result = "Registered agents and their capabilities:\n\n"
                for name, info in self.agents.items():
                    card = info.get("card", {})
                    result += f"{name}\n"
                    result += f"   Description: {card.get('description', 'No description')}\n"
                    
                    # Get skills/tools from agent card
                    skills = card.get('skills', [])
                    if skills:
                        result += f"   Tools ({len(skills)}):\n"
                        for skill in skills:
                            skill_name = skill.get('name', 'Unknown')
                            skill_desc = skill.get('description', 'No description')
                            result += f"     - {skill_name}: {skill_desc}\n"
                    else:
                        result += "   Tools: Not specified in agent card\n"
                    result += "\n"
                return result
            else:
                # Get specific agent details
                if agent_name not in self.agents:
                    return f"Agent '{agent_name}' not found. Available agents: {', '.join(self.agents.keys())}"
                
                info = self.agents[agent_name]
                card = info.get("card", {})
                
                result = f"{agent_name} - Detailed Capabilities\n\n"
                result += f"URL: {info.get('url')}\n"
                result += f"Description: {card.get('description', 'No description')}\n\n"
                
                # Detailed skills/tools
                skills = card.get('skills', [])
                if skills:
                    result += f"Available Tools ({len(skills)}):\n"
                    for i, skill in enumerate(skills, 1):
                        skill_name = skill.get('name', 'Unknown')
                        skill_desc = skill.get('description', 'No description')
                        result += f"{i}. {skill_name}\n   {skill_desc}\n\n"
                else:
                    result += "Tools: Not specified in agent card\n\n"
                
                # Additional capabilities
                capabilities = card.get('capabilities', {})
                if capabilities:
                    result += "Capabilities:\n"
                    for key, value in capabilities.items():
                        result += f"  - {key}: {value}\n"
                    result += "\n"
                
                # Input/Output modes
                input_modes = card.get('defaultInputModes', card.get('default_input_modes', []))
                output_modes = card.get('defaultOutputModes', card.get('default_output_modes', []))
                
                if input_modes:
                    result += f"Supported Input Modes: {', '.join(input_modes)}\n"
                if output_modes:
                    result += f"Supported Output Modes: {', '.join(output_modes)}\n"
                
                return result
        
        # Add task tracking tools
        async def create_task_list(tasks: List[str]) -> str:
            """Create a task list for tracking project progress"""
            if not hasattr(self, 'task_lists'):
                self.task_lists = {}
            
            task_id = f"task_list_{len(self.task_lists)}"
            self.task_lists[task_id] = {
                'tasks': [{'id': i, 'description': task, 'status': 'pending'} for i, task in enumerate(tasks)],
                'created_at': datetime.now().isoformat()
            }
            return f"Created task list {task_id} with {len(tasks)} tasks"
        
        async def update_task_status(task_list_id: str, task_id: int, status: str) -> str:
            """Update the status of a task (pending, in_progress, completed)"""
            if not hasattr(self, 'task_lists') or task_list_id not in self.task_lists:
                return f"Task list {task_list_id} not found"
            
            tasks = self.task_lists[task_list_id]['tasks']
            for task in tasks:
                if task['id'] == task_id:
                    task['status'] = status
                    return f"Updated task {task_id} to {status}"
            return f"Task {task_id} not found"
        
        async def get_task_list(task_list_id: str) -> str:
            """Get current task list status"""
            # Handle empty task_list_id
            if not task_list_id or task_list_id.strip() == "":
                task_list_id = "default"
            
            if not hasattr(self, 'task_lists'):
                return "No task lists created"
            
            if task_list_id:
                if task_list_id in self.task_lists:
                    tasks = self.task_lists[task_list_id]['tasks']
                    result = f"Task List {task_list_id}:\n"
                    for task in tasks:
                        result += f"  [{task['status']}] {task['id']}: {task['description']}\n"
                    return result
                return f"Task list {task_list_id} not found"
            else:
                # Return all task lists
                result = "All task lists:\n"
                for list_id, list_data in self.task_lists.items():
                    completed = sum(1 for t in list_data['tasks'] if t['status'] == 'completed')
                    total = len(list_data['tasks'])
                    result += f"  {list_id}: {completed}/{total} completed\n"
                return result
        
        tools.extend([
            FunctionTool(get_agent_capabilities),
            FunctionTool(create_task_list),
            FunctionTool(update_task_status),
            FunctionTool(get_task_list)
        ])

        
        # Create the agent
        self.agent = LlmAgent(
            model=LiteLlm(model=self.model),
            name="fuzzforge_executor",
            description="Intelligent A2A orchestrator with memory",
            instruction=self._build_instruction(),
            tools=tools  # Always pass tools list (empty list is fine)
        )
        
        # Create runner with our session service
        self.runner = Runner(
            agent=self.agent,
            session_service=self.session_service,  # Use our configured session service
            app_name="fuzzforge"
        )
        
        # Connect runner to our artifact service
        if hasattr(self.runner, 'artifact_service'):
            # Override with our configured artifact service
            self.runner.artifact_service = self.artifact_service
        
    def _build_instruction(self) -> str:
        """Build the agent's instruction prompt"""
        instruction = """You are FuzzForge, an intelligent A2A orchestrator with dual memory systems.

## Your Core Responsibilities:

1. **Agent Orchestration (Primary)**
   - Always use get_agent_capabilities() tool to check available agents
   - When users ask about agent tools/capabilities, use get_agent_capabilities(agent_name)
   - When a user mentions any registered agent by name, delegate to that agent
   - When a request matches an agent's capabilities, route to it
   - To route to an agent, format your response as: "ROUTE_TO: [agent_name] [message]"
   - The system follows A2A protocol standards for agent communication
   - Be agent-agnostic - work with whatever agents are registered
   - Prefer using your built-in FuzzForge workflow tools directly unless the user explicitly requests delegation

2. **FuzzForge Platform Tools (Secondary)**
   - Use your FuzzForge MCP tools by default for workflow submission, monitoring, and findings retrieval
   - Use the appropriate tool for the user's request
   - You can submit and monitor FuzzForge workflows via MCP tools (list_workflows_mcp, submit_security_scan_mcp, list_recent_runs_mcp, get_run_status_mcp, get_comprehensive_scan_summary)
   - Treat any absolute path the user provides as mountable; the backend handles volume access. Do NOT ask the user to upload, move, or zip projects—just call submit_security_scan_mcp with the supplied path and options.
   - When asked to send local files or binaries to another agent, call send_file_to_agent(agent_name, file_path, note="...")

3. **Dual Memory Systems**:
   
   a) **Conversational Memory** (ADK MemoryService - for past conversations)
      - Automatically ingests completed sessions
      - Search with "recall from past conversations about X"
      - Uses semantic search (VertexAI) or keyword matching (InMemory)
      
   b) **Project Knowledge Graph** (Cognee - for ingested code, documentation, specs, and structured data)
      - Use search_project_knowledge(query, dataset="", search_type="INSIGHTS") to search project knowledge
      - Available search_type options: INSIGHTS, CHUNKS, GRAPH_COMPLETION, CODE, SUMMARIES, RAG_COMPLETION, NATURAL_LANGUAGE, CYPHER, TEMPORAL, FEELING_LUCKY
      - Use list_project_knowledge() to see available datasets and knowledge
      - Use ingest_to_dataset(content, dataset) to add content to specific datasets
      - Use cognify_information(text) to add new information to knowledge graph
      - Automatically uses current project context and directory
      - Example: "what functions are in the codebase?" -> use search_project_knowledge("functions classes methods", search_type="CHUNKS")
      - Example: "what documentation exists?" -> use search_project_knowledge("documentation specs readme", search_type="INSIGHTS")
      - Example: "search security docs" -> use search_project_knowledge("security vulnerabilities", dataset="security_docs")

   c) **Project Filesystem Access** (Project-local file operations)
      - Use list_project_files(path, pattern) to explore project structure
      - Use read_project_file(file_path, max_lines) to examine file contents  
      - Use search_project_files(search_pattern, file_pattern, path) to find text in files
      - All file operations are restricted to the current project directory for security
      - Example: "show me all Python files" -> use list_project_files(".", "*.py")
      - Example: "read the main agent file" -> use read_project_file("agent.py", 0)
      - Example: "find TODO comments" -> use search_project_files("TODO", "**/*.py", ".")

4. **Artifact Creation**
   - When generating code, configurations, or documents, create an artifact
   - Format: "ARTIFACT: [type] [title]\n```\n[content]\n```"
   - Types: code, config, document, data, diagram

5. **Multi-Step Task Execution with Graph Building**
   - Chain multiple actions together
   - When user says "ask agent X and then save to memory":
     a) Route to agent X
     b) Use `cognify` to structure the response as a knowledge graph
     c) This automatically creates searchable nodes and relationships
   - Build a growing knowledge graph from all interactions
   - Connect new information to existing graph nodes

6. **General Assistance**
   - Only answer directly if no suitable agent is registered AND no FuzzForge tool can help
   - Provide helpful responses
   - Maintain conversation context

## Tool Usage Protocol:
- ALWAYS use get_agent_capabilities() tool when asked about agents or their tools
- Use get_agent_capabilities(agent_name) for specific agent details
- Use get_agent_capabilities() without parameters to list all agents
- If an agent's skills/description match the request, use "ROUTE_TO: [name] [message]"
- After receiving agent response:
  - If user wants to save/store: Use `cognify` to create knowledge graph
  - Structure the data as: entities (nodes) and relationships (edges)
  - Example cognify text: "Entity: 1001 (Number). Property: is_prime=false. Relationship: 1001 CHECKED_BY CalculatorAgent. Relationship: 1001 HAS_FACTORS [7, 11, 13]"
- When searching memory, use GRAPH_COMPLETION mode to traverse relationships

## Important Rules:
- NEVER mention specific types of agents or tasks in greetings
- Do NOT say things like "I can run calculations" or mention specific capabilities
- Keep greetings generic: just say you're an orchestrator that can help
- When user asks for chained actions, acknowledge and execute all steps

Be concise and intelligent in your responses."""
        
        
        return instruction
    
    async def execute(self, message: str, context_id: str = None) -> Dict[str, Any]:
        """Execute a task/message and return the result"""
        
        # Use default context if none provided
        if not context_id:
            context_id = "default"
            
        # Get or create session
        if context_id not in self.sessions:
            session_obj = await self._create_session()
            self.sessions[context_id] = session_obj
            self.session_metadata[context_id] = {
                "session_id": getattr(session_obj, 'id', context_id),
                "user_id": getattr(session_obj, 'user_id', 'user'),
                "app_name": getattr(session_obj, 'app_name', 'fuzzforge'),
            }
            if self.debug:
                print(f"[DEBUG] Created new session for context: {context_id}")
        
        session = self.sessions[context_id]
        session_id = getattr(session, 'id', context_id)
        self.session_lookup[session_id] = context_id
        if context_id not in self.session_metadata:
            self.session_metadata[context_id] = {
                "session_id": getattr(session, 'id', context_id),
                "user_id": getattr(session, 'user_id', 'user'),
                "app_name": getattr(session, 'app_name', 'fuzzforge'),
            }
        
        # Search conversational memory if relevant
        if self.memory_service and any(word in message.lower() for word in ['recall', 'remember', 'past conversation', 'previously']):
            try:
                memory_results = await self.memory_service.search_memory(
                    query=message,
                    app_name="fuzzforge",
                    user_id=getattr(session, 'user_id', 'user')
                )
                if memory_results and memory_results.memories:
                    # Add memory context to session state
                    # MemoryEntry has 'text' field
                    session.state["memory_context"] = [
                        {"text": getattr(m, 'text', str(m))}
                        for m in memory_results.memories
                    ]
                    if self.debug:
                        print(f"[DEBUG] Found {len(memory_results.memories)} memories")
            except Exception as e:
                if self.debug:
                    print(f"[DEBUG] Memory search failed: {e}")
        
        # Update session with registered agents following A2A AgentCard standard
        registered_agents = []
        for name, info in self.agents.items():
            card = info.get("card", {})
            skills = card.get("skills", [])
            
            # Format according to A2A AgentSkill standard
            agent_info = {
                "name": name,
                "url": info["url"],
                "description": card.get("description", ""),
                "skills": [
                    {
                        "id": skill.get("id", ""),
                        "name": skill.get("name", ""),
                        "description": skill.get("description", ""),
                        "tags": skill.get("tags", [])
                    }
                    for skill in skills
                ],
                "skill_count": len(skills),
                "default_input_modes": card.get("defaultInputModes", card.get("default_input_modes", [])),
                "default_output_modes": card.get("defaultOutputModes", card.get("default_output_modes", []))
            }
            registered_agents.append(agent_info)
        
        session.state["registered_agents"] = registered_agents
        session.state["agent_names"] = list(self.agents.keys())
        
        # Track if this is a multi-step request
        multi_step_keywords = ["and then", "then save", "and save", "store the", "save the result", "save to memory", "remember"]
        is_multi_step = any(keyword in message.lower() for keyword in multi_step_keywords)
        
        if is_multi_step:
            session.state["multi_step_request"] = message
            session.state["pending_actions"] = []
        
        # Process with LLM
        content = types.Content(
            role='user',
            parts=[types.Part.from_text(text=message)]
        )
        
        response = ""
        try:
            # Try to use existing session ID or create a new one
            session_id = getattr(session, 'id', context_id)
            user_id = getattr(session, 'user_id', 'user')
            
            if self.debug:
                print(f"[DEBUG] Running with session_id: {session_id}, user_id: {user_id}")
            
            async for event in self.runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=content
            ):
                # Check if event has content before accessing parts
                if event and event.content:
                    # Normal content handling
                    if event.content:
                        if hasattr(event.content, 'parts') and event.content.parts:
                            # Get text from the first part that has text
                            for part in event.content.parts:
                                if hasattr(part, 'text') and part.text:
                                    response = part.text
                                    break
                            if not response and len(event.content.parts) > 0:
                                # Fallback to string representation
                                response = str(event.content.parts[0])
                        elif hasattr(event.content, 'text'):
                            # Direct text content
                            response = event.content.text
                        else:
                            # Log for debugging
                            if self.debug:
                                print(f"[DEBUG] Event content type: {type(event.content)}, has parts: {hasattr(event.content, 'parts')}")
                    
                    # Check if LLM wants to route to an agent
                    if "ROUTE_TO:" in response:
                        # Extract routing command from response
                        route_line = None
                        for line in response.split('\n'):
                            if line.strip().startswith("ROUTE_TO:"):
                                route_line = line.strip()
                                break
                        
                        if route_line:
                            # Parse routing command more robustly
                            route_content = route_line[9:].strip()  # Remove "ROUTE_TO:"
                            
                            # Try to match against registered agents
                            agent_name = None
                            agent_message = route_content
                            
                            # Check each registered agent name
                            for registered_name in self.agents.keys():
                                if route_content.lower().startswith(registered_name.lower()):
                                    agent_name = registered_name
                                    # Extract message after agent name
                                    agent_message = route_content[len(registered_name):].strip()
                                    break
                            
                            if not agent_name:
                                # Fallback: try first word as agent name
                                parts = route_content.split(None, 1)
                                if parts:
                                    agent_name = parts[0]
                                    agent_message = parts[1] if len(parts) > 1 else message
                            
                            # Route to the agent
                            if agent_name in self.agents:
                                try:
                                    connection = self.agents[agent_name]["connection"]
                                    routed_response = await connection.send_message(agent_message)
                                    agent_result = f"[{agent_name}]: {routed_response}"
                                    
                                    # If this was a multi-step request, process next steps
                                    if is_multi_step:
                                        # Store the agent response for next action
                                        session.state["last_agent_response"] = routed_response
                                        
                                        # Ask LLM to continue with next steps
                                        followup_content = types.Content(
                                            role='user',
                                            parts=[types.Part.from_text(
                                                text=f"The agent responded: {routed_response}\n\nNow complete the remaining actions from the original request: {message}"
                                            )]
                                        )
                                        
                                        # Process followup
                                        async for followup_event in self.runner.run_async(
                                            user_id=user_id,
                                            session_id=session_id,
                                            new_message=followup_content
                                        ):
                                            if followup_event.content.parts and followup_event.content.parts[0].text:
                                                followup_response = followup_event.content.parts[0].text
                                                response = f"{agent_result}\n\n{followup_response}"
                                                break
                                    else:
                                        response = agent_result
                                        
                                except Exception as e:
                                    response = f"Error routing to {agent_name}: {e}"
                            else:
                                response = f"Agent {agent_name} not found. Available agents: {', '.join(self.agents.keys())}"
                    
                    # Check for artifacts in response
                    elif "ARTIFACT:" in response:
                        response = await self._extract_and_store_artifact(response, session, context_id)
        except Exception as e:
            if self.debug:
                print(f"[DEBUG] Runner error: {e}")
                print(f"[DEBUG] Error type: {type(e).__name__}")
                import traceback
                print(f"[DEBUG] Traceback: {traceback.format_exc()}")
            # Fallback to direct agent response
            response = f"I encountered an issue processing your request: {str(e) if self.debug else 'Please try again.'}"
        
        try:
            save_session = getattr(self.runner.session_service, "save_session", None)
            if callable(save_session):
                await save_session(session)
        except Exception as exc:
            if self.debug:
                print(f"[DEBUG] Failed to save session: {exc}")

        return {
            "response": response or "No response generated",
            "context_id": context_id,
            "routed": False
        }
    
    async def _create_session(self) -> Any:
        """Create a new session"""
        try:
            # Create session with proper parameters
            session = await self.runner.session_service.create_session(
                app_name="fuzzforge",
                user_id=f"user_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            return session
        except Exception as e:
            # If session service fails, create a simple mock session
            if self.debug:
                print(f"[DEBUG] Session creation failed: {e}, using mock session")
            
            # Return a simple session object
            from types import SimpleNamespace
            return SimpleNamespace(
                id=f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                state={},
                app_name="fuzzforge",
                user_id="user"
            )
    
    
    async def _extract_and_store_artifact(self, response: str, session: Any, context_id: str) -> str:
        """Extract and store artifacts from response using ADK artifact service (A2A compliant)"""
        import re
        
        # Pattern to match artifact format - handle both inline and multiline formats
        # Format: ARTIFACT: type filename\n```content``` (with possible extra newlines)
        pattern = r'ARTIFACT:\s*(\w+)\s+(.+?)\s*\n```([^`]*?)```'
        matches = re.findall(pattern, response, re.DOTALL)
        
        if self.debug:
            print(f"[DEBUG] Looking for artifacts in response. Found {len(matches)} matches.")
            if matches:
                for i, (artifact_type, title, content) in enumerate(matches):
                    print(f"[DEBUG] Artifact {i+1}: type={artifact_type}, title={title.strip()}, content_length={len(content)}")
            else:
                # Show first 500 chars of response to debug regex issues
                print(f"[DEBUG] No artifacts found. Response preview: {response[:500]}...")
        
        if matches:
            artifacts_created = []
            
            for artifact_type, title, content in matches:
                # Determine MIME type based on artifact type
                mime_type_map = {
                    "code": "text/plain",
                    "c": "text/x-c",
                    "cpp": "text/x-c++",
                    "python": "text/x-python",
                    "javascript": "text/javascript",
                    "json": "application/json",
                    "config": "text/plain",
                    "document": "text/markdown",
                    "data": "application/json",
                    "diagram": "text/plain",
                    "yaml": "text/yaml",
                    "xml": "text/xml",
                    "html": "text/html"
                }
                mime_type = mime_type_map.get(artifact_type, "text/plain")
                
                # Create proper A2A artifact format  
                title_clean = title.strip().replace(' ', '_')
                # If title already has extension, use it as-is, otherwise add artifact_type as extension
                if '.' in title_clean:
                    filename = title_clean
                else:
                    filename = f"{title_clean}.{artifact_type}"
                artifact_id = f"artifact_{uuid.uuid4().hex[:8]}"
                
                try:
                    # Store using ADK artifact service if available
                    if self.artifact_service:
                        # Create artifact metadata for A2A
                        artifact_metadata = {
                            "id": artifact_id,
                            "name": title.strip(),
                            "type": artifact_type,
                            "mimeType": mime_type,
                            "filename": filename,
                            "size": len(content),
                            "createdAt": datetime.now().isoformat()
                        }
                        
                        # Store content in artifact service
                        # Save to ADK artifact service using correct API
                        try:
                            from google.genai import types
                            
                            # Detect content type and extension from artifact metadata
                            filename = artifact_metadata.get("filename", f"{artifact_id}.txt")
                            mime_type = artifact_metadata.get("mimeType", "text/plain")
                            
                            # Handle different content types
                            if isinstance(content, str):
                                content_bytes = content.encode('utf-8')
                            elif isinstance(content, bytes):
                                content_bytes = content
                            else:
                                content_bytes = str(content).encode('utf-8')
                            
                            # Create ADK artifact using correct API
                            artifact_part = types.Part(
                                inline_data=types.Blob(
                                    mime_type=mime_type,
                                    data=content_bytes
                                )
                            )
                            
                            # Save using ADK artifact service
                            await self.artifact_service.save_artifact(
                                filename=filename,
                                artifact=artifact_part
                            )
                            
                            if self.debug:
                                print(f"[DEBUG] Saved artifact to ADK service: {filename}")
                                
                        except ImportError as e:
                            # Fallback: just store in local cache if ADK not available
                            if self.debug:
                                print(f"[DEBUG] ADK types not available ({e}), using local storage only")
                        except Exception as e:
                            if self.debug:
                                print(f"[DEBUG] ADK artifact service error: {e}, using local storage only")
                        
                        if self.debug:
                            print(f"[DEBUG] Saved artifact to service: {artifact_id}")
                    
                    # Store to file system cache for HTTP serving
                    try:
                        content_bytes = content.encode('utf-8') if isinstance(content, str) else content
                        sha256_digest = hashlib.sha256(content_bytes).hexdigest()
                        
                        file_cache_result = self._register_artifact_bytes(
                            name=filename,
                            data=content_bytes,
                            mime_type=mime_type,
                            sha256_digest=sha256_digest,
                            size=len(content_bytes),
                            artifact_id=artifact_id  # Use the display ID for file system
                        )
                        
                        if self.debug:
                            print(f"[DEBUG] Stored artifact to file cache: {file_cache_result['file_uri']}")
                    except Exception as e:
                        if self.debug:
                            print(f"[DEBUG] Failed to store to file cache: {e}")
                    
                    # Also store in local cache for quick access
                    if context_id not in self.artifacts:
                        self.artifacts[context_id] = []
                    
                    artifact = {
                        "id": artifact_id,
                        "type": artifact_type,
                        "title": title.strip(),
                        "filename": filename,
                        "mimeType": mime_type,
                        "content": content.strip(),
                        "size": len(content),
                        "created_at": datetime.now().isoformat()
                    }
                    
                    self.artifacts[context_id].append(artifact)
                    artifacts_created.append(f"{title.strip()} ({artifact_type})")
                    
                    if self.debug:
                        print(f"[DEBUG] Stored artifact: {artifact['id']} - {artifact['title']}")
                        
                except Exception as e:
                    if self.debug:
                        print(f"[DEBUG] Failed to store artifact: {e}")
            
            # Create A2A compliant response with artifact references
            artifact_list = ", ".join(artifacts_created)
            clean_response = re.sub(pattern, "", response)
            
            # Add artifact notification in A2A format
            artifact_response = f"{clean_response}\n\n📎 Created artifacts: {artifact_list}"
            
            return artifact_response
        
        return response
    
    async def get_artifacts(self, context_id: str = None) -> List[Dict[str, Any]]:
        """Get artifacts for a context or all artifacts"""
        if self.debug:
            print(f"[DEBUG] get_artifacts called with context_id: {context_id}")
            print(f"[DEBUG] Available artifact contexts: {list(self.artifacts.keys())}")
            print(f"[DEBUG] Total artifacts stored: {sum(len(artifacts) for artifacts in self.artifacts.values())}")
        
        if context_id:
            result = self.artifacts.get(context_id, [])
            if self.debug:
                print(f"[DEBUG] Returning {len(result)} artifacts for context {context_id}")
            return result
        
        # Return all artifacts
        all_artifacts = []
        for ctx_id, artifacts in self.artifacts.items():
            for artifact in artifacts:
                artifact_copy = artifact.copy()
                artifact_copy['context_id'] = ctx_id
                all_artifacts.append(artifact_copy)
        
        if self.debug:
            print(f"[DEBUG] Returning {len(all_artifacts)} total artifacts")
        return all_artifacts
    
    def format_artifacts_for_a2a(self, context_id: str) -> List[Dict[str, Any]]:
        """Format artifacts for A2A protocol response"""
        artifacts = self.artifacts.get(context_id, [])
        a2a_artifacts = []
        
        for artifact in artifacts:
            # Create A2A compliant artifact format
            a2a_artifact = {
                "id": artifact["id"],
                "type": "artifact",
                "mimeType": artifact.get("mimeType", "text/plain"),
                "name": artifact.get("title", artifact.get("filename", "untitled")),
                "parts": [
                    {
                        "type": "text",
                        "text": artifact.get("content", "")
                    }
                ],
                "metadata": {
                    "filename": artifact.get("filename"),
                    "size": artifact.get("size", 0),
                    "createdAt": artifact.get("created_at")
                }
            }
            a2a_artifacts.append(a2a_artifact)
        
        return a2a_artifacts
    
    async def register_agent(self, url: str) -> Dict[str, Any]:
        """Register a new A2A agent with persistence"""
        try:
            conn = RemoteAgentConnection(url)
            card = await conn.get_agent_card()
            
            if not card:
                return {"success": False, "error": "Failed to get agent card"}
            
            name = card.get("name", f"agent_{len(self.agents)}")
            description = card.get("description", "")
            
            self.agents[name] = {
                "url": url,
                "card": card,
                "connection": conn
            }
            
            if self.debug:
                print(f"[DEBUG] Registered agent {name} for ROUTE_TO delegation")
            
            # Update session state with registered agents for the LLM
            if hasattr(self, 'sessions'):
                for session in self.sessions.values():
                    if hasattr(session, 'state'):
                        session.state["registered_agents"] = list(self.agents.keys())
            
            # Persist to config
            from .config_manager import ConfigManager
            config_mgr = ConfigManager()
            config_mgr.add_registered_agent(name, url, description)
            
            return {
                "success": True,
                "name": name,
                "capabilities": len(card.get("skills", [])),
                "description": description
            }
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def list_agents(self) -> List[Dict[str, Any]]:
        """List all registered agents"""
        return [
            {
                "name": name,
                "url": info["url"],
                "description": info.get("card", {}).get("description", ""),
                "skills": len(info.get("card", {}).get("skills", []))
            }
            for name, info in self.agents.items()
        ]
    
    async def cleanup(self):
        """Clean up resources"""
        # Close agent connections
        for agent in self.agents.values():
            conn = agent.get("connection")
            if conn:
                await conn.close()

        # End AgentOps trace
        if self.agentops_trace:
            try:
                agentops.end_trace()
            except Exception:
                pass

        # Cancel background monitors
        for task in list(self._background_tasks):
            task.cancel()
        self._background_tasks.clear()

    def _schedule_run_followup(self, run_id: str) -> None:
        if run_id not in self.pending_runs:
            return

        try:
            task = asyncio.create_task(self._monitor_run_and_notify(run_id), name=f"fuzzforge_run_{run_id}")
            self._background_tasks.add(task)

            def _cleanup(t: asyncio.Task) -> None:
                self._background_tasks.discard(t)
                try:
                    t.result()
                except asyncio.CancelledError:
                    if self.debug:
                        print(f"[DEBUG] Run monitor for {run_id} cancelled")
                except Exception as exc:
                    if self.debug:
                        print(f"[DEBUG] Run monitor for {run_id} failed: {exc}")

            task.add_done_callback(_cleanup)
        except RuntimeError as exc:
            if self.debug:
                print(f"[DEBUG] Unable to schedule run follow-up: {exc}")

    async def _monitor_run_and_notify(self, run_id: str) -> None:
        try:
            run_meta = self.pending_runs.get(run_id)
            if not run_meta:
                return
            context_id = run_meta.get("context_id")
            while True:
                status = await self._call_mcp_status(run_id)
                if isinstance(status, dict) and status.get("is_completed"):
                    break
                await asyncio.sleep(5)

            summary = await self._call_mcp_summary(run_id)
            findings: Any | None = None
            try:
                findings = await self._call_mcp_generic(
                    "get_run_findings_mcp", {"run_id": run_id}
                )
            except Exception as exc:
                if self.debug:
                    print(f"[DEBUG] Unable to fetch findings for {run_id}: {exc}")

            artifact_info = None
            try:
                artifact_info = await self._create_run_artifact(
                    run_id=run_id,
                    run_meta=run_meta,
                    status=status,
                    summary=summary,
                    findings=findings,
                )
                if artifact_info:
                    run_meta["artifact"] = artifact_info
            except Exception as exc:
                if self.debug:
                    print(f"[DEBUG] Failed to create artifact for {run_id}: {exc}")

            message = self._format_run_summary(run_id, status, summary)
            if artifact_info and artifact_info.get("file_uri"):
                message += (
                    f"\nArtifact: {artifact_info['file_uri']}"
                    f" ({artifact_info.get('name', 'run-summary')})"
                )
            if context_id:
                await self._append_session_message(context_id, message, run_id)
            await self._publish_task_update(
                run_id,
                context_id,
                status,
                summary,
                message,
                artifact_info,
            )
            self.pending_runs.pop(run_id, None)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if self.debug:
                print(f"[DEBUG] Follow-up notification failed for {run_id}: {exc}")

    async def _call_mcp_status(self, run_id: str) -> Any:
        return await self._call_mcp_generic("get_run_status_mcp", {"run_id": run_id})

    async def _call_mcp_summary(self, run_id: str) -> Any:
        return await self._call_mcp_generic("get_comprehensive_scan_summary", {"run_id": run_id})

    async def _call_mcp_generic(self, tool_name: str, payload: Dict[str, Any]) -> Any:
        if not self.fuzzforge_mcp_url:
            return {"error": "FUZZFORGE_MCP_URL not configured"}

        try:
            from fastmcp.client import Client
        except ImportError as exc:
            return {"error": f"fastmcp not installed: {exc}"}

        async with Client(self.fuzzforge_mcp_url) as client:
            result = await client.call_tool(tool_name, payload)

        if hasattr(result, "content") and result.content:
            raw = result.content[0] if isinstance(result.content, list) else result.content
            if isinstance(raw, dict) and "text" in raw:
                raw = raw["text"]
            if isinstance(raw, str):
                stripped = raw.strip()
                if stripped.startswith("{") or stripped.startswith("["):
                    try:
                        return json.loads(stripped)
                    except json.JSONDecodeError:
                        return raw
                return raw
            return raw

        if isinstance(result, (dict, list)):
            return result
        return str(result)

    def _format_run_summary(self, run_id: str, status: Any, summary: Any) -> str:
        lines = [f"FuzzForge workflow {run_id} completed."]
        if isinstance(status, dict):
            state = status.get("status") or status.get("state")
            if state:
                lines.append(f"Status: {state}")
            updated = status.get("updated_at") or status.get("completed_at")
            if updated:
                lines.append(f"Completed at: {updated}")
        if isinstance(summary, dict):
            total = summary.get("total_findings")
            if total is not None:
                lines.append(f"Total findings: {total}")
            severity = summary.get("severity_summary")
            if isinstance(severity, dict):
                lines.append("Severity breakdown: " + ", ".join(f"{k}={v}" for k, v in severity.items()))
            recommendations = summary.get("recommendations")
            if recommendations:
                if isinstance(recommendations, list):
                    lines.append("Recommendations:")
                    lines.extend(f"- {item}" for item in recommendations)
                else:
                    lines.append(f"Recommendations: {recommendations}")
        else:
            lines.append(str(summary))
        lines.append("You can request more detail with get_run_findings_mcp(run_id) or get_run_status_mcp(run_id).")
        return "\n".join(lines)

    async def query_project_knowledge_api(
        self,
        query: str,
        search_type: str = "INSIGHTS",
        dataset: str = "",
    ) -> Dict[str, Any]:
        integration = await self._get_knowledge_integration()
        if integration is None:
            return {"error": "Knowledge graph integration unavailable"}

        try:
            result = await integration.search_knowledge_graph(
                query=query,
                search_type=search_type,
                dataset=dataset or None,
            )
            return json.loads(json.dumps(result, default=str))
        except Exception as exc:
            return {"error": f"Knowledge graph query failed: {exc}"}

    async def create_project_file_artifact_api(self, file_path: str) -> Dict[str, Any]:
        try:
            config = ProjectConfigManager()
            if not config.is_initialized():
                return {"error": "Project not initialized. Run 'fuzzforge init' first."}

            project_root = config.config_path.parent.resolve()
            requested_file = (project_root / file_path).resolve()

            try:
                requested_file.relative_to(project_root)
            except ValueError:
                return {"error": f"Access denied: '{file_path}' is outside the project"}

            if not requested_file.exists() or not requested_file.is_file():
                return {"error": f"File not found: {file_path}"}

            size = requested_file.stat().st_size
            max_bytes = int(os.getenv("FUZZFORGE_ARTIFACT_MAX_BYTES", str(25 * 1024 * 1024)))
            if size > max_bytes:
                return {
                    "error": (
                        f"File {file_path} is {size} bytes, exceeding the limit of {max_bytes} bytes"
                    )
                }

            data = requested_file.read_bytes()
            mime_type, _ = mimetypes.guess_type(str(requested_file))
            if not mime_type:
                mime_type = "application/octet-stream"

            artifact_id = f"project_file_{uuid.uuid4().hex[:8]}"
            sha256_digest = hashlib.sha256(data).hexdigest()

            if self.artifact_service:
                try:
                    artifact_part = types.Part(
                        inline_data=types.Blob(
                            mime_type=mime_type,
                            data=data,
                        )
                    )
                    await self.artifact_service.save_artifact(
                        filename=requested_file.name,
                        artifact=artifact_part,
                    )
                    if self.debug:
                        print(
                            f"[DEBUG] Saved project file artifact to service: {requested_file.name}"
                        )
                except Exception as exc:
                    if self.debug:
                        print(f"[DEBUG] Artifact service save failed: {exc}")

            local_meta = self._register_artifact_bytes(
                name=requested_file.name,
                data=data,
                mime_type=mime_type,
                sha256_digest=sha256_digest,
                size=size,
                artifact_id=artifact_id,
            )

            local_meta.update(
                {
                    "path": str(requested_file),
                    "size": size,
                    "name": requested_file.name,
                    "mime_type": mime_type,
                }
            )
            return local_meta
        except Exception as exc:
            return {"error": f"Failed to create artifact: {exc}"}

    async def _create_run_artifact(
        self,
        *,
        run_id: str,
        run_meta: Dict[str, Any],
        status: Any,
        summary: Any,
        findings: Any | None = None,
    ) -> Dict[str, Any] | None:
        workflow_name = run_meta.get("workflow_name") or "workflow"
        safe_workflow = "".join(
            ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in workflow_name
        ) or "workflow"
        artifact_filename = f"{safe_workflow}_{run_id}_summary.json"

        payload: Dict[str, Any] = {
            "run_id": run_id,
            "workflow": workflow_name,
            "submitted_at": run_meta.get("submitted_at"),
            "status": status,
            "summary": summary,
        }

        if isinstance(findings, dict) and not findings.get("error"):
            payload["findings"] = findings

        artifact_bytes = json.dumps(payload, indent=2, default=str).encode("utf-8")

        if self.artifact_service:
            try:
                artifact_part = types.Part(
                    inline_data=types.Blob(
                        mime_type="application/json",
                        data=artifact_bytes,
                    )
                )
                await self.artifact_service.save_artifact(
                    filename=artifact_filename,
                    artifact=artifact_part,
                )
                if self.debug:
                    print(
                        f"[DEBUG] Saved run artifact to artifact service: {artifact_filename}"
                    )
            except Exception as exc:
                if self.debug:
                    print(f"[DEBUG] Artifact service save failed: {exc}")

        sha256_digest = hashlib.sha256(artifact_bytes).hexdigest()
        local_meta = self._register_artifact_bytes(
            name=artifact_filename,
            data=artifact_bytes,
            mime_type="application/json",
            sha256_digest=sha256_digest,
            size=len(artifact_bytes),
            artifact_id=f"fuzzforge_run_{run_id}",
        )

        return local_meta

    async def _append_session_message(self, context_id: str, message: str, run_id: str) -> None:
        meta = self.session_metadata.get(context_id)
        if not meta:
            return
        service = self.runner.session_service
        session_obj = None
        if hasattr(service, "sessions"):
            session_obj = (
                service.sessions
                .get(meta.get("app_name", "fuzzforge"), {})
                .get(meta.get("user_id"), {})
                .get(meta.get("session_id"))
            )
        if not session_obj:
            if self.debug:
                print(f"[DEBUG] Could not locate session for context {context_id}")
            return

        event = Event(
            invocationId=str(uuid.uuid4()),
            id=str(uuid.uuid4()),
            author=getattr(self.agent, 'name', 'FuzzForge'),
            content=types.Content(
                role='assistant',
                parts=[Part.from_text(text=message)]
            ),
            actions=EventActions(),
        )
        event.actions.state_delta[f"fuzzforge.run.{run_id}.status"] = "completed"
        event.actions.state_delta[f"fuzzforge.run.{run_id}.timestamp"] = datetime.now().isoformat()

        await service.append_event(session_obj, event)
        session_obj.last_update_time = time.time()

        cached_session = self.sessions.get(context_id)
        if cached_session and hasattr(cached_session, 'events'):
            cached_session.events.append(event)
        elif cached_session:
            cached_session.events = [event]

    async def _append_external_event(self, session: Any, agent_name: str, message_text: str) -> None:
        if session is None:
            return
        event = Event(
            invocationId=str(uuid.uuid4()),
            id=str(uuid.uuid4()),
            author=agent_name,
            content=types.Content(
                role='assistant',
                parts=[Part.from_text(text=message_text)]
            ),
            actions=EventActions(),
        )
        await self.runner.session_service.append_event(session, event)
        if hasattr(session, 'events'):
            session.events.append(event)
        else:
            session.events = [event]

    async def _send_to_agent(
        self,
        agent_name: str,
        message: Union[str, Dict[str, Any], List[Dict[str, Any]]],
        session: Any,
        context_id: str,
    ) -> str:
        agent_entry = self.agents.get(agent_name)
        if not agent_entry:
            return f"Agent '{agent_name}' is not registered."

        conn = agent_entry.get('connection')
        if conn is None:
            conn = RemoteAgentConnection(agent_entry['url'])
            await conn.get_agent_card()
            agent_entry['connection'] = conn

        conn.context_id = context_id
        response = await conn.send_message(message)
        response_text = response if isinstance(response, str) else str(response)
        await self._append_external_event(session, agent_name, response_text)
        return response_text

    async def delegate_file_to_agent(
        self,
        agent_name: str,
        file_path: str,
        note: str = "",
        session: Any = None,
        context_id: str | None = None,
    ) -> str:
        try:
            project_root = None
            try:
                config = ProjectConfigManager()
                if config.is_initialized():
                    project_root = config.config_path.parent
            except Exception:
                project_root = None

            path_obj = Path(file_path).expanduser()
            if not path_obj.is_absolute() and project_root:
                path_obj = (project_root / path_obj).resolve()
            else:
                path_obj = path_obj.resolve()

            if not path_obj.is_file():
                return f"File not found: {path_obj}"

            data = path_obj.read_bytes()
        except Exception as exc:
            return f"Failed to read file '{file_path}': {exc}"

        message_text = note or f"Please analyse the artifact {path_obj.name}."

        if session is None:
            if not self.sessions:
                return "No active session available for delegation."
            default_context = next(iter(self.sessions.keys()))
            session = self.sessions[default_context]
            context_id = default_context

        if context_id is None:
            session_id = getattr(session, 'id', None)
            context_id = self.session_lookup.get(session_id, session_id or 'default')

        app_name = getattr(session, 'app_name', 'fuzzforge')
        user_id = getattr(session, 'user_id', 'user')
        session_id = getattr(session, 'id', context_id)

        mime_type, _ = mimetypes.guess_type(str(path_obj))
        if not mime_type:
            mime_type = 'application/octet-stream'

        sha256_digest = hashlib.sha256(data).hexdigest()
        size = len(data)

        artifact_version = None
        if self.artifact_service:
            try:
                artifact_part = types.Part(
                    inline_data=types.Blob(data=data, mime_type=mime_type)
                )
                artifact_version = await self.artifact_service.save_artifact(
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                    filename=path_obj.name,
                    artifact=artifact_part,
                )
            except Exception as exc:
                artifact_version = None
                if self.debug:
                    print(f"[DEBUG] Failed to persist artifact in service: {exc}")

        artifact_meta = self._register_artifact_bytes(
            name=path_obj.name,
            data=data,
            mime_type=mime_type,
            sha256_digest=sha256_digest,
            size=size,
        )

        artifact_info = {
            "file_uri": artifact_meta["file_uri"],  # HTTP URL for download
            "artifact_url": artifact_meta["file_uri"],  # Alias for reverse agent compatibility
            "cache_path": artifact_meta["path"],
            "filename": path_obj.name,
            "mime_type": mime_type,
            "sha256": sha256_digest,
            "size": size,
            "session": {
                "app_name": app_name,
                "user_id": user_id,
                "session_id": session_id,
            },
        }
        if artifact_version is not None:
            artifact_info["artifact_version"] = artifact_version

        parts: List[Dict[str, Any]] = [
            {"type": "text", "text": message_text},
            {
                "type": "file",
                "file": {
                    "uri": artifact_meta["file_uri"],
                    "name": path_obj.name,
                    "mime_type": mime_type,
                },
            },
            {
                "type": "text",
                "text": f"artifact_metadata: {json.dumps(artifact_info)}",
            },
        ]

        return await self._send_to_agent(agent_name, {"parts": parts}, session, context_id)

    async def _publish_task_pending(self, run_id: str, context_id: str, workflow_name: str) -> None:
        task_store = self.task_store
        queue_manager = self.queue_manager
        if not task_store or not queue_manager:
            return

        context_identifier = context_id or "default"

        status_obj = TaskStatus(
            state=TaskState.working,
            timestamp=datetime.now().isoformat(),
        )

        task = Task(
            id=run_id,
            context_id=context_identifier,
            status=status_obj,
            metadata={"workflow": workflow_name},
        )
        await task_store.save(task)

        status_event = TaskStatusUpdateEvent(
            taskId=run_id,
            contextId=context_identifier,
            status=status_obj,
            final=False,
            metadata={"workflow": workflow_name},
        )

        queue = await queue_manager.create_or_tap(run_id)
        await queue.enqueue_event(status_event)  # type: ignore[arg-type]

    async def _publish_task_update(
        self,
        run_id: str,
        context_id: str | None,
        status_payload: Any,
        summary_payload: Any,
        message_text: str,
        artifact_info: Dict[str, Any] | None = None,
    ) -> None:
        if not FuzzForgeExecutor.task_store or not FuzzForgeExecutor.queue_manager:
            return

        task_store = self.task_store
        queue_manager = self.queue_manager

        context_identifier = context_id or "default"
        existing_task = await task_store.get(run_id)

        message_obj = Message(
            messageId=str(uuid.uuid4()),
            role="agent",
            parts=[A2APart.model_validate({"type": "text", "text": message_text})],
            contextId=context_identifier,
            taskId=run_id,
        )

        status_obj = TaskStatus(
            state=TaskState.completed,
            timestamp=datetime.now().isoformat(),
            message=message_obj,
        )

        metadata = {
            "status": status_payload,
            "summary": summary_payload,
        }
        if artifact_info:
            metadata["artifact"] = artifact_info

        status_event = TaskStatusUpdateEvent(
            taskId=run_id,
            contextId=context_identifier,
            status=status_obj,
            final=True,
            metadata=metadata,
        )

        if existing_task:
            existing_task.status = status_obj
            if existing_task.metadata is None:
                existing_task.metadata = {}
            existing_task.metadata.update(metadata)
            if existing_task.history:
                existing_task.history.append(message_obj)
            else:
                existing_task.history = [message_obj]
            await task_store.save(existing_task)
        else:
            new_task = Task(
                id=run_id,
                context_id=context_identifier,
                status=status_obj,
                metadata=metadata,
                history=[message_obj],
            )
            await task_store.save(new_task)

        queue = await queue_manager.create_or_tap(run_id)
        await queue.enqueue_event(status_event)  # type: ignore[arg-type]
