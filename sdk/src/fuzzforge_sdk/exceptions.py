"""
Enhanced exceptions for FuzzForge SDK with rich context.

Provides comprehensive error information and actionable suggestions for troubleshooting.
Note: Container diagnostics are not available in Temporal architecture as workflows
run in long-lived worker containers rather than ephemeral per-workflow containers.
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


import json
import re
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict


@dataclass
class ErrorContext:
    """Rich context information for errors."""
    url: Optional[str] = None
    request_method: Optional[str] = None
    request_data: Optional[Dict[str, Any]] = None
    response_data: Optional[Dict[str, Any]] = None
    suggested_fixes: List[str] = None
    error_patterns: Dict[str, List[str]] = None
    related_run_id: Optional[str] = None
    workflow_name: Optional[str] = None

    def __post_init__(self):
        if self.suggested_fixes is None:
            self.suggested_fixes = []
        if self.error_patterns is None:
            self.error_patterns = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


class FuzzForgeError(Exception):
    """Base exception for all FuzzForge SDK errors with rich context."""

    def __init__(
        self,
        message: str,
        context: Optional[ErrorContext] = None,
        original_exception: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.context = context or ErrorContext()
        self.original_exception = original_exception

    def get_summary(self) -> str:
        """Get a summary of the error with key details."""
        parts = [self.message]

        if self.context.error_patterns:
            detected = list(self.context.error_patterns.keys())
            parts.append(f"Detected issues: {', '.join(detected)}")

        return " | ".join(parts)

    def get_detailed_info(self) -> Dict[str, Any]:
        """Get detailed error information for rich display."""
        info = {
            "message": self.message,
            "type": self.__class__.__name__,
        }

        if self.context:
            info.update(self.context.to_dict())

        return info

    def __str__(self) -> str:
        return self.get_summary()


class FuzzForgeHTTPError(FuzzForgeError):
    """HTTP-related errors with enhanced context."""

    def __init__(
        self,
        message: str,
        status_code: int,
        response_text: Optional[str] = None,
        context: Optional[ErrorContext] = None,
        original_exception: Optional[Exception] = None
    ):
        if context is None:
            context = ErrorContext()

        # Parse response data if it's JSON
        if response_text:
            try:
                context.response_data = json.loads(response_text)
            except (json.JSONDecodeError, TypeError):
                context.response_data = {"raw": response_text}

        super().__init__(message, context, original_exception)
        self.status_code = status_code
        self.response_text = response_text

    def get_summary(self) -> str:
        return f"HTTP {self.status_code}: {self.message}"


class DeploymentError(FuzzForgeHTTPError):
    """Enhanced deployment errors."""

    def __init__(
        self,
        workflow_name: str,
        message: str,
        deployment_id: Optional[str] = None,
        container_name: Optional[str] = None,
        status_code: int = 500,
        response_text: Optional[str] = None,
        context: Optional[ErrorContext] = None
    ):
        if context is None:
            context = ErrorContext()

        context.workflow_name = workflow_name

        # Note: Container diagnostics are not fetched in Temporal architecture.
        # Workflows run in long-lived worker containers, not per-workflow containers.
        # The container_name parameter is kept for backward compatibility but not used.

        full_message = f"Deployment failed for workflow '{workflow_name}': {message}"
        super().__init__(full_message, status_code, response_text, context)
        self.workflow_name = workflow_name
        self.deployment_id = deployment_id


class WorkflowExecutionError(FuzzForgeHTTPError):
    """Enhanced workflow execution errors."""

    def __init__(
        self,
        workflow_name: str,
        run_id: str,
        message: str,
        status_code: int = 400,
        response_text: Optional[str] = None,
        context: Optional[ErrorContext] = None
    ):
        if context is None:
            context = ErrorContext()

        context.workflow_name = workflow_name
        context.related_run_id = run_id

        full_message = f"Workflow '{workflow_name}' execution failed (run: {run_id}): {message}"
        super().__init__(full_message, status_code, response_text, context)
        self.workflow_name = workflow_name
        self.run_id = run_id


class WorkflowNotFoundError(FuzzForgeHTTPError):
    """Enhanced workflow not found error."""

    def __init__(
        self,
        workflow_name: str,
        available_workflows: List[str] = None,
        context: Optional[ErrorContext] = None
    ):
        if context is None:
            context = ErrorContext()

        context.workflow_name = workflow_name

        if available_workflows:
            context.suggested_fixes = [
                f"Available workflows: {', '.join(available_workflows)}",
                "Use 'fuzzforge workflows list' to see all available workflows",
                "Check workflow name spelling and case sensitivity"
            ]

        message = f"Workflow not found: {workflow_name}"
        super().__init__(message, 404, context=context)
        self.workflow_name = workflow_name
        self.available_workflows = available_workflows or []


class RunNotFoundError(FuzzForgeHTTPError):
    """Enhanced run not found error."""

    def __init__(
        self,
        run_id: str,
        context: Optional[ErrorContext] = None
    ):
        if context is None:
            context = ErrorContext()

        context.related_run_id = run_id
        context.suggested_fixes = [
            "Use 'fuzzforge runs list' to see available runs",
            "Check if the run ID is correct and complete",
            "Ensure the run hasn't been deleted or expired"
        ]

        message = f"Run not found: {run_id}"
        super().__init__(message, 404, context=context)
        self.run_id = run_id


class ContainerError(FuzzForgeError):
    """Enhanced container-specific errors."""

    def __init__(
        self,
        container_name: str,
        message: str,
        exit_code: Optional[int] = None,
        context: Optional[ErrorContext] = None
    ):
        if context is None:
            context = ErrorContext()

        # Note: Container diagnostics are not fetched in Temporal architecture.
        # Workflows run in long-lived worker containers, not per-workflow containers.
        # The container_name parameter is kept for backward compatibility but not used.

        full_message = f"Container error ({container_name}): {message}"
        if exit_code is not None:
            full_message += f" (exit code: {exit_code})"

        super().__init__(full_message, context)
        self.container_name = container_name
        self.exit_code = exit_code


class VolumeError(FuzzForgeError):
    """Volume mount related errors."""

    def __init__(
        self,
        volume_path: str,
        message: str,
        context: Optional[ErrorContext] = None
    ):
        if context is None:
            context = ErrorContext()

        context.suggested_fixes = [
            "Check if the volume path exists and is accessible",
            "Verify file permissions (Docker needs read access)",
            "Ensure the path is not in use by another process",
            "Try using an absolute path instead of relative path",
            "Check if SELinux or AppArmor is blocking access"
        ]

        full_message = f"Volume error ({volume_path}): {message}"
        super().__init__(full_message, context)
        self.volume_path = volume_path


class ResourceLimitError(FuzzForgeError):
    """Resource limit related errors."""

    def __init__(
        self,
        resource_type: str,
        message: str,
        current_usage: Optional[Dict[str, Any]] = None,
        context: Optional[ErrorContext] = None
    ):
        if context is None:
            context = ErrorContext()

        context.suggested_fixes = [
            f"Increase {resource_type} limits in workflow configuration",
            "Check system resource availability",
            "Consider using a smaller dataset or batch size",
            "Monitor resource usage during execution"
        ]

        full_message = f"{resource_type.title()} limit error: {message}"
        super().__init__(full_message, context)
        self.resource_type = resource_type
        self.current_usage = current_usage or {}


class ValidationError(FuzzForgeError):
    """Enhanced data validation errors."""

    def __init__(
        self,
        field_name: str,
        message: str,
        provided_value: Any = None,
        expected_format: Optional[str] = None,
        context: Optional[ErrorContext] = None
    ):
        if context is None:
            context = ErrorContext()

        if expected_format:
            context.suggested_fixes = [
                f"Expected format: {expected_format}",
                f"Provided value: {provided_value}",
                "Check parameter documentation for valid values"
            ]

        full_message = f"Validation error for '{field_name}': {message}"
        super().__init__(full_message, context)
        self.field_name = field_name
        self.provided_value = provided_value
        self.expected_format = expected_format


class ConnectionError(FuzzForgeError):
    """Enhanced connection errors."""

    def __init__(
        self,
        endpoint: str,
        message: str,
        context: Optional[ErrorContext] = None
    ):
        if context is None:
            context = ErrorContext()

        context.suggested_fixes = [
            "Check if FuzzForge backend is running (docker-compose up -d)",
            "Verify the API endpoint URL is correct",
            "Check network connectivity and firewall settings",
            "Ensure all required services are healthy",
            "Try restarting the FuzzForge services"
        ]

        full_message = f"Connection error to {endpoint}: {message}"
        super().__init__(full_message, context)
        self.endpoint = endpoint


class TimeoutError(FuzzForgeError):
    """Enhanced timeout errors."""

    def __init__(
        self,
        operation: str,
        timeout_seconds: int,
        context: Optional[ErrorContext] = None
    ):
        if context is None:
            context = ErrorContext()

        context.suggested_fixes = [
            f"Increase timeout value (current: {timeout_seconds}s)",
            "Check if the operation is resource-intensive",
            "Verify backend services are responsive",
            "Consider breaking down large operations into smaller chunks"
        ]

        full_message = f"Timeout error for {operation} after {timeout_seconds} seconds"
        super().__init__(full_message, context)
        self.operation = operation
        self.timeout_seconds = timeout_seconds


class WebSocketError(FuzzForgeError):
    """WebSocket-related errors."""


class SSEError(FuzzForgeError):
    """Server-Sent Events related errors."""


def from_http_error(status_code: int, response_text: str, url: str) -> FuzzForgeHTTPError:
    """
    Create appropriate exception from HTTP error response with enhanced context.

    Args:
        status_code: HTTP status code
        response_text: Response body text
        url: Request URL that failed

    Returns:
        Appropriate FuzzForgeError subclass with rich context
    """
    context = ErrorContext(url=url, response_data={"raw": response_text})

    # Try to parse JSON response for more context
    try:
        response_data = json.loads(response_text)
        context.response_data = response_data

        # Extract additional context from structured error responses
        if isinstance(response_data, dict):
            if "run_id" in response_data:
                context.related_run_id = response_data["run_id"]
            if "workflow" in response_data:
                context.workflow_name = response_data["workflow"]

    except (json.JSONDecodeError, TypeError):
        # Unable to parse JSON, use raw text
        pass

    # Handle specific error types based on URL patterns and status codes
    if status_code == 404:
        if "/workflows/" in url and "/submit" not in url:
            # Extract workflow name from URL
            parts = url.split("/workflows/")
            if len(parts) > 1:
                workflow_name = parts[1].split("/")[0]
                return WorkflowNotFoundError(workflow_name, context=context)

        elif "/runs/" in url:
            # Extract run ID from URL
            parts = url.split("/runs/")
            if len(parts) > 1:
                run_id = parts[1].split("/")[0]
                return RunNotFoundError(run_id, context)

    elif status_code == 400:
        # Check for specific error patterns in response
        if "deployment" in response_text.lower() and "not found" in response_text.lower():
            # Extract workflow name if possible
            workflow_match = re.search(r"workflow['\"]?\s*[:\-]?\s*['\"]?(\w+)", response_text, re.IGNORECASE)
            workflow_name = workflow_match.group(1) if workflow_match else "unknown"

            return DeploymentError(
                workflow_name=workflow_name,
                message="Deployment not found",
                status_code=status_code,
                response_text=response_text,
                context=context
            )

        elif "volume" in response_text.lower() or "mount" in response_text.lower():
            return VolumeError(
                volume_path="unknown",
                message=response_text,
                context=context
            )

        elif "memory" in response_text.lower() or "resource" in response_text.lower():
            return ResourceLimitError(
                resource_type="memory",
                message=response_text,
                context=context
            )

    elif status_code == 500:
        # Server errors might be deployment or execution issues
        if "deployment" in response_text.lower() or "container" in response_text.lower():
            workflow_match = re.search(r"workflow['\"]?\s*[:\-]?\s*['\"]?(\w+)", response_text, re.IGNORECASE)
            workflow_name = workflow_match.group(1) if workflow_match else "unknown"

            return DeploymentError(
                workflow_name=workflow_name,
                message=response_text,
                status_code=status_code,
                response_text=response_text,
                context=context
            )

    # Generic HTTP error with enhanced context
    return FuzzForgeHTTPError(
        message=f"HTTP request failed: {response_text}",
        status_code=status_code,
        response_text=response_text,
        context=context
    )