"""
Remote Agent Connection Handler
Handles A2A protocol communication with remote agents
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


import httpx
import uuid
from typing import Dict, Any, Optional, List


class RemoteAgentConnection:
    """Handles A2A protocol communication with remote agents"""
    
    def __init__(self, url: str):
        """Initialize connection to a remote agent"""
        self.url = url.rstrip('/')
        self.agent_card = None
        self.client = httpx.AsyncClient(timeout=120.0, follow_redirects=True)
        self.context_id = None
        
    async def get_agent_card(self) -> Optional[Dict[str, Any]]:
        """Get the agent card from the remote agent"""
        # If URL already points to a .json file, fetch it directly
        if self.url.endswith('.json'):
            try:
                response = await self.client.get(self.url)
                response.raise_for_status()
                self.agent_card = response.json()

                # Use canonical URL from agent card if provided
                if isinstance(self.agent_card, dict) and "url" in self.agent_card:
                    self.url = self.agent_card["url"].rstrip('/')

                return self.agent_card
            except Exception as e:
                print(f"Failed to get agent card from {self.url}: {e}")
                return None

        # Try both agent-card.json (A2A 0.3.0+) and agent.json (legacy)
        well_known_paths = [
            "/.well-known/agent-card.json",
            "/.well-known/agent.json",
        ]

        for path in well_known_paths:
            try:
                response = await self.client.get(f"{self.url}{path}")
                response.raise_for_status()
                self.agent_card = response.json()

                # Use canonical URL from agent card if provided
                if isinstance(self.agent_card, dict) and "url" in self.agent_card:
                    self.url = self.agent_card["url"].rstrip('/')

                return self.agent_card
            except Exception:
                continue

        print(f"Failed to get agent card from {self.url}")
        print("Tip: If agent is at /a2a/something, use full URL: /register http://host:port/a2a/something")
        return None
                
    async def send_message(self, message: str | Dict[str, Any] | List[Dict[str, Any]]) -> str:
        """Send a message to the remote agent using A2A protocol"""
        try:
            parts: List[Dict[str, Any]]
            metadata: Dict[str, Any] | None = None
            if isinstance(message, dict):
                metadata = message.get("metadata") if isinstance(message.get("metadata"), dict) else None
                raw_parts = message.get("parts", [])
                if not raw_parts:
                    text_value = message.get("text") or message.get("message")
                    if isinstance(text_value, str):
                        raw_parts = [{"type": "text", "text": text_value}]
                parts = [raw_part for raw_part in raw_parts if isinstance(raw_part, dict)]
            elif isinstance(message, list):
                parts = [part for part in message if isinstance(part, dict)]
                metadata = None
            else:
                parts = [{"type": "text", "text": message}]
                metadata = None

            if not parts:
                parts = [{"type": "text", "text": ""}]

            # Build JSON-RPC request per A2A spec
            payload = {
                "jsonrpc": "2.0",
                "method": "message/send",
                "params": {
                    "message": {
                        "messageId": str(uuid.uuid4()),
                        "role": "user",
                        "parts": parts,
                    }
                },
                "id": 1
            }

            if metadata:
                payload["params"]["message"]["metadata"] = metadata
            
            # Include context if we have one
            if self.context_id:
                payload["params"]["contextId"] = self.context_id
            
            # Send to root endpoint per A2A protocol
            response = await self.client.post(self.url, json=payload)
            response.raise_for_status()
            result = response.json()
            
            # Extract response based on A2A JSON-RPC format
            if isinstance(result, dict):
                # Update context for continuity
                if "result" in result and isinstance(result["result"], dict):
                    if "contextId" in result["result"]:
                        self.context_id = result["result"]["contextId"]
                    
                    # Extract text from artifacts
                    if "artifacts" in result["result"]:
                        texts = []
                        for artifact in result["result"]["artifacts"]:
                            if isinstance(artifact, dict) and "parts" in artifact:
                                for part in artifact["parts"]:
                                    if isinstance(part, dict) and "text" in part:
                                        texts.append(part["text"])
                        if texts:
                            return " ".join(texts)
                    
                    # Extract from message format
                    if "message" in result["result"]:
                        msg = result["result"]["message"]
                        if isinstance(msg, dict) and "parts" in msg:
                            texts = []
                            for part in msg["parts"]:
                                if isinstance(part, dict) and "text" in part:
                                    texts.append(part["text"])
                            return " ".join(texts) if texts else str(msg)
                        return str(msg)
                    
                    return str(result["result"])
                
                # Handle error response
                elif "error" in result:
                    error = result["error"]
                    if isinstance(error, dict):
                        return f"Error: {error.get('message', str(error))}"
                    return f"Error: {error}"
                
                # Fallback
                return result.get("response", result.get("message", str(result)))
            
            return str(result)
            
        except Exception as e:
            return f"Error communicating with agent: {e}"
            
    async def close(self):
        """Close the connection properly"""
        await self.client.aclose()
