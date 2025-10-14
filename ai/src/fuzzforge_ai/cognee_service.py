"""
Cognee Service for FuzzForge
Provides integrated Cognee functionality for codebase analysis and knowledge graphs
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
import logging
from pathlib import Path
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class CogneeService:
    """
    Service for managing Cognee integration with FuzzForge
    Handles multi-tenant isolation and project-specific knowledge graphs
    """
    
    def __init__(self, config):
        """Initialize with FuzzForge config"""
        self.config = config
        self.cognee_config = config.get_cognee_config()
        self.project_context = config.get_project_context()
        self._cognee = None
        self._user = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize Cognee with project-specific configuration"""
        try:
            # Ensure environment variables for Cognee are set before import
            self.config.setup_cognee_environment()
            logger.debug(
                "Cognee environment configured",
                extra={
                    "data": self.cognee_config.get("data_directory"),
                    "system": self.cognee_config.get("system_directory"),
                },
            )

            import cognee
            self._cognee = cognee
            
            # Configure LLM with API key BEFORE any other cognee operations
            provider = os.getenv("LLM_PROVIDER", "openai")
            model = os.getenv("LLM_MODEL") or os.getenv("LITELLM_MODEL", "gpt-4o-mini")
            api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
            endpoint = os.getenv("LLM_ENDPOINT")
            api_version = os.getenv("LLM_API_VERSION")
            max_tokens = os.getenv("LLM_MAX_TOKENS")

            if provider.lower() in {"openai", "azure_openai", "custom"} and not api_key:
                raise ValueError(
                    "OpenAI-compatible API key is required for Cognee LLM operations. "
                    "Set OPENAI_API_KEY, LLM_API_KEY, or COGNEE_LLM_API_KEY in your .env"
                )

            # Expose environment variables for downstream libraries
            os.environ["LLM_PROVIDER"] = provider
            os.environ["LITELLM_MODEL"] = model
            os.environ["LLM_MODEL"] = model
            if api_key:
                os.environ["LLM_API_KEY"] = api_key
                # Maintain compatibility with components still expecting OPENAI_API_KEY
                if provider.lower() in {"openai", "azure_openai", "custom"}:
                    os.environ.setdefault("OPENAI_API_KEY", api_key)
            if endpoint:
                os.environ["LLM_ENDPOINT"] = endpoint
            if api_version:
                os.environ["LLM_API_VERSION"] = api_version
            if max_tokens:
                os.environ["LLM_MAX_TOKENS"] = str(max_tokens)

            # Configure Cognee's runtime using its configuration helpers when available
            if hasattr(cognee.config, "set_llm_provider"):
                cognee.config.set_llm_provider(provider)
            if hasattr(cognee.config, "set_llm_model"):
                cognee.config.set_llm_model(model)
            if api_key and hasattr(cognee.config, "set_llm_api_key"):
                cognee.config.set_llm_api_key(api_key)
            if endpoint and hasattr(cognee.config, "set_llm_endpoint"):
                cognee.config.set_llm_endpoint(endpoint)
            if api_version and hasattr(cognee.config, "set_llm_api_version"):
                cognee.config.set_llm_api_version(api_version)
            if max_tokens and hasattr(cognee.config, "set_llm_max_tokens"):
                cognee.config.set_llm_max_tokens(int(max_tokens))
            
            # Configure graph database
            cognee.config.set_graph_db_config({
                "graph_database_provider": self.cognee_config.get("graph_database_provider", "kuzu"),
            })
            
            # Set data directories
            data_dir = self.cognee_config.get("data_directory")
            system_dir = self.cognee_config.get("system_directory")
            
            if data_dir:
                logger.debug("Setting cognee data root", extra={"path": data_dir})
                cognee.config.data_root_directory(data_dir)
            if system_dir:
                logger.debug("Setting cognee system root", extra={"path": system_dir})
                cognee.config.system_root_directory(system_dir)
            
            # Setup multi-tenant user context
            await self._setup_user_context()
            
            self._initialized = True
            logger.info(f"Cognee initialized for project {self.project_context['project_name']} "
                       f"with Kuzu at {system_dir}")
            
        except ImportError:
            logger.error("Cognee not installed. Install with: pip install cognee")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Cognee: {e}")
            raise
    
    async def create_dataset(self):
        """Create dataset for this project if it doesn't exist"""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Dataset creation is handled automatically by Cognee when adding files
            # We just ensure we have the right context set up
            dataset_name = f"{self.project_context['project_name']}_codebase"
            logger.info(f"Dataset {dataset_name} ready for project {self.project_context['project_name']}")
            return dataset_name
        except Exception as e:
            logger.error(f"Failed to create dataset: {e}")
            raise
    
    async def _setup_user_context(self):
        """Setup user context for multi-tenant isolation"""
        try:
            from cognee.modules.users.methods import create_user, get_user
            
            # Always try fallback email first to avoid validation issues
            fallback_email = f"project_{self.project_context['project_id']}@fuzzforge.example"
            user_tenant = self.project_context['tenant_id']
            
            # Try to get existing fallback user first
            try:
                self._user = await get_user(fallback_email)
                logger.info(f"Using existing user: {fallback_email}")
                return
            except Exception:
                # User doesn't exist, try to create fallback
                pass
            
            # Create fallback user
            try:
                self._user = await create_user(fallback_email, user_tenant)
                logger.info(f"Created fallback user: {fallback_email} for tenant: {user_tenant}")
                return
            except Exception as fallback_error:
                logger.warning(f"Fallback user creation failed: {fallback_error}")
                self._user = None
                return
            
        except Exception as e:
            logger.warning(f"Could not setup multi-tenant user context: {e}")
            logger.info("Proceeding with default context")
            self._user = None
    
    def get_project_dataset_name(self, dataset_suffix: str = "codebase") -> str:
        """Get project-specific dataset name"""
        return f"{self.project_context['project_name']}_{dataset_suffix}"
    
    async def ingest_text(self, content: str, dataset: str = "fuzzforge") -> bool:
        """Ingest text content into knowledge graph"""
        if not self._initialized:
            await self.initialize()
        
        try:
            await self._cognee.add([content], dataset)
            await self._cognee.cognify([dataset])
            return True
        except Exception as e:
            logger.error(f"Failed to ingest text: {e}")
            return False
    
    async def ingest_files(self, file_paths: List[Path], dataset: str = "fuzzforge") -> Dict[str, Any]:
        """Ingest multiple files into knowledge graph"""
        if not self._initialized:
            await self.initialize()
        
        results = {
            "success": 0,
            "failed": 0,
            "errors": []
        }
        
        try:
            ingest_paths: List[str] = []
            for file_path in file_paths:
                try:
                    with open(file_path, 'r', encoding='utf-8'):
                        ingest_paths.append(str(file_path))
                    results["success"] += 1
                except (UnicodeDecodeError, PermissionError) as exc:
                    results["failed"] += 1
                    results["errors"].append(f"{file_path}: {exc}")
                    logger.warning("Skipping %s: %s", file_path, exc)

            if ingest_paths:
                await self._cognee.add(ingest_paths, dataset_name=dataset)
                await self._cognee.cognify([dataset])
            
        except Exception as e:
            logger.error(f"Failed to ingest files: {e}")
            results["errors"].append(f"Cognify error: {str(e)}")
        
        return results
    
    async def search_insights(self, query: str, dataset: str = None) -> List[str]:
        """Search for insights in the knowledge graph"""
        if not self._initialized:
            await self.initialize()
        
        try:
            from cognee.modules.search.types import SearchType
            
            kwargs = {
                "query_type": SearchType.INSIGHTS,
                "query_text": query
            }
            
            if dataset:
                kwargs["datasets"] = [dataset]
            
            results = await self._cognee.search(**kwargs)
            return results if isinstance(results, list) else []
            
        except Exception as e:
            logger.error(f"Failed to search insights: {e}")
            return []
    
    async def search_chunks(self, query: str, dataset: str = None) -> List[str]:
        """Search for relevant text chunks"""
        if not self._initialized:
            await self.initialize()
        
        try:
            from cognee.modules.search.types import SearchType
            
            kwargs = {
                "query_type": SearchType.CHUNKS,
                "query_text": query
            }
            
            if dataset:
                kwargs["datasets"] = [dataset]
            
            results = await self._cognee.search(**kwargs)
            return results if isinstance(results, list) else []
            
        except Exception as e:
            logger.error(f"Failed to search chunks: {e}")
            return []
    
    async def search_graph_completion(self, query: str) -> List[str]:
        """Search for graph completion (relationships)"""
        if not self._initialized:
            await self.initialize()
        
        try:
            from cognee.modules.search.types import SearchType
            
            results = await self._cognee.search(
                query_type=SearchType.GRAPH_COMPLETION,
                query_text=query
            )
            return results if isinstance(results, list) else []
            
        except Exception as e:
            logger.error(f"Failed to search graph completion: {e}")
            return []
    
    async def get_status(self) -> Dict[str, Any]:
        """Get service status and statistics"""
        status = {
            "initialized": self._initialized,
            "enabled": self.cognee_config.get("enabled", True),
            "provider": self.cognee_config.get("graph_database_provider", "kuzu"),
            "data_directory": self.cognee_config.get("data_directory"),
            "system_directory": self.cognee_config.get("system_directory"),
        }
        
        if self._initialized:
            try:
                # Check if directories exist and get sizes
                data_dir = Path(status["data_directory"])
                system_dir = Path(status["system_directory"])
                
                status.update({
                    "data_dir_exists": data_dir.exists(),
                    "system_dir_exists": system_dir.exists(),
                    "kuzu_db_exists": (system_dir / "kuzu_db").exists(),
                    "lancedb_exists": (system_dir / "lancedb").exists(),
                })
                
            except Exception as e:
                status["status_error"] = str(e)
        
        return status
    
    async def clear_data(self, confirm: bool = False):
        """Clear all ingested data (dangerous!)"""
        if not confirm:
            raise ValueError("Must confirm data clearing with confirm=True")
        
        if not self._initialized:
            await self.initialize()
        
        try:
            await self._cognee.prune.prune_data()
            await self._cognee.prune.prune_system(metadata=True)
            logger.info("Cognee data cleared")
        except Exception as e:
            logger.error(f"Failed to clear data: {e}")
            raise


class FuzzForgeCogneeIntegration:
    """
    Main integration class for FuzzForge + Cognee
    Provides high-level operations for security analysis
    """
    
    def __init__(self, config):
        self.service = CogneeService(config)
    
    async def analyze_codebase(self, path: Path, recursive: bool = True) -> Dict[str, Any]:
        """
        Analyze a codebase and extract security-relevant insights
        """
        # Collect code files
        from fuzzforge_ai.ingest_utils import collect_ingest_files

        files = collect_ingest_files(path, recursive, None, [])
        
        if not files:
            return {"error": "No files found to analyze"}
        
        # Ingest files
        results = await self.service.ingest_files(files, "security_analysis")
        
        if results["success"] == 0:
            return {"error": "Failed to ingest any files", "details": results}
        
        # Extract security insights
        security_queries = [
            "vulnerabilities security risks",
            "authentication authorization",
            "input validation sanitization", 
            "encryption cryptography",
            "error handling exceptions",
            "logging sensitive data"
        ]
        
        insights = {}
        for query in security_queries:
            insight_results = await self.service.search_insights(query, "security_analysis")
            if insight_results:
                insights[query.replace(" ", "_")] = insight_results
        
        return {
            "files_processed": results["success"],
            "files_failed": results["failed"],
            "errors": results["errors"],
            "security_insights": insights
        }
    
    async def query_codebase(self, query: str, search_type: str = "insights") -> List[str]:
        """Query the ingested codebase"""
        if search_type == "insights":
            return await self.service.search_insights(query)
        elif search_type == "chunks":
            return await self.service.search_chunks(query)
        elif search_type == "graph":
            return await self.service.search_graph_completion(query)
        else:
            raise ValueError(f"Unknown search type: {search_type}")
    
    async def get_project_summary(self) -> Dict[str, Any]:
        """Get a summary of the analyzed project"""
        # Search for general project insights
        summary_queries = [
            "project structure components",
            "main functionality features",
            "programming languages frameworks",
            "dependencies libraries"
        ]
        
        summary = {}
        for query in summary_queries:
            results = await self.service.search_insights(query)
            if results:
                summary[query.replace(" ", "_")] = results[:3]  # Top 3 results
        
        return summary
