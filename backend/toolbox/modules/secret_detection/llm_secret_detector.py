"""
LLM Secret Detection Module

This module uses an LLM to detect secrets and sensitive information via semantic understanding.
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


import logging
from pathlib import Path
from typing import Dict, Any, List

from ..base import BaseModule, ModuleMetadata, ModuleFinding, ModuleResult
from . import register_module

logger = logging.getLogger(__name__)


@register_module
class LLMSecretDetectorModule(BaseModule):
    """
    LLM-based secret detection module using AI semantic analysis.

    Uses an LLM agent to identify secrets through natural language understanding,
    potentially catching secrets that pattern-based tools miss.
    """

    def get_metadata(self) -> ModuleMetadata:
        """Get module metadata"""
        return ModuleMetadata(
            name="llm_secret_detector",
            version="1.0.0",
            description="AI-powered secret detection using LLM semantic analysis",
            author="FuzzForge Team",
            category="secret_detection",
            tags=["secrets", "llm", "ai", "semantic"],
            input_schema={
                "type": "object",
                "properties": {
                    "agent_url": {
                        "type": "string",
                        "default": "http://fuzzforge-task-agent:8000/a2a/litellm_agent",
                        "description": "A2A agent endpoint URL"
                    },
                    "llm_model": {
                        "type": "string",
                        "default": "gpt-4o-mini",
                        "description": "LLM model to use"
                    },
                    "llm_provider": {
                        "type": "string",
                        "default": "openai",
                        "description": "LLM provider (openai, anthropic, etc.)"
                    },
                    "file_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": ["*.py", "*.js", "*.ts", "*.java", "*.go", "*.env", "*.yaml", "*.yml", "*.json", "*.xml", "*.ini", "*.sql", "*.properties", "*.sh", "*.bat", "*.config", "*.conf", "*.toml", "*id_rsa*"],
                        "description": "File patterns to analyze"
                    },
                    "max_files": {
                        "type": "integer",
                        "default": 20,
                        "description": "Maximum number of files to analyze"
                    },
                    "max_file_size": {
                        "type": "integer",
                        "default": 30000,
                        "description": "Maximum file size in bytes (30KB default)"
                    },
                    "timeout": {
                        "type": "integer",
                        "default": 45,
                        "description": "Timeout per file in seconds"
                    }
                },
                "required": []
            },
            output_schema={
                "type": "object",
                "properties": {
                    "findings": {
                        "type": "array",
                        "description": "Secrets identified by LLM"
                    }
                }
            }
        )

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate module configuration"""
        # Lazy import to avoid Temporal sandbox restrictions
        try:
            from fuzzforge_ai.a2a_wrapper import send_agent_task  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "A2A wrapper not available. Ensure fuzzforge_ai module is accessible."
            )

        agent_url = config.get("agent_url")
        # agent_url is optional - will have default from metadata.yaml
        if agent_url is not None and not isinstance(agent_url, str):
            raise ValueError("agent_url must be a valid URL string")

        max_files = config.get("max_files", 20)
        if not isinstance(max_files, int) or max_files <= 0:
            raise ValueError("max_files must be a positive integer")

        return True

    async def execute(self, config: Dict[str, Any], workspace: Path) -> ModuleResult:
        """
        Execute LLM-based secret detection.

        Args:
            config: Module configuration
            workspace: Path to the workspace containing code to analyze

        Returns:
            ModuleResult with secrets detected by LLM
        """
        self.start_timer()

        logger.info(f"Starting LLM secret detection in workspace: {workspace}")

        # Extract configuration (defaults come from metadata.yaml via API)
        agent_url = config["agent_url"]
        llm_model = config["llm_model"]
        llm_provider = config["llm_provider"]
        file_patterns = config["file_patterns"]
        max_files = config["max_files"]
        max_file_size = config["max_file_size"]
        timeout = config["timeout"]

        # Find files to analyze
        # Skip files that are unlikely to contain secrets
        skip_patterns = ['*.sarif', '*.md', '*.html', '*.css', '*.db', '*.sqlite']

        files_to_analyze = []
        for pattern in file_patterns:
            for file_path in workspace.rglob(pattern):
                if file_path.is_file():
                    try:
                        # Skip unlikely files
                        if any(file_path.match(skip) for skip in skip_patterns):
                            logger.debug(f"Skipping {file_path.name} (unlikely to have secrets)")
                            continue

                        # Check file size
                        if file_path.stat().st_size > max_file_size:
                            logger.debug(f"Skipping {file_path} (too large)")
                            continue

                        files_to_analyze.append(file_path)

                        if len(files_to_analyze) >= max_files:
                            break
                    except Exception as e:
                        logger.warning(f"Error checking file {file_path}: {e}")
                        continue

            if len(files_to_analyze) >= max_files:
                break

        logger.info(f"Found {len(files_to_analyze)} files to analyze for secrets")

        # Analyze each file with LLM
        all_findings = []
        for file_path in files_to_analyze:
            logger.info(f"Analyzing: {file_path.relative_to(workspace)}")

            try:
                findings = await self._analyze_file_for_secrets(
                    file_path=file_path,
                    workspace=workspace,
                    agent_url=agent_url,
                    llm_model=llm_model,
                    llm_provider=llm_provider,
                    timeout=timeout
                )
                all_findings.extend(findings)

            except Exception as e:
                logger.error(f"Error analyzing {file_path}: {e}")
                # Continue with next file
                continue

        logger.info(f"LLM secret detection complete. Found {len(all_findings)} potential secrets.")

        # Create result
        return self.create_result(
            findings=all_findings,
            status="success",
            summary={
                "files_analyzed": len(files_to_analyze),
                "total_secrets": len(all_findings),
                "agent_url": agent_url,
                "model": f"{llm_provider}/{llm_model}"
            }
        )

    async def _analyze_file_for_secrets(
        self,
        file_path: Path,
        workspace: Path,
        agent_url: str,
        llm_model: str,
        llm_provider: str,
        timeout: int
    ) -> List[ModuleFinding]:
        """Analyze a single file for secrets using LLM"""

        # Read file content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code_content = f.read()
        except Exception as e:
            logger.error(f"Failed to read {file_path}: {e}")
            return []

        # Build specialized prompt for secret detection
        system_prompt = (
            "You are a security expert specialized in detecting secrets and credentials in code. "
            "Your job is to find REAL secrets that could be exploited. Be thorough and aggressive.\n\n"
            "For each secret found, respond in this exact format:\n"
            "SECRET_FOUND: [type like 'AWS Key', 'GitHub Token', 'Database Password']\n"
            "SEVERITY: [critical/high/medium/low]\n"
            "LINE: [exact line number]\n"
            "CONFIDENCE: [high/medium/low]\n"
            "DESCRIPTION: [brief explanation]\n\n"
            "EXAMPLES of secrets to find:\n"
            "1. API Keys: 'AKIA...', 'ghp_...', 'sk_live_...', 'SG.'\n"
            "2. Tokens: Bearer tokens, OAuth tokens, JWT secrets\n"
            "3. Passwords: Database passwords, admin passwords in configs\n"
            "4. Connection Strings: mongodb://, postgres://, redis:// with credentials\n"
            "5. Private Keys: -----BEGIN PRIVATE KEY-----, -----BEGIN RSA PRIVATE KEY-----\n"
            "6. Cloud Credentials: AWS keys, GCP keys, Azure keys\n"
            "7. Encryption Keys: AES keys, secret keys in config\n"
            "8. Webhook URLs: URLs with tokens like hooks.slack.com/services/...\n\n"
            "FIND EVERYTHING that looks like a real credential, password, key, or token.\n"
            "DO NOT be overly cautious. Report anything suspicious.\n\n"
            "If absolutely no secrets exist, respond with 'NO_SECRETS_FOUND'."
        )

        user_message = (
            f"Analyze this code for secrets and credentials:\n\n"
            f"File: {file_path.relative_to(workspace)}\n\n"
            f"```\n{code_content}\n```"
        )

        # Call LLM via A2A wrapper
        try:
            from fuzzforge_ai.a2a_wrapper import send_agent_task

            result = await send_agent_task(
                url=agent_url,
                model=llm_model,
                provider=llm_provider,
                prompt=system_prompt,
                message=user_message,
                context=f"secret_detection_{file_path.stem}",
                timeout=float(timeout)
            )

            llm_response = result.text

            # Debug: Log LLM response
            logger.debug(f"LLM response for {file_path.name}: {llm_response[:200]}...")

        except Exception as e:
            logger.error(f"A2A call failed for {file_path}: {e}")
            return []

        # Parse LLM response into findings
        findings = self._parse_llm_response(
            llm_response=llm_response,
            file_path=file_path,
            workspace=workspace
        )

        if findings:
            logger.info(f"Found {len(findings)} secrets in {file_path.name}")
        else:
            logger.debug(f"No secrets found in {file_path.name}. Response: {llm_response[:500]}")

        return findings

    def _parse_llm_response(
        self,
        llm_response: str,
        file_path: Path,
        workspace: Path
    ) -> List[ModuleFinding]:
        """Parse LLM response into structured findings"""

        if "NO_SECRETS_FOUND" in llm_response:
            return []

        findings = []
        relative_path = str(file_path.relative_to(workspace))

        # Simple parser for the expected format
        lines = llm_response.split('\n')
        current_secret = {}

        for line in lines:
            line = line.strip()

            if line.startswith("SECRET_FOUND:"):
                # Save previous secret if exists
                if current_secret:
                    findings.append(self._create_secret_finding(current_secret, relative_path))
                current_secret = {"type": line.replace("SECRET_FOUND:", "").strip()}

            elif line.startswith("SEVERITY:"):
                severity = line.replace("SEVERITY:", "").strip().lower()
                current_secret["severity"] = severity

            elif line.startswith("LINE:"):
                line_num = line.replace("LINE:", "").strip()
                try:
                    current_secret["line"] = int(line_num)
                except ValueError:
                    current_secret["line"] = None

            elif line.startswith("CONFIDENCE:"):
                confidence = line.replace("CONFIDENCE:", "").strip().lower()
                current_secret["confidence"] = confidence

            elif line.startswith("DESCRIPTION:"):
                current_secret["description"] = line.replace("DESCRIPTION:", "").strip()

        # Save last secret
        if current_secret:
            findings.append(self._create_secret_finding(current_secret, relative_path))

        return findings

    def _create_secret_finding(self, secret: Dict[str, Any], file_path: str) -> ModuleFinding:
        """Create a ModuleFinding from parsed secret"""

        severity_map = {
            "critical": "critical",
            "high": "high",
            "medium": "medium",
            "low": "low"
        }

        severity = severity_map.get(secret.get("severity", "medium"), "medium")
        confidence = secret.get("confidence", "medium")

        # Adjust severity based on confidence
        if confidence == "low" and severity == "critical":
            severity = "high"
        elif confidence == "low" and severity == "high":
            severity = "medium"

        # Create finding
        title = f"LLM detected secret: {secret.get('type', 'Unknown secret')}"
        description = secret.get("description", "An LLM identified this as a potential secret.")
        description += f"\n\nConfidence: {confidence}"

        return self.create_finding(
            title=title,
            description=description,
            severity=severity,
            category="secret_detection",
            file_path=file_path,
            line_start=secret.get("line"),
            recommendation=self._get_secret_recommendation(secret.get("type", "")),
            metadata={
                "tool": "llm-secret-detector",
                "secret_type": secret.get("type", "unknown"),
                "confidence": confidence,
                "detection_method": "semantic-analysis"
            }
        )

    def _get_secret_recommendation(self, secret_type: str) -> str:
        """Get remediation recommendation for detected secret"""
        return (
            f"A potential {secret_type} was detected by AI analysis. "
            f"Verify whether this is a real secret or a false positive. "
            f"If real: (1) Revoke the credential immediately, "
            f"(2) Remove from codebase and Git history, "
            f"(3) Rotate to a new secret, "
            f"(4) Use secret management tools for storage. "
            f"Implement pre-commit hooks to prevent future leaks."
        )
