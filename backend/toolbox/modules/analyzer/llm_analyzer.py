"""
LLM Analyzer Module - Uses AI to analyze code for security issues
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

try:
    from toolbox.modules.base import BaseModule, ModuleMetadata, ModuleResult
except ImportError:
    try:
        from modules.base import BaseModule, ModuleMetadata, ModuleResult
    except ImportError:
        from src.toolbox.modules.base import BaseModule, ModuleMetadata, ModuleResult

logger = logging.getLogger(__name__)


class LLMAnalyzer(BaseModule):
    """
    Uses an LLM to analyze code for potential security issues.

    This module:
    - Sends code to an LLM agent via A2A protocol
    - Asks the LLM to identify security vulnerabilities
    - Collects findings and returns them in structured format
    """

    def get_metadata(self) -> ModuleMetadata:
        """Get module metadata"""
        return ModuleMetadata(
            name="llm_analyzer",
            version="1.0.0",
            description="Uses AI to analyze code for security issues",
            author="FuzzForge Team",
            category="analyzer",
            tags=["llm", "ai", "security", "analysis"],
            input_schema={
                "agent_url": {
                    "type": "string",
                    "description": "A2A agent endpoint URL",
                    "default": "http://fuzzforge-task-agent:8000/a2a/litellm_agent"
                },
                "llm_model": {
                    "type": "string",
                    "description": "LLM model to use",
                    "default": "gpt-4o-mini"
                },
                "llm_provider": {
                    "type": "string",
                    "description": "LLM provider (openai, anthropic, etc.)",
                    "default": "openai"
                },
                "file_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "File patterns to analyze",
                    "default": ["*.py", "*.js", "*.ts", "*.java", "*.go"]
                },
                "max_files": {
                    "type": "integer",
                    "description": "Maximum number of files to analyze",
                    "default": 5
                },
                "max_file_size": {
                    "type": "integer",
                    "description": "Maximum file size in bytes",
                    "default": 50000  # 50KB
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout per file in seconds",
                    "default": 60
                }
            },
            output_schema={
                "findings": {
                    "type": "array",
                    "description": "Security issues identified by LLM"
                }
            },
            requires_workspace=True
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
        if not agent_url or not isinstance(agent_url, str):
            raise ValueError("agent_url must be a valid URL string")

        max_files = config.get("max_files", 5)
        if not isinstance(max_files, int) or max_files <= 0:
            raise ValueError("max_files must be a positive integer")

        return True

    async def execute(self, config: Dict[str, Any], workspace: Path) -> ModuleResult:
        """
        Execute the LLM analysis module.

        Args:
            config: Module configuration
            workspace: Path to the workspace containing code to analyze

        Returns:
            ModuleResult with findings from LLM analysis
        """
        # Start execution timer
        self.start_timer()

        logger.info(f"Starting LLM analysis in workspace: {workspace}")

        # Extract configuration
        agent_url = config.get("agent_url", "http://fuzzforge-task-agent:8000/a2a/litellm_agent")
        llm_model = config.get("llm_model", "gpt-4o-mini")
        llm_provider = config.get("llm_provider", "openai")
        file_patterns = config.get("file_patterns", ["*.py", "*.js", "*.ts", "*.java", "*.go"])
        max_files = config.get("max_files", 5)
        max_file_size = config.get("max_file_size", 50000)
        timeout = config.get("timeout", 60)

        # Find files to analyze
        files_to_analyze = []
        for pattern in file_patterns:
            for file_path in workspace.rglob(pattern):
                if file_path.is_file():
                    try:
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

        logger.info(f"Found {len(files_to_analyze)} files to analyze")

        # Analyze each file
        all_findings = []
        for file_path in files_to_analyze:
            logger.info(f"Analyzing: {file_path.relative_to(workspace)}")

            try:
                findings = await self._analyze_file(
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

        logger.info(f"LLM analysis complete. Found {len(all_findings)} issues.")

        # Create result using base module helper
        return self.create_result(
            findings=all_findings,
            status="success",
            summary={
                "files_analyzed": len(files_to_analyze),
                "total_findings": len(all_findings),
                "agent_url": agent_url,
                "model": f"{llm_provider}/{llm_model}"
            }
        )

    async def _analyze_file(
        self,
        file_path: Path,
        workspace: Path,
        agent_url: str,
        llm_model: str,
        llm_provider: str,
        timeout: int
    ) -> List[Dict[str, Any]]:
        """Analyze a single file with LLM"""

        # Read file content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code_content = f.read()
        except Exception as e:
            logger.error(f"Failed to read {file_path}: {e}")
            return []

        # Determine language from extension
        extension = file_path.suffix.lower()
        language_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
            ".c": "c",
            ".cpp": "cpp",
        }
        language = language_map.get(extension, "code")

        # Build prompt for LLM
        system_prompt = (
            "You are a security code analyzer. Analyze the provided code and identify "
            "potential security vulnerabilities, bugs, and code quality issues. "
            "For each issue found, respond in this exact format:\n"
            "ISSUE: [short title]\n"
            "SEVERITY: [error/warning/note]\n"
            "LINE: [line number or 'unknown']\n"
            "DESCRIPTION: [detailed explanation]\n\n"
            "If no issues are found, respond with 'NO_ISSUES_FOUND'."
        )

        user_message = (
            f"Analyze this {language} code for security vulnerabilities:\n\n"
            f"File: {file_path.relative_to(workspace)}\n\n"
            f"```{language}\n{code_content}\n```"
        )

        # Call LLM via A2A wrapper (lazy import to avoid Temporal sandbox restrictions)
        try:
            from fuzzforge_ai.a2a_wrapper import send_agent_task

            result = await send_agent_task(
                url=agent_url,
                model=llm_model,
                provider=llm_provider,
                prompt=system_prompt,
                message=user_message,
                context=f"llm_analysis_{file_path.stem}",
                timeout=float(timeout)
            )

            llm_response = result.text

        except Exception as e:
            logger.error(f"A2A call failed for {file_path}: {e}")
            return []

        # Parse LLM response into findings
        findings = self._parse_llm_response(
            llm_response=llm_response,
            file_path=file_path,
            workspace=workspace
        )

        return findings

    def _parse_llm_response(
        self,
        llm_response: str,
        file_path: Path,
        workspace: Path
    ) -> List:
        """Parse LLM response into structured findings"""

        if "NO_ISSUES_FOUND" in llm_response:
            return []

        findings = []
        relative_path = str(file_path.relative_to(workspace))

        # Simple parser for the expected format
        lines = llm_response.split('\n')
        current_issue = {}

        for line in lines:
            line = line.strip()

            if line.startswith("ISSUE:"):
                # Save previous issue if exists
                if current_issue:
                    findings.append(self._create_module_finding(current_issue, relative_path))
                current_issue = {"title": line.replace("ISSUE:", "").strip()}

            elif line.startswith("SEVERITY:"):
                current_issue["severity"] = line.replace("SEVERITY:", "").strip().lower()

            elif line.startswith("LINE:"):
                line_num = line.replace("LINE:", "").strip()
                try:
                    current_issue["line"] = int(line_num)
                except ValueError:
                    current_issue["line"] = None

            elif line.startswith("DESCRIPTION:"):
                current_issue["description"] = line.replace("DESCRIPTION:", "").strip()

        # Save last issue
        if current_issue:
            findings.append(self._create_module_finding(current_issue, relative_path))

        return findings

    def _create_module_finding(self, issue: Dict[str, Any], file_path: str):
        """Create a ModuleFinding from parsed issue"""

        severity_map = {
            "error": "critical",
            "warning": "medium",
            "note": "low",
            "info": "low"
        }

        # Use base class helper to create proper ModuleFinding
        return self.create_finding(
            title=issue.get("title", "Security issue detected"),
            description=issue.get("description", ""),
            severity=severity_map.get(issue.get("severity", "warning"), "medium"),
            category="security",
            file_path=file_path,
            line_start=issue.get("line"),
            metadata={
                "tool": "llm-analyzer",
                "type": "llm-security-analysis"
            }
        )
