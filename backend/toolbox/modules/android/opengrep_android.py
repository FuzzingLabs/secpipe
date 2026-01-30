"""
OpenGrep Android Static Analysis Module

Pattern-based static analysis for Android applications using OpenGrep/Semgrep
with Android-specific security rules.
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

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Any, List

try:
    from toolbox.modules.base import BaseModule, ModuleMetadata, ModuleFinding, ModuleResult
except ImportError:
    try:
        from modules.base import BaseModule, ModuleMetadata, ModuleFinding, ModuleResult
    except ImportError:
        from src.toolbox.modules.base import BaseModule, ModuleMetadata, ModuleFinding, ModuleResult

logger = logging.getLogger(__name__)


class OpenGrepAndroid(BaseModule):
    """OpenGrep static analysis module specialized for Android security"""

    def get_metadata(self) -> ModuleMetadata:
        """Get module metadata"""
        return ModuleMetadata(
            name="opengrep_android",
            version="1.45.0",
            description="Android-focused static analysis using OpenGrep/Semgrep with custom security rules for Java/Kotlin",
            author="FuzzForge Team",
            category="android",
            tags=["sast", "android", "opengrep", "semgrep", "java", "kotlin", "security"],
            input_schema={
                "type": "object",
                "properties": {
                    "config": {
                        "type": "string",
                        "enum": ["auto", "p/security-audit", "p/owasp-top-ten", "p/cwe-top-25"],
                        "default": "auto",
                        "description": "Rule configuration to use"
                    },
                    "custom_rules_path": {
                        "type": "string",
                        "description": "Path to a directory containing custom OpenGrep rules (Android-specific rules recommended)",
                        "default": None,
                    },
                    "languages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific languages to analyze (defaults to java, kotlin for Android)",
                        "default": ["java", "kotlin"],
                    },
                    "include_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "File patterns to include",
                        "default": [],
                    },
                    "exclude_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "File patterns to exclude",
                        "default": [],
                    },
                    "max_target_bytes": {
                        "type": "integer",
                        "default": 1000000,
                        "description": "Maximum file size to analyze (bytes)"
                    },
                    "timeout": {
                        "type": "integer",
                        "default": 300,
                        "description": "Analysis timeout in seconds"
                    },
                    "severity": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["ERROR", "WARNING", "INFO"]},
                        "default": ["ERROR", "WARNING", "INFO"],
                        "description": "Minimum severity levels to report"
                    },
                    "confidence": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                        "default": ["HIGH", "MEDIUM", "LOW"],
                        "description": "Minimum confidence levels to report"
                    }
                }
            },
            output_schema={
                "type": "object",
                "properties": {
                    "findings": {
                        "type": "array",
                        "description": "Security findings from OpenGrep analysis"
                    },
                    "total_findings": {"type": "integer"},
                    "severity_counts": {"type": "object"},
                    "files_analyzed": {"type": "integer"},
                }
            },
            requires_workspace=True,
        )

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate configuration"""
        timeout = config.get("timeout", 300)
        if not isinstance(timeout, int) or timeout < 30 or timeout > 3600:
            raise ValueError("Timeout must be between 30 and 3600 seconds")

        max_bytes = config.get("max_target_bytes", 1000000)
        if not isinstance(max_bytes, int) or max_bytes < 1000 or max_bytes > 10000000:
            raise ValueError("max_target_bytes must be between 1000 and 10000000")

        custom_rules_path = config.get("custom_rules_path")
        if custom_rules_path:
            rules_path = Path(custom_rules_path)
            if not rules_path.exists():
                logger.warning(f"Custom rules path does not exist: {custom_rules_path}")

        return True

    async def execute(self, config: Dict[str, Any], workspace: Path) -> ModuleResult:
        """Execute OpenGrep static analysis on Android code"""
        self.start_timer()

        try:
            # Validate inputs
            self.validate_config(config)
            self.validate_workspace(workspace)

            logger.info(f"Running OpenGrep Android analysis on {workspace}")

            # Build opengrep command
            cmd = ["opengrep", "scan", "--json"]

            # Add configuration
            custom_rules_path = config.get("custom_rules_path")
            use_custom_rules = False
            if custom_rules_path and Path(custom_rules_path).exists():
                cmd.extend(["--config", custom_rules_path])
                use_custom_rules = True
                logger.info(f"Using custom Android rules from: {custom_rules_path}")
            else:
                config_type = config.get("config", "auto")
                if config_type == "auto":
                    cmd.extend(["--config", "auto"])
                else:
                    cmd.extend(["--config", config_type])

            # Add timeout
            cmd.extend(["--timeout", str(config.get("timeout", 300))])

            # Add max target bytes
            cmd.extend(["--max-target-bytes", str(config.get("max_target_bytes", 1000000))])

            # Add languages if specified (but NOT when using custom rules)
            languages = config.get("languages", ["java", "kotlin"])
            if languages and not use_custom_rules:
                langs = ",".join(languages)
                cmd.extend(["--lang", langs])
                logger.debug(f"Analyzing languages: {langs}")

            # Add include patterns
            include_patterns = config.get("include_patterns", [])
            for pattern in include_patterns:
                cmd.extend(["--include", pattern])

            # Add exclude patterns
            exclude_patterns = config.get("exclude_patterns", [])
            for pattern in exclude_patterns:
                cmd.extend(["--exclude", pattern])

            # Add severity filter if single level requested
            severity_levels = config.get("severity", ["ERROR", "WARNING", "INFO"])
            if severity_levels and len(severity_levels) == 1:
                cmd.extend(["--severity", severity_levels[0]])

            # Disable metrics collection
            cmd.append("--disable-version-check")
            cmd.append("--no-git-ignore")

            # Add target directory
            cmd.append(str(workspace))

            logger.debug(f"Running command: {' '.join(cmd)}")

            # Run OpenGrep
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workspace
            )

            stdout, stderr = await process.communicate()

            # Parse results
            findings = []
            if process.returncode in [0, 1]:  # 0 = no findings, 1 = findings found
                findings = self._parse_opengrep_output(stdout.decode(), workspace, config)
                logger.info(f"OpenGrep found {len(findings)} potential security issues")
            else:
                error_msg = stderr.decode()
                logger.error(f"OpenGrep failed: {error_msg}")
                return self.create_result(
                    findings=[],
                    status="failed",
                    error=f"OpenGrep execution failed (exit code {process.returncode}): {error_msg[:500]}"
                )

            # Create summary
            summary = self._create_summary(findings)

            return self.create_result(
                findings=findings,
                status="success",
                summary=summary,
                metadata={
                    "tool": "opengrep",
                    "tool_version": "1.45.0",
                    "languages": languages,
                    "custom_rules": bool(custom_rules_path),
                }
            )

        except Exception as e:
            logger.error(f"OpenGrep Android module failed: {e}", exc_info=True)
            return self.create_result(
                findings=[],
                status="failed",
                error=str(e)
            )

    def _parse_opengrep_output(self, output: str, workspace: Path, config: Dict[str, Any]) -> List[ModuleFinding]:
        """Parse OpenGrep JSON output into findings"""
        findings = []

        if not output.strip():
            return findings

        try:
            data = json.loads(output)
            results = data.get("results", [])
            logger.debug(f"OpenGrep returned {len(results)} raw results")

            # Get filtering criteria
            allowed_severities = set(config.get("severity", ["ERROR", "WARNING", "INFO"]))
            allowed_confidences = set(config.get("confidence", ["HIGH", "MEDIUM", "LOW"]))

            for result in results:
                # Extract basic info
                rule_id = result.get("check_id", "unknown")
                message = result.get("message", "")
                extra = result.get("extra", {})
                severity = extra.get("severity", "INFO").upper()

                # File location info
                path_info = result.get("path", "")
                start_line = result.get("start", {}).get("line", 0)
                end_line = result.get("end", {}).get("line", 0)

                # Code snippet
                lines = extra.get("lines", "")

                # Metadata
                rule_metadata = extra.get("metadata", {})
                cwe = rule_metadata.get("cwe", [])
                owasp = rule_metadata.get("owasp", [])
                confidence = extra.get("confidence", rule_metadata.get("confidence", "MEDIUM")).upper()

                # Apply severity filter
                if severity not in allowed_severities:
                    continue

                # Apply confidence filter
                if confidence not in allowed_confidences:
                    continue

                # Make file path relative to workspace
                if path_info:
                    try:
                        rel_path = Path(path_info).relative_to(workspace)
                        path_info = str(rel_path)
                    except ValueError:
                        pass

                # Map severity to our standard levels
                finding_severity = self._map_severity(severity)

                # Create finding
                finding = self.create_finding(
                    title=f"Android Security: {rule_id}",
                    description=message or f"OpenGrep rule {rule_id} triggered",
                    severity=finding_severity,
                    category=self._get_category(rule_id, extra),
                    file_path=path_info if path_info else None,
                    line_start=start_line if start_line > 0 else None,
                    line_end=end_line if end_line > 0 and end_line != start_line else None,
                    code_snippet=lines.strip() if lines else None,
                    recommendation=self._get_recommendation(rule_id, extra),
                    metadata={
                        "rule_id": rule_id,
                        "opengrep_severity": severity,
                        "confidence": confidence,
                        "cwe": cwe,
                        "owasp": owasp,
                        "fix": extra.get("fix", ""),
                        "impact": extra.get("impact", ""),
                        "likelihood": extra.get("likelihood", ""),
                        "references": extra.get("references", []),
                        "tool": "opengrep",
                    }
                )

                findings.append(finding)

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse OpenGrep output: {e}. Output snippet: {output[:200]}...")
        except Exception as e:
            logger.warning(f"Error processing OpenGrep results: {e}", exc_info=True)

        return findings

    def _map_severity(self, opengrep_severity: str) -> str:
        """Map OpenGrep severity to our standard severity levels"""
        severity_map = {
            "ERROR": "high",
            "WARNING": "medium",
            "INFO": "low"
        }
        return severity_map.get(opengrep_severity.upper(), "medium")

    def _get_category(self, rule_id: str, extra: Dict[str, Any]) -> str:
        """Determine finding category based on rule and metadata"""
        rule_metadata = extra.get("metadata", {})
        cwe_list = rule_metadata.get("cwe", [])
        owasp_list = rule_metadata.get("owasp", [])

        rule_lower = rule_id.lower()

        # Android-specific categories
        if "injection" in rule_lower or "sql" in rule_lower:
            return "injection"
        elif "intent" in rule_lower:
            return "android-intent"
        elif "webview" in rule_lower:
            return "android-webview"
        elif "deeplink" in rule_lower:
            return "android-deeplink"
        elif "storage" in rule_lower or "sharedpreferences" in rule_lower:
            return "android-storage"
        elif "logging" in rule_lower or "log" in rule_lower:
            return "android-logging"
        elif "clipboard" in rule_lower:
            return "android-clipboard"
        elif "activity" in rule_lower or "service" in rule_lower or "provider" in rule_lower:
            return "android-component"
        elif "crypto" in rule_lower or "encrypt" in rule_lower:
            return "cryptography"
        elif "hardcode" in rule_lower or "secret" in rule_lower:
            return "secrets"
        elif "auth" in rule_lower:
            return "authentication"
        elif cwe_list:
            return f"cwe-{cwe_list[0]}"
        elif owasp_list:
            return f"owasp-{owasp_list[0].replace(' ', '-').lower()}"
        else:
            return "android-security"

    def _get_recommendation(self, rule_id: str, extra: Dict[str, Any]) -> str:
        """Generate recommendation based on rule and metadata"""
        fix_suggestion = extra.get("fix", "")
        if fix_suggestion:
            return fix_suggestion

        rule_lower = rule_id.lower()

        # Android-specific recommendations
        if "injection" in rule_lower or "sql" in rule_lower:
            return "Use parameterized queries or Room database with type-safe queries to prevent SQL injection."
        elif "intent" in rule_lower:
            return "Validate all incoming Intent data and use explicit Intents when possible to prevent Intent manipulation attacks."
        elif "webview" in rule_lower and "javascript" in rule_lower:
            return "Disable JavaScript in WebView if not needed, or implement proper JavaScript interfaces with @JavascriptInterface annotation."
        elif "deeplink" in rule_lower:
            return "Validate all deeplink URLs and sanitize user input to prevent deeplink hijacking attacks."
        elif "storage" in rule_lower or "sharedpreferences" in rule_lower:
            return "Encrypt sensitive data before storing in SharedPreferences or use EncryptedSharedPreferences for Android API 23+."
        elif "logging" in rule_lower:
            return "Remove sensitive data from logs in production builds. Use ProGuard/R8 to strip logging statements."
        elif "clipboard" in rule_lower:
            return "Avoid placing sensitive data on the clipboard. If necessary, clear clipboard data when no longer needed."
        elif "crypto" in rule_lower:
            return "Use modern cryptographic algorithms (AES-GCM, RSA-OAEP) and Android Keystore for key management."
        elif "hardcode" in rule_lower or "secret" in rule_lower:
            return "Remove hardcoded secrets. Use Android Keystore, environment variables, or secure configuration management."
        else:
            return "Review this Android security issue and apply appropriate fixes based on Android security best practices."

    def _create_summary(self, findings: List[ModuleFinding]) -> Dict[str, Any]:
        """Create analysis summary"""
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        category_counts = {}
        rule_counts = {}

        for finding in findings:
            # Count by severity
            severity_counts[finding.severity] += 1

            # Count by category
            category = finding.category
            category_counts[category] = category_counts.get(category, 0) + 1

            # Count by rule
            rule_id = finding.metadata.get("rule_id", "unknown")
            rule_counts[rule_id] = rule_counts.get(rule_id, 0) + 1

        return {
            "total_findings": len(findings),
            "severity_counts": severity_counts,
            "category_counts": category_counts,
            "top_rules": dict(sorted(rule_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
            "files_analyzed": len(set(f.file_path for f in findings if f.file_path))
        }
