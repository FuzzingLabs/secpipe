"""FuzzForge Runner exceptions."""

from __future__ import annotations


class RunnerError(Exception):
    """Base exception for all Runner errors."""


class ModuleNotFoundError(RunnerError):
    """Raised when a module cannot be found."""


class ModuleExecutionError(RunnerError):
    """Raised when module execution fails."""


class WorkflowExecutionError(RunnerError):
    """Raised when workflow execution fails."""


class StorageError(RunnerError):
    """Raised when storage operations fail."""


class SandboxError(RunnerError):
    """Raised when sandbox operations fail."""
