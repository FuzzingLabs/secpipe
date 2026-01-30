"""
FuzzForge Agent Card and Skills Definition
Defines what FuzzForge can do and how others can discover it
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


from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class AgentSkill:
    """Represents a specific capability of the agent"""
    id: str
    name: str
    description: str
    tags: List[str]
    examples: List[str]
    input_modes: List[str] = None
    output_modes: List[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
            "examples": self.examples,
            "inputModes": self.input_modes or ["text/plain"],
            "outputModes": self.output_modes or ["text/plain"]
        }


@dataclass
class AgentCapabilities:
    """Defines agent capabilities for A2A protocol"""
    streaming: bool = False
    push_notifications: bool = False
    multi_turn: bool = True
    context_retention: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "streaming": self.streaming,
            "pushNotifications": self.push_notifications,
            "multiTurn": self.multi_turn,
            "contextRetention": self.context_retention
        }


@dataclass
class AgentCard:
    """The agent's business card - tells others what this agent can do"""
    name: str
    description: str
    version: str
    url: str
    skills: List[AgentSkill]
    capabilities: AgentCapabilities
    default_input_modes: List[str] = None
    default_output_modes: List[str] = None
    preferred_transport: str = "JSONRPC"
    protocol_version: str = "0.3.0"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to A2A-compliant agent card JSON"""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "url": self.url,
            "protocolVersion": self.protocol_version,
            "preferredTransport": self.preferred_transport,
            "defaultInputModes": self.default_input_modes or ["text/plain"],
            "defaultOutputModes": self.default_output_modes or ["text/plain"],
            "capabilities": self.capabilities.to_dict(),
            "skills": [skill.to_dict() for skill in self.skills]
        }


# Define FuzzForge's skills
orchestration_skill = AgentSkill(
    id="orchestration",
    name="Agent Orchestration",
    description="Route requests to appropriate registered agents based on their capabilities",
    tags=["orchestration", "routing", "coordination"],
    examples=[
        "Route this to the calculator",
        "Send this to the appropriate agent",
        "Which agent should handle this?"
    ]
)

memory_skill = AgentSkill(
    id="memory",
    name="Memory Management",
    description="Store and retrieve information using Cognee knowledge graph",
    tags=["memory", "knowledge", "storage", "cognee"],
    examples=[
        "Remember that my favorite color is blue",
        "What do you remember about me?",
        "Search your memory for project details"
    ]
)

conversation_skill = AgentSkill(
    id="conversation",
    name="General Conversation",
    description="Engage in general conversation and answer questions using LLM",
    tags=["chat", "conversation", "qa", "llm"],
    examples=[
        "What is the meaning of life?",
        "Explain quantum computing",
        "Help me understand this concept"
    ]
)

workflow_automation_skill = AgentSkill(
    id="workflow_automation",
    name="Workflow Automation",
    description="Operate project workflows via MCP, monitor runs, and share results",
    tags=["workflow", "automation", "mcp", "orchestration"],
    examples=[
        "Submit the security assessment workflow",
        "Kick off the infrastructure scan and monitor it",
        "Summarise findings for run abc123"
    ]
)

agent_management_skill = AgentSkill(
    id="agent_management",
    name="Agent Registry Management",
    description="Register, list, and manage connections to other A2A agents",
    tags=["registry", "management", "discovery"],
    examples=[
        "Register agent at http://localhost:10201",
        "List all registered agents",
        "Show agent capabilities"
    ]
)

# Define FuzzForge's capabilities
fuzzforge_capabilities = AgentCapabilities(
    streaming=False,
    push_notifications=True,
    multi_turn=True,  # We support multi-turn conversations
    context_retention=True  # We maintain context across turns
)

# Create the public agent card
def get_fuzzforge_agent_card(url: str = "http://localhost:10100") -> AgentCard:
    """Get FuzzForge's agent card with current configuration"""
    return AgentCard(
        name="ProjectOrchestrator",
        description=(
            "An A2A-capable project agent that can launch and monitor FuzzForge workflows, "
            "consult the project knowledge graph, and coordinate with speciality agents."
        ),
        version="project-agent",
        url=url,
        skills=[
            orchestration_skill,
            memory_skill,
            conversation_skill,
            agent_management_skill
        ],
        capabilities=fuzzforge_capabilities,
        default_input_modes=["text/plain", "application/json"],
        default_output_modes=["text/plain", "application/json"],
        preferred_transport="JSONRPC",
        protocol_version="0.3.0"
    )
