"""
Security Analyzer Module - Analyzes code for security vulnerabilities
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
import re
from pathlib import Path
from typing import Dict, Any, List

try:
    from toolbox.modules.base import BaseModule, ModuleMetadata, ModuleResult, ModuleFinding
except ImportError:
    try:
        from modules.base import BaseModule, ModuleMetadata, ModuleResult, ModuleFinding
    except ImportError:
        from src.toolbox.modules.base import BaseModule, ModuleMetadata, ModuleResult, ModuleFinding

logger = logging.getLogger(__name__)


class SecurityAnalyzer(BaseModule):
    """
    Analyzes source code for common security vulnerabilities.

    This module:
    - Detects hardcoded secrets and credentials
    - Identifies dangerous function calls
    - Finds SQL injection vulnerabilities
    - Detects insecure configurations
    """

    def get_metadata(self) -> ModuleMetadata:
        """Get module metadata"""
        return ModuleMetadata(
            name="security_analyzer",
            version="1.0.0",
            description="Analyzes code for security vulnerabilities",
            author="FuzzForge Team",
            category="analyzer",
            tags=["security", "vulnerabilities", "static-analysis"],
            input_schema={
                "file_extensions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "File extensions to analyze",
                    "default": [".py", ".js", ".java", ".php", ".rb", ".go"]
                },
                "check_secrets": {
                    "type": "boolean",
                    "description": "Check for hardcoded secrets",
                    "default": True
                },
                "check_sql": {
                    "type": "boolean",
                    "description": "Check for SQL injection risks",
                    "default": True
                },
                "check_dangerous_functions": {
                    "type": "boolean",
                    "description": "Check for dangerous function calls",
                    "default": True
                }
            },
            output_schema={
                "findings": {
                    "type": "array",
                    "description": "List of security findings"
                }
            },
            requires_workspace=True
        )

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate module configuration"""
        extensions = config.get("file_extensions", [])
        if not isinstance(extensions, list):
            raise ValueError("file_extensions must be a list")

        return True

    async def execute(self, config: Dict[str, Any], workspace: Path) -> ModuleResult:
        """
        Execute the security analysis module.

        Args:
            config: Module configuration
            workspace: Path to the workspace directory

        Returns:
            ModuleResult with security findings
        """
        self.start_timer()
        self.validate_workspace(workspace)
        self.validate_config(config)

        findings = []
        files_analyzed = 0

        # Get configuration
        file_extensions = config.get("file_extensions", [".py", ".js", ".java", ".php", ".rb", ".go"])
        check_secrets = config.get("check_secrets", True)
        check_sql = config.get("check_sql", True)
        check_dangerous = config.get("check_dangerous_functions", True)

        logger.info(f"Analyzing files with extensions: {file_extensions}")

        try:
            # Analyze each file
            for ext in file_extensions:
                for file_path in workspace.rglob(f"*{ext}"):
                    if not file_path.is_file():
                        continue

                    files_analyzed += 1
                    relative_path = file_path.relative_to(workspace)

                    try:
                        content = file_path.read_text(encoding='utf-8', errors='ignore')
                        lines = content.splitlines()

                        # Check for secrets
                        if check_secrets:
                            secret_findings = self._check_hardcoded_secrets(
                                content, lines, relative_path
                            )
                            findings.extend(secret_findings)

                        # Check for SQL injection
                        if check_sql and ext in [".py", ".php", ".java", ".js"]:
                            sql_findings = self._check_sql_injection(
                                content, lines, relative_path
                            )
                            findings.extend(sql_findings)

                        # Check for dangerous functions
                        if check_dangerous:
                            dangerous_findings = self._check_dangerous_functions(
                                content, lines, relative_path, ext
                            )
                            findings.extend(dangerous_findings)

                    except Exception as e:
                        logger.error(f"Error analyzing file {relative_path}: {e}")

            # Create summary
            summary = {
                "files_analyzed": files_analyzed,
                "total_findings": len(findings),
                "extensions_scanned": file_extensions
            }

            return self.create_result(
                findings=findings,
                status="success" if files_analyzed > 0 else "partial",
                summary=summary,
                metadata={
                    "workspace": str(workspace),
                    "config": config
                }
            )

        except Exception as e:
            logger.error(f"Security analyzer failed: {e}")
            return self.create_result(
                findings=findings,
                status="failed",
                error=str(e)
            )

    def _check_hardcoded_secrets(
        self, content: str, lines: List[str], file_path: Path
    ) -> List[ModuleFinding]:
        """
        Check for hardcoded secrets in code.

        Args:
            content: File content
            lines: File lines
            file_path: Relative file path

        Returns:
            List of findings
        """
        findings = []

        # Patterns for secrets
        secret_patterns = [
            (r'api[_-]?key\s*=\s*["\']([^"\']{20,})["\']', 'API Key'),
            (r'api[_-]?secret\s*=\s*["\']([^"\']{20,})["\']', 'API Secret'),
            (r'password\s*=\s*["\']([^"\']+)["\']', 'Hardcoded Password'),
            (r'token\s*=\s*["\']([^"\']{20,})["\']', 'Authentication Token'),
            (r'aws[_-]?access[_-]?key\s*=\s*["\']([^"\']+)["\']', 'AWS Access Key'),
            (r'aws[_-]?secret[_-]?key\s*=\s*["\']([^"\']+)["\']', 'AWS Secret Key'),
            (r'private[_-]?key\s*=\s*["\']([^"\']+)["\']', 'Private Key'),
            (r'["\']([A-Za-z0-9]{32,})["\']', 'Potential Secret Hash'),
            (r'Bearer\s+([A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+)', 'JWT Token'),
        ]

        for pattern, secret_type in secret_patterns:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                # Find line number
                line_num = content[:match.start()].count('\n') + 1
                line_content = lines[line_num - 1] if line_num <= len(lines) else ""

                # Skip common false positives
                if self._is_false_positive_secret(match.group(0)):
                    continue

                findings.append(self.create_finding(
                    title=f"Hardcoded {secret_type} detected",
                    description=f"Found potential hardcoded {secret_type} in {file_path}",
                    severity="high" if "key" in secret_type.lower() else "medium",
                    category="hardcoded_secret",
                    file_path=str(file_path),
                    line_start=line_num,
                    code_snippet=line_content.strip()[:100],
                    recommendation=f"Remove hardcoded {secret_type} and use environment variables or secure vault",
                    metadata={"secret_type": secret_type}
                ))

        return findings

    def _check_sql_injection(
        self, content: str, lines: List[str], file_path: Path
    ) -> List[ModuleFinding]:
        """
        Check for potential SQL injection vulnerabilities.

        Args:
            content: File content
            lines: File lines
            file_path: Relative file path

        Returns:
            List of findings
        """
        findings = []

        # SQL injection patterns
        sql_patterns = [
            (r'(SELECT|INSERT|UPDATE|DELETE).*\+\s*[\'"]?\s*\+?\s*\w+', 'String concatenation in SQL'),
            (r'(SELECT|INSERT|UPDATE|DELETE).*%\s*[\'"]?\s*%?\s*\w+', 'String formatting in SQL'),
            (r'f[\'"].*?(SELECT|INSERT|UPDATE|DELETE).*?\{.*?\}', 'F-string in SQL query'),
            (r'query\s*=.*?\+', 'Dynamic query building'),
            (r'execute\s*\(.*?\+.*?\)', 'Dynamic execute statement'),
        ]

        for pattern, vuln_type in sql_patterns:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                line_num = content[:match.start()].count('\n') + 1
                line_content = lines[line_num - 1] if line_num <= len(lines) else ""

                findings.append(self.create_finding(
                    title=f"Potential SQL Injection: {vuln_type}",
                    description=f"Detected potential SQL injection vulnerability via {vuln_type}",
                    severity="high",
                    category="sql_injection",
                    file_path=str(file_path),
                    line_start=line_num,
                    code_snippet=line_content.strip()[:100],
                    recommendation="Use parameterized queries or prepared statements instead",
                    metadata={"vulnerability_type": vuln_type}
                ))

        return findings

    def _check_dangerous_functions(
        self, content: str, lines: List[str], file_path: Path, ext: str
    ) -> List[ModuleFinding]:
        """
        Check for dangerous function calls.

        Args:
            content: File content
            lines: File lines
            file_path: Relative file path
            ext: File extension

        Returns:
            List of findings
        """
        findings = []

        # Language-specific dangerous functions
        dangerous_functions = {
            ".py": [
                (r'eval\s*\(', 'eval()', 'Arbitrary code execution'),
                (r'exec\s*\(', 'exec()', 'Arbitrary code execution'),
                (r'os\.system\s*\(', 'os.system()', 'Command injection risk'),
                (r'subprocess\.call\s*\(.*shell=True', 'subprocess with shell=True', 'Command injection risk'),
                (r'pickle\.loads?\s*\(', 'pickle.load()', 'Deserialization vulnerability'),
            ],
            ".js": [
                (r'eval\s*\(', 'eval()', 'Arbitrary code execution'),
                (r'new\s+Function\s*\(', 'new Function()', 'Arbitrary code execution'),
                (r'innerHTML\s*=', 'innerHTML', 'XSS vulnerability'),
                (r'document\.write\s*\(', 'document.write()', 'XSS vulnerability'),
            ],
            ".php": [
                (r'eval\s*\(', 'eval()', 'Arbitrary code execution'),
                (r'exec\s*\(', 'exec()', 'Command execution'),
                (r'system\s*\(', 'system()', 'Command execution'),
                (r'shell_exec\s*\(', 'shell_exec()', 'Command execution'),
                (r'\$_GET\[', 'Direct $_GET usage', 'Input validation missing'),
                (r'\$_POST\[', 'Direct $_POST usage', 'Input validation missing'),
            ]
        }

        if ext in dangerous_functions:
            for pattern, func_name, risk_type in dangerous_functions[ext]:
                for match in re.finditer(pattern, content):
                    line_num = content[:match.start()].count('\n') + 1
                    line_content = lines[line_num - 1] if line_num <= len(lines) else ""

                    findings.append(self.create_finding(
                        title=f"Dangerous function: {func_name}",
                        description=f"Use of potentially dangerous function {func_name}: {risk_type}",
                        severity="medium",
                        category="dangerous_function",
                        file_path=str(file_path),
                        line_start=line_num,
                        code_snippet=line_content.strip()[:100],
                        recommendation=f"Consider safer alternatives to {func_name}",
                        metadata={
                            "function": func_name,
                            "risk": risk_type
                        }
                    ))

        return findings

    def _is_false_positive_secret(self, value: str) -> bool:
        """
        Check if a potential secret is likely a false positive.

        Args:
            value: Potential secret value

        Returns:
            True if likely false positive
        """
        false_positive_patterns = [
            'example',
            'test',
            'demo',
            'sample',
            'dummy',
            'placeholder',
            'xxx',
            '123',
            'change',
            'your',
            'here'
        ]

        value_lower = value.lower()
        return any(pattern in value_lower for pattern in false_positive_patterns)