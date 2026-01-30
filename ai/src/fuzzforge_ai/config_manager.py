"""
Configuration manager for FuzzForge
Handles loading and saving registered agents
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
import yaml
from typing import Dict, Any, List

class ConfigManager:
    """Manages FuzzForge agent registry configuration"""
    
    def __init__(self, config_path: str = None):
        """Initialize config manager"""
        if config_path:
            self.config_path = config_path
        else:
            # Check for local .fuzzforge/agents.yaml first, then fall back to global
            local_config = os.path.join(os.getcwd(), '.fuzzforge', 'agents.yaml')
            global_config = os.path.join(os.path.dirname(__file__), 'config.yaml')
            
            if os.path.exists(local_config):
                self.config_path = local_config
                if os.getenv("FUZZFORGE_DEBUG", "0") == "1":
                    print(f"[CONFIG] Using local config: {local_config}")
            else:
                self.config_path = global_config
                if os.getenv("FUZZFORGE_DEBUG", "0") == "1":
                    print(f"[CONFIG] Using global config: {global_config}")
        
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if not os.path.exists(self.config_path):
            # Create default config if it doesn't exist
            return {'registered_agents': []}
        
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f) or {}
                # Ensure registered_agents is a list
                if 'registered_agents' not in config or config['registered_agents'] is None:
                    config['registered_agents'] = []
                return config
        except Exception as e:
            print(f"[WARNING] Failed to load config: {e}")
            return {'registered_agents': []}
    
    def save_config(self):
        """Save current configuration to file"""
        try:
            # Create a clean config with comments
            config_content = """# FuzzForge Registered Agents
# These agents will be automatically registered on startup

"""
            # Add the agents list
            if self.config.get('registered_agents'):
                config_content += yaml.dump({'registered_agents': self.config['registered_agents']}, 
                                           default_flow_style=False, sort_keys=False)
            else:
                config_content += "registered_agents: []\n"
            
            config_content += """
# Example entries:
# - name: Calculator
#   url: http://localhost:10201
#   description: Mathematical calculations agent
"""
            
            with open(self.config_path, 'w') as f:
                f.write(config_content)
                
            return True
        except Exception as e:
            print(f"[ERROR] Failed to save config: {e}")
            return False
    
    def get_registered_agents(self) -> List[Dict[str, Any]]:
        """Get list of registered agents from config"""
        return self.config.get('registered_agents', [])
    
    def add_registered_agent(self, name: str, url: str, description: str = "") -> bool:
        """Add a new registered agent to config"""
        if 'registered_agents' not in self.config:
            self.config['registered_agents'] = []
        
        # Check if agent already exists
        for agent in self.config['registered_agents']:
            if agent.get('url') == url:
                # Update existing agent
                agent['name'] = name
                agent['description'] = description
                return self.save_config()
        
        # Add new agent
        self.config['registered_agents'].append({
            'name': name,
            'url': url,
            'description': description
        })
        
        return self.save_config()
    
    def remove_registered_agent(self, name: str = None, url: str = None) -> bool:
        """Remove a registered agent from config"""
        if 'registered_agents' not in self.config:
            return False
        
        original_count = len(self.config['registered_agents'])
        
        # Filter out the agent
        self.config['registered_agents'] = [
            agent for agent in self.config['registered_agents']
            if not ((name and agent.get('name') == name) or 
                   (url and agent.get('url') == url))
        ]
        
        if len(self.config['registered_agents']) < original_count:
            return self.save_config()
        
        return False
