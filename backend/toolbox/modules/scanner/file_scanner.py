"""
File Scanner Module - Scans and enumerates files in the workspace
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
import mimetypes
from pathlib import Path
from typing import Dict, Any
import hashlib

try:
    from toolbox.modules.base import BaseModule, ModuleMetadata, ModuleResult
except ImportError:
    try:
        from modules.base import BaseModule, ModuleMetadata, ModuleResult
    except ImportError:
        from src.toolbox.modules.base import BaseModule, ModuleMetadata, ModuleResult

logger = logging.getLogger(__name__)


class FileScanner(BaseModule):
    """
    Scans files in the mounted workspace and collects information.

    This module:
    - Enumerates files based on patterns
    - Detects file types
    - Calculates file hashes
    - Identifies potentially sensitive files
    """

    def get_metadata(self) -> ModuleMetadata:
        """Get module metadata"""
        return ModuleMetadata(
            name="file_scanner",
            version="1.0.0",
            description="Scans and enumerates files in the workspace",
            author="FuzzForge Team",
            category="scanner",
            tags=["files", "enumeration", "discovery"],
            input_schema={
                "patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "File patterns to scan (e.g., ['*.py', '*.js'])",
                    "default": ["*"]
                },
                "max_file_size": {
                    "type": "integer",
                    "description": "Maximum file size to scan in bytes",
                    "default": 10485760  # 10MB
                },
                "check_sensitive": {
                    "type": "boolean",
                    "description": "Check for sensitive file patterns",
                    "default": True
                },
                "calculate_hashes": {
                    "type": "boolean",
                    "description": "Calculate SHA256 hashes for files",
                    "default": False
                }
            },
            output_schema={
                "findings": {
                    "type": "array",
                    "description": "List of discovered files with metadata"
                }
            },
            requires_workspace=True
        )

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate module configuration"""
        patterns = config.get("patterns", ["*"])
        if not isinstance(patterns, list):
            raise ValueError("patterns must be a list")

        max_size = config.get("max_file_size", 10485760)
        if not isinstance(max_size, int) or max_size <= 0:
            raise ValueError("max_file_size must be a positive integer")

        return True

    async def execute(self, config: Dict[str, Any], workspace: Path) -> ModuleResult:
        """
        Execute the file scanning module.

        Args:
            config: Module configuration
            workspace: Path to the workspace directory

        Returns:
            ModuleResult with file findings
        """
        self.start_timer()
        self.validate_workspace(workspace)
        self.validate_config(config)

        findings = []
        file_count = 0
        total_size = 0
        file_types = {}

        # Get configuration
        patterns = config.get("patterns", ["*"])
        max_file_size = config.get("max_file_size", 10485760)
        check_sensitive = config.get("check_sensitive", True)
        calculate_hashes = config.get("calculate_hashes", False)

        logger.info(f"Scanning workspace with patterns: {patterns}")

        try:
            # Scan for each pattern
            for pattern in patterns:
                for file_path in workspace.rglob(pattern):
                    if not file_path.is_file():
                        continue

                    file_count += 1
                    relative_path = file_path.relative_to(workspace)

                    # Get file stats
                    try:
                        stats = file_path.stat()
                        file_size = stats.st_size
                        total_size += file_size

                        # Skip large files
                        if file_size > max_file_size:
                            logger.warning(f"Skipping large file: {relative_path} ({file_size} bytes)")
                            continue

                        # Detect file type
                        file_type = self._detect_file_type(file_path)
                        if file_type not in file_types:
                            file_types[file_type] = 0
                        file_types[file_type] += 1

                        # Check for sensitive files
                        if check_sensitive and self._is_sensitive_file(file_path):
                            findings.append(self.create_finding(
                                title=f"Potentially sensitive file: {relative_path.name}",
                                description=f"Found potentially sensitive file at {relative_path}",
                                severity="medium",
                                category="sensitive_file",
                                file_path=str(relative_path),
                                metadata={
                                    "file_size": file_size,
                                    "file_type": file_type
                                }
                            ))

                        # Calculate hash if requested
                        file_hash = None
                        if calculate_hashes and file_size < 1048576:  # Only hash files < 1MB
                            file_hash = self._calculate_hash(file_path)

                        # Create informational finding for each file
                        findings.append(self.create_finding(
                            title=f"File discovered: {relative_path.name}",
                            description=f"File: {relative_path}",
                            severity="info",
                            category="file_enumeration",
                            file_path=str(relative_path),
                            metadata={
                                "file_size": file_size,
                                "file_type": file_type,
                                "file_hash": file_hash
                            }
                        ))

                    except Exception as e:
                        logger.error(f"Error processing file {relative_path}: {e}")

            # Create summary
            summary = {
                "total_files": file_count,
                "total_size_bytes": total_size,
                "file_types": file_types,
                "patterns_scanned": patterns
            }

            return self.create_result(
                findings=findings,
                status="success",
                summary=summary,
                metadata={
                    "workspace": str(workspace),
                    "config": config
                }
            )

        except Exception as e:
            logger.error(f"File scanner failed: {e}")
            return self.create_result(
                findings=findings,
                status="failed",
                error=str(e)
            )

    def _detect_file_type(self, file_path: Path) -> str:
        """
        Detect the type of a file.

        Args:
            file_path: Path to the file

        Returns:
            File type string
        """
        # Try to determine from extension
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type:
            return mime_type

        # Check by extension
        ext = file_path.suffix.lower()
        type_map = {
            '.py': 'text/x-python',
            '.js': 'application/javascript',
            '.java': 'text/x-java',
            '.cpp': 'text/x-c++',
            '.c': 'text/x-c',
            '.go': 'text/x-go',
            '.rs': 'text/x-rust',
            '.rb': 'text/x-ruby',
            '.php': 'text/x-php',
            '.yaml': 'text/yaml',
            '.yml': 'text/yaml',
            '.json': 'application/json',
            '.xml': 'text/xml',
            '.md': 'text/markdown',
            '.txt': 'text/plain',
            '.sh': 'text/x-shellscript',
            '.bat': 'text/x-batch',
            '.ps1': 'text/x-powershell'
        }

        return type_map.get(ext, 'application/octet-stream')

    def _is_sensitive_file(self, file_path: Path) -> bool:
        """
        Check if a file might contain sensitive information.

        Args:
            file_path: Path to the file

        Returns:
            True if potentially sensitive
        """
        sensitive_patterns = [
            '.env',
            '.env.local',
            '.env.production',
            'credentials',
            'password',
            'secret',
            'private_key',
            'id_rsa',
            'id_dsa',
            '.pem',
            '.key',
            '.pfx',
            '.p12',
            'wallet',
            '.ssh',
            'token',
            'api_key',
            'config.json',
            'settings.json',
            '.git-credentials',
            '.npmrc',
            '.pypirc',
            '.docker/config.json'
        ]

        file_name_lower = file_path.name.lower()
        for pattern in sensitive_patterns:
            if pattern in file_name_lower:
                return True

        return False

    def _calculate_hash(self, file_path: Path) -> str:
        """
        Calculate SHA256 hash of a file.

        Args:
            file_path: Path to the file

        Returns:
            Hex string of SHA256 hash
        """
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"Failed to calculate hash for {file_path}: {e}")
            return None