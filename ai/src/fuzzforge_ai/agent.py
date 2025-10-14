"""
FuzzForge Agent Definition
The core agent that combines all components
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
from pathlib import Path
from typing import Dict, Any, List
from google.adk import Agent
from google.adk.models.lite_llm import LiteLlm
from .agent_card import get_fuzzforge_agent_card
from .agent_executor import FuzzForgeExecutor
from .memory_service import FuzzForgeMemoryService, HybridMemoryManager

# Load environment variables from the AI module's .env file
try:
    from dotenv import load_dotenv
    _ai_dir = Path(__file__).parent
    _env_file = _ai_dir / ".env"
    if _env_file.exists():
        load_dotenv(_env_file, override=False)  # Don't override existing env vars
except ImportError:
    # dotenv not available, skip loading
    pass


class FuzzForgeAgent:
    """The main FuzzForge agent that combines card, executor, and ADK agent"""
    
    def __init__(
        self,
        model: str = None,
        cognee_url: str = None,
        port: int = 10100,
    ):
        """Initialize FuzzForge agent with configuration"""
        self.model = model or os.getenv('LITELLM_MODEL', 'gpt-4o-mini')
        self.cognee_url = cognee_url or os.getenv('COGNEE_MCP_URL')
        self.port = port

        # Initialize ADK Memory Service for conversational memory
        memory_type = os.getenv('MEMORY_SERVICE', 'inmemory')
        self.memory_service = FuzzForgeMemoryService(memory_type=memory_type)
        
        # Create the executor (the brain) with memory and session services
        self.executor = FuzzForgeExecutor(
            model=self.model,
            cognee_url=self.cognee_url,
            debug=os.getenv('FUZZFORGE_DEBUG', '0') == '1',
            memory_service=self.memory_service,
            session_persistence=os.getenv('SESSION_PERSISTENCE', 'inmemory'),
            fuzzforge_mcp_url=None,  # Disabled
        )
        
        # Create Hybrid Memory Manager (ADK + Cognee direct integration)
        # MCP tools removed - using direct Cognee integration only
        self.memory_manager = HybridMemoryManager(
            memory_service=self.memory_service,
            cognee_tools=None  # No MCP tools, direct integration used instead
        )
        
        # Get the agent card (the identity)
        self.agent_card = get_fuzzforge_agent_card(f"http://localhost:{self.port}")
        
        # Create the ADK agent (for A2A server mode)
        self.adk_agent = self._create_adk_agent()
        
    def _create_adk_agent(self) -> Agent:
        """Create the ADK agent for A2A server mode"""
        # Build instruction
        instruction = f"""You are {self.agent_card.name}, {self.agent_card.description}

Your capabilities include:
"""
        for skill in self.agent_card.skills:
            instruction += f"\n- {skill.name}: {skill.description}"
        
        instruction += """

When responding to requests:
1. Use your registered agents when appropriate
2. Use Cognee memory tools when available
3. Provide helpful, concise responses
4. Maintain context across conversations
"""
        
        # Create ADK agent
        return Agent(
            model=LiteLlm(model=self.model),
            name=self.agent_card.name,
            description=self.agent_card.description,
            instruction=instruction,
            tools=self.executor.agent.tools if hasattr(self.executor.agent, 'tools') else []
        )
    
    async def process_message(self, message: str, context_id: str = None) -> str:
        """Process a message using the executor"""
        result = await self.executor.execute(message, context_id or "default")
        return result.get("response", "No response generated")
    
    async def register_agent(self, url: str) -> Dict[str, Any]:
        """Register a new agent"""
        return await self.executor.register_agent(url)
    
    def list_agents(self) -> List[Dict[str, Any]]:
        """List registered agents"""
        return self.executor.list_agents()
    
    async def cleanup(self):
        """Clean up resources"""
        await self.executor.cleanup()


# Create a singleton instance for import
_instance = None

def get_fuzzforge_agent() -> FuzzForgeAgent:
    """Get the singleton FuzzForge agent instance"""
    global _instance
    if _instance is None:
        _instance = FuzzForgeAgent()
    return _instance
