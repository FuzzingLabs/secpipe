"""Utilities for collecting files to ingest into Cognee."""
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


from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Iterable, List, Optional

_DEFAULT_FILE_TYPES = [
    ".py",
    ".js",
    ".ts",
    ".java",
    ".cpp",
    ".c",
    ".h",
    ".rs",
    ".go",
    ".rb",
    ".php",
    ".cs",
    ".swift",
    ".kt",
    ".scala",
    ".clj",
    ".hs",
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".cfg",
    ".ini",
]

_DEFAULT_EXCLUDE = [
    "*.pyc",
    "__pycache__",
    ".git",
    ".svn",
    ".hg",
    "node_modules",
    ".venv",
    "venv",
    ".env",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    "coverage",
    "*.log",
    "*.tmp",
]


def collect_ingest_files(
    path: Path,
    recursive: bool = True,
    file_types: Optional[Iterable[str]] = None,
    exclude: Optional[Iterable[str]] = None,
) -> List[Path]:
    """Return a list of files eligible for ingestion."""
    path = path.resolve()
    files: List[Path] = []

    extensions = list(file_types) if file_types else list(_DEFAULT_FILE_TYPES)
    exclusions = list(exclude) if exclude else []
    exclusions.extend(_DEFAULT_EXCLUDE)

    def should_exclude(file_path: Path) -> bool:
        file_str = str(file_path)
        for pattern in exclusions:
            if fnmatch.fnmatch(file_str, f"*{pattern}*") or fnmatch.fnmatch(file_path.name, pattern):
                return True
        return False

    if path.is_file():
        if not should_exclude(path) and any(str(path).endswith(ext) for ext in extensions):
            files.append(path)
        return files

    pattern = "**/*" if recursive else "*"
    for file_path in path.glob(pattern):
        if file_path.is_file() and not should_exclude(file_path):
            if any(str(file_path).endswith(ext) for ext in extensions):
                files.append(file_path)

    return files


__all__ = ["collect_ingest_files"]
