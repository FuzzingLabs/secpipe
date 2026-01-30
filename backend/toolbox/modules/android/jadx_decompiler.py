"""
Jadx APK Decompilation Module

Decompiles Android APK files to Java source code using Jadx.
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
import shutil
import logging
from pathlib import Path
from typing import Dict, Any

try:
    from toolbox.modules.base import BaseModule, ModuleMetadata, ModuleResult
except ImportError:
    try:
        from modules.base import BaseModule, ModuleMetadata, ModuleResult
    except ImportError:
        from src.toolbox.modules.base import BaseModule, ModuleMetadata, ModuleResult

logger = logging.getLogger(__name__)


class JadxDecompiler(BaseModule):
    """Module for decompiling APK files to Java source code using Jadx"""

    def get_metadata(self) -> ModuleMetadata:
        return ModuleMetadata(
            name="jadx_decompiler",
            version="1.5.0",
            description="Android APK decompilation using Jadx - converts DEX bytecode to Java source",
            author="FuzzForge Team",
            category="android",
            tags=["android", "jadx", "decompilation", "reverse", "apk"],
            input_schema={
                "type": "object",
                "properties": {
                    "apk_path": {
                        "type": "string",
                        "description": "Path to the APK to decompile (absolute or relative to workspace)",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Directory (relative to workspace) where Jadx output should be written",
                        "default": "jadx_output",
                    },
                    "overwrite": {
                        "type": "boolean",
                        "description": "Overwrite existing output directory if present",
                        "default": True,
                    },
                    "threads": {
                        "type": "integer",
                        "description": "Number of Jadx decompilation threads",
                        "default": 4,
                        "minimum": 1,
                        "maximum": 32,
                    },
                    "decompiler_args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Additional arguments passed directly to Jadx",
                        "default": [],
                    },
                },
                "required": ["apk_path"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "output_dir": {
                        "type": "string",
                        "description": "Path to decompiled output directory",
                    },
                    "source_dir": {
                        "type": "string",
                        "description": "Path to decompiled Java sources",
                    },
                    "resource_dir": {
                        "type": "string",
                        "description": "Path to extracted resources",
                    },
                    "java_files": {
                        "type": "integer",
                        "description": "Number of Java files decompiled",
                    },
                },
            },
            requires_workspace=True,
        )

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate module configuration"""
        apk_path = config.get("apk_path")
        if not apk_path:
            raise ValueError("'apk_path' must be provided for Jadx decompilation")

        threads = config.get("threads", 4)
        if not isinstance(threads, int) or threads < 1 or threads > 32:
            raise ValueError("threads must be between 1 and 32")

        return True

    async def execute(self, config: Dict[str, Any], workspace: Path) -> ModuleResult:
        """
        Execute Jadx decompilation on an APK file.

        Args:
            config: Configuration dict with apk_path, output_dir, etc.
            workspace: Workspace directory path

        Returns:
            ModuleResult with decompilation summary and metadata
        """
        self.start_timer()

        try:
            self.validate_config(config)
            self.validate_workspace(workspace)

            workspace = workspace.resolve()

            # Resolve APK path
            apk_path = Path(config["apk_path"])
            if not apk_path.is_absolute():
                apk_path = (workspace / apk_path).resolve()

            if not apk_path.exists():
                raise ValueError(f"APK not found: {apk_path}")

            if apk_path.is_dir():
                raise ValueError(f"APK path must be a file, not a directory: {apk_path}")

            logger.info(f"Decompiling APK: {apk_path}")

            # Resolve output directory
            output_dir = Path(config.get("output_dir", "jadx_output"))
            if not output_dir.is_absolute():
                output_dir = (workspace / output_dir).resolve()

            # Handle existing output directory
            if output_dir.exists():
                if config.get("overwrite", True):
                    logger.info(f"Removing existing output directory: {output_dir}")
                    shutil.rmtree(output_dir)
                else:
                    raise ValueError(
                        f"Output directory already exists: {output_dir}. Set overwrite=true to replace it."
                    )

            output_dir.mkdir(parents=True, exist_ok=True)

            # Build Jadx command
            threads = str(config.get("threads", 4))
            extra_args = config.get("decompiler_args", []) or []

            cmd = [
                "jadx",
                "--threads-count",
                threads,
                "--deobf",  # Deobfuscate code
                "--output-dir",
                str(output_dir),
            ]
            cmd.extend(extra_args)
            cmd.append(str(apk_path))

            logger.info(f"Running Jadx: {' '.join(cmd)}")

            # Execute Jadx
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(workspace),
            )

            stdout, stderr = await process.communicate()
            stdout_str = stdout.decode(errors="ignore") if stdout else ""
            stderr_str = stderr.decode(errors="ignore") if stderr else ""

            if stdout_str:
                logger.debug(f"Jadx stdout: {stdout_str[:200]}...")
            if stderr_str:
                logger.debug(f"Jadx stderr: {stderr_str[:200]}...")

            if process.returncode != 0:
                error_output = stderr_str or stdout_str or "No error output"
                raise RuntimeError(
                    f"Jadx failed with exit code {process.returncode}: {error_output[:500]}"
                )

            # Verify output structure
            source_dir = output_dir / "sources"
            resource_dir = output_dir / "resources"

            if not source_dir.exists():
                logger.warning(
                    f"Jadx sources directory not found at expected path: {source_dir}"
                )
                # Use output_dir as fallback
                source_dir = output_dir

            # Count decompiled Java files
            java_files = 0
            if source_dir.exists():
                java_files = sum(1 for _ in source_dir.rglob("*.java"))
                logger.info(f"Decompiled {java_files} Java files")

                # Log sample files for debugging
                sample_files = []
                for idx, file_path in enumerate(source_dir.rglob("*.java")):
                    sample_files.append(str(file_path.relative_to(workspace)))
                    if idx >= 4:
                        break
                if sample_files:
                    logger.debug(f"Sample Java files: {sample_files}")

            # Create summary
            summary = {
                "output_dir": str(output_dir),
                "source_dir": str(source_dir if source_dir.exists() else output_dir),
                "resource_dir": str(
                    resource_dir if resource_dir.exists() else output_dir
                ),
                "java_files": java_files,
                "apk_name": apk_path.name,
                "apk_size_bytes": apk_path.stat().st_size,
            }

            metadata = {
                "apk_path": str(apk_path),
                "output_dir": str(output_dir),
                "source_dir": summary["source_dir"],
                "resource_dir": summary["resource_dir"],
                "threads": threads,
                "decompiler": "jadx",
                "decompiler_version": "1.5.0",
            }

            logger.info(
                f"✓ Jadx decompilation completed: {java_files} Java files generated"
            )

            return self.create_result(
                findings=[],  # Jadx doesn't generate findings, only decompiles
                status="success",
                summary=summary,
                metadata=metadata,
            )

        except Exception as exc:
            logger.error(f"Jadx decompilation failed: {exc}", exc_info=True)
            return self.create_result(
                findings=[],
                status="failed",
                error=str(exc),
                metadata={"decompiler": "jadx", "apk_path": config.get("apk_path")},
            )
