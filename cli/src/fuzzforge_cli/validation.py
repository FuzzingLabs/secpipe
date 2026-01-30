"""
Input validation utilities for FuzzForge CLI.
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


import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .constants import SUPPORTED_EXPORT_FORMATS
from .exceptions import ValidationError


def validate_run_id(run_id: str) -> None:
    """Validate a run/execution ID format"""
    if not run_id or not isinstance(run_id, str):
        raise ValidationError("run_id", run_id, "a non-empty string")

    # Check for reasonable length (UUIDs are typically 36 chars)
    if len(run_id) < 8 or len(run_id) > 128:
        raise ValidationError("run_id", run_id, "between 8 and 128 characters")

    # Check for valid characters (alphanumeric, hyphens, underscores)
    if not re.match(r'^[a-zA-Z0-9_-]+$', run_id):
        raise ValidationError("run_id", run_id, "alphanumeric characters, hyphens, and underscores only")


def validate_workflow_name(workflow: str) -> None:
    """Validate workflow name format"""
    if not workflow or not isinstance(workflow, str):
        raise ValidationError("workflow_name", workflow, "a non-empty string")

    # Check for reasonable length
    if len(workflow) < 2 or len(workflow) > 64:
        raise ValidationError("workflow_name", workflow, "between 2 and 64 characters")

    # Check for valid characters (alphanumeric, hyphens, underscores)
    if not re.match(r'^[a-zA-Z0-9_-]+$', workflow):
        raise ValidationError("workflow_name", workflow, "alphanumeric characters, hyphens, and underscores only")


def validate_target_path(target_path: str, must_exist: bool = True) -> Path:
    """Validate and normalize a target path"""
    if not target_path or not isinstance(target_path, str):
        raise ValidationError("target_path", target_path, "a non-empty string")

    try:
        path = Path(target_path).resolve()
    except Exception as e:
        raise ValidationError("target_path", target_path, f"a valid path: {e}")

    if must_exist and not path.exists():
        raise ValidationError("target_path", target_path, "an existing path")

    return path


def validate_export_format(export_format: str) -> None:
    """Validate export format"""
    if export_format not in SUPPORTED_EXPORT_FORMATS:
        raise ValidationError(
            "export_format", export_format,
            f"one of: {', '.join(SUPPORTED_EXPORT_FORMATS)}"
        )


def validate_parameter_value(key: str, value: str, param_type: str) -> Any:
    """Validate and convert a parameter value based on its type"""
    if param_type == "integer":
        try:
            return int(value)
        except ValueError:
            raise ValidationError(f"parameter '{key}'", value, "an integer")

    elif param_type == "number":
        try:
            return float(value)
        except ValueError:
            raise ValidationError(f"parameter '{key}'", value, "a number")

    elif param_type == "boolean":
        lower_value = value.lower()
        if lower_value in ("true", "yes", "1", "on"):
            return True
        elif lower_value in ("false", "no", "0", "off"):
            return False
        else:
            raise ValidationError(f"parameter '{key}'", value, "a boolean (true/false, yes/no, 1/0, on/off)")

    elif param_type == "array":
        # Split by comma and strip whitespace
        items = [item.strip() for item in value.split(",") if item.strip()]
        if not items:
            raise ValidationError(f"parameter '{key}'", value, "a non-empty comma-separated list")
        return items

    else:
        # String type - basic validation
        if not value:
            raise ValidationError(f"parameter '{key}'", value, "a non-empty string")
        return value


def validate_parameters(params: List[str]) -> Dict[str, Any]:
    """Validate and parse parameter list"""
    parameters = {}

    for param_str in params:
        if "=" not in param_str:
            raise ValidationError("parameter format", param_str, "key=value format")

        key, value = param_str.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not key:
            raise ValidationError("parameter key", param_str, "a non-empty key")

        if not value:
            raise ValidationError(f"parameter '{key}'", param_str, "a non-empty value")

        # Auto-detect type and convert
        try:
            if value.lower() in ("true", "false"):
                parameters[key] = value.lower() == "true"
            elif value.isdigit():
                parameters[key] = int(value)
            elif re.match(r'^\d+\.\d+$', value):
                parameters[key] = float(value)
            else:
                parameters[key] = value
        except ValueError:
            parameters[key] = value

    return parameters


def validate_config_key(key: str) -> None:
    """Validate configuration key format"""
    if not key or not isinstance(key, str):
        raise ValidationError("config_key", key, "a non-empty string")

    # Check for valid key format (e.g., "api.url", "timeout")
    if not re.match(r'^[a-zA-Z0-9._-]+$', key):
        raise ValidationError("config_key", key, "alphanumeric characters, dots, hyphens, and underscores only")


def validate_positive_integer(value: int, name: str) -> None:
    """Validate that a value is a positive integer"""
    if not isinstance(value, int) or value <= 0:
        raise ValidationError(name, value, "a positive integer")


def validate_timeout(timeout: Optional[int]) -> None:
    """Validate timeout value"""
    if timeout is not None:
        if not isinstance(timeout, int) or timeout <= 0:
            raise ValidationError("timeout", timeout, "a positive integer (seconds)")

        if timeout > 86400:  # 24 hours
            raise ValidationError("timeout", timeout, "less than 24 hours (86400 seconds)")