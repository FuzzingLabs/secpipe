"""
API response validation and graceful degradation utilities.
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
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ValidationError as PydanticValidationError

from .exceptions import ValidationError

logger = logging.getLogger(__name__)


class WorkflowMetadata(BaseModel):
    """Expected workflow metadata structure"""
    name: str
    version: str
    author: Optional[str] = None
    description: Optional[str] = None
    parameters: Dict[str, Any] = {}


class RunStatus(BaseModel):
    """Expected run status structure"""
    run_id: str
    workflow: str
    status: str
    created_at: str
    updated_at: str

    @property
    def is_completed(self) -> bool:
        """Check if run is in a completed state"""
        return self.status.lower() in ["completed", "success", "finished"]

    @property
    def is_running(self) -> bool:
        """Check if run is currently running"""
        return self.status.lower() in ["running", "in_progress", "active"]

    @property
    def is_failed(self) -> bool:
        """Check if run has failed"""
        return self.status.lower() in ["failed", "error", "cancelled"]


class FindingsResponse(BaseModel):
    """Expected findings response structure"""
    run_id: str
    sarif: Dict[str, Any]
    total_issues: Optional[int] = None

    def model_post_init(self, __context: Any) -> None:
        """Validate SARIF structure after initialization"""
        if not self.sarif.get("runs"):
            logger.warning(f"SARIF data for run {self.run_id} missing 'runs' section")
        elif not isinstance(self.sarif["runs"], list):
            logger.warning(f"SARIF 'runs' section is not a list for run {self.run_id}")


def validate_api_response(response_data: Any, expected_model: type[BaseModel],
                         operation: str = "API operation") -> BaseModel:
    """
    Validate API response against expected Pydantic model.

    Args:
        response_data: Raw response data from API
        expected_model: Pydantic model class to validate against
        operation: Description of the operation for error messages

    Returns:
        Validated model instance

    Raises:
        ValidationError: If validation fails
    """
    try:
        return expected_model.model_validate(response_data)
    except PydanticValidationError as e:
        logger.error(f"API response validation failed for {operation}: {e}")
        raise ValidationError(
            f"API response for {operation}",
            str(response_data)[:200] + "..." if len(str(response_data)) > 200 else str(response_data),
            f"valid {expected_model.__name__} format"
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error validating API response for {operation}: {e}")
        raise ValidationError(
            f"API response for {operation}",
            "invalid data",
            f"valid {expected_model.__name__} format"
        ) from e


def validate_sarif_structure(sarif_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Validate basic SARIF structure and return validation issues.

    Args:
        sarif_data: SARIF data dictionary

    Returns:
        Dictionary of validation issues found
    """
    issues = {}

    # Check basic SARIF structure
    if not isinstance(sarif_data, dict):
        issues["structure"] = "SARIF data is not a dictionary"
        return issues

    if "runs" not in sarif_data:
        issues["runs"] = "Missing 'runs' section in SARIF data"
    elif not isinstance(sarif_data["runs"], list):
        issues["runs_type"] = "'runs' section is not a list"
    elif len(sarif_data["runs"]) == 0:
        issues["runs_empty"] = "'runs' section is empty"
    else:
        # Check first run structure
        run = sarif_data["runs"][0]
        if not isinstance(run, dict):
            issues["run_structure"] = "First run is not a dictionary"
        else:
            if "results" not in run:
                issues["results"] = "Missing 'results' section in run"
            elif not isinstance(run["results"], list):
                issues["results_type"] = "'results' section is not a list"

            if "tool" not in run:
                issues["tool"] = "Missing 'tool' section in run"
            elif not isinstance(run["tool"], dict):
                issues["tool_type"] = "'tool' section is not a dictionary"

    return issues


def safe_extract_sarif_summary(sarif_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Safely extract summary information from SARIF data with fallbacks.

    Args:
        sarif_data: SARIF data dictionary

    Returns:
        Summary dictionary with safe defaults
    """
    summary = {
        "total_issues": 0,
        "by_severity": {},
        "by_rule": {},
        "tools": [],
        "validation_issues": []
    }

    # Validate structure first
    validation_issues = validate_sarif_structure(sarif_data)
    if validation_issues:
        summary["validation_issues"] = list(validation_issues.values())
        logger.warning(f"SARIF validation issues: {validation_issues}")

    try:
        runs = sarif_data.get("runs", [])
        if not runs:
            return summary

        run = runs[0]
        results = run.get("results", [])

        summary["total_issues"] = len(results)

        # Count by severity/level
        for result in results:
            try:
                level = result.get("level", "note")
                rule_id = result.get("ruleId", "unknown")

                summary["by_severity"][level] = summary["by_severity"].get(level, 0) + 1
                summary["by_rule"][rule_id] = summary["by_rule"].get(rule_id, 0) + 1
            except Exception as e:
                logger.warning(f"Failed to process result: {e}")
                continue

        # Extract tool information safely
        try:
            tool = run.get("tool", {})
            driver = tool.get("driver", {})
            if driver.get("name"):
                summary["tools"].append({
                    "name": driver.get("name", "unknown"),
                    "version": driver.get("version", "unknown"),
                    "rules": len(driver.get("rules", []))
                })
        except Exception as e:
            logger.warning(f"Failed to extract tool information: {e}")

    except Exception as e:
        logger.error(f"Failed to extract SARIF summary: {e}")
        summary["validation_issues"].append(f"Summary extraction failed: {e}")

    return summary


def validate_workflow_parameters(parameters: Dict[str, Any],
                                workflow_schema: Dict[str, Any]) -> List[str]:
    """
    Validate workflow parameters against schema with detailed error messages.

    Args:
        parameters: Parameters to validate
        workflow_schema: JSON schema for the workflow

    Returns:
        List of validation error messages
    """
    errors = []

    try:
        properties = workflow_schema.get("properties", {})
        required = set(workflow_schema.get("required", []))

        # Check required parameters
        missing_required = required - set(parameters.keys())
        if missing_required:
            errors.append(f"Missing required parameters: {', '.join(missing_required)}")

        # Validate individual parameters
        for param_name, param_value in parameters.items():
            if param_name not in properties:
                errors.append(f"Unknown parameter: {param_name}")
                continue

            param_schema = properties[param_name]
            param_type = param_schema.get("type", "string")

            # Type validation
            if param_type == "integer" and not isinstance(param_value, int):
                errors.append(f"Parameter '{param_name}' must be an integer")
            elif param_type == "number" and not isinstance(param_value, (int, float)):
                errors.append(f"Parameter '{param_name}' must be a number")
            elif param_type == "boolean" and not isinstance(param_value, bool):
                errors.append(f"Parameter '{param_name}' must be a boolean")
            elif param_type == "array" and not isinstance(param_value, list):
                errors.append(f"Parameter '{param_name}' must be an array")

            # Range validation for numbers
            if param_type in ["integer", "number"] and isinstance(param_value, (int, float)):
                minimum = param_schema.get("minimum")
                maximum = param_schema.get("maximum")

                if minimum is not None and param_value < minimum:
                    errors.append(f"Parameter '{param_name}' must be >= {minimum}")
                if maximum is not None and param_value > maximum:
                    errors.append(f"Parameter '{param_name}' must be <= {maximum}")

    except Exception as e:
        logger.error(f"Parameter validation failed: {e}")
        errors.append(f"Parameter validation error: {e}")

    return errors


def create_fallback_response(response_type: str, **kwargs) -> Dict[str, Any]:
    """
    Create fallback responses when API calls fail.

    Args:
        response_type: Type of response to create
        **kwargs: Additional data for the fallback

    Returns:
        Fallback response dictionary
    """
    fallbacks = {
        "workflow_list": {
            "workflows": [],
            "message": "Unable to fetch workflows from API"
        },
        "run_status": {
            "run_id": kwargs.get("run_id", "unknown"),
            "workflow": kwargs.get("workflow", "unknown"),
            "status": "unknown",
            "created_at": kwargs.get("created_at", "unknown"),
            "updated_at": kwargs.get("updated_at", "unknown"),
            "message": "Unable to fetch run status from API"
        },
        "findings": {
            "run_id": kwargs.get("run_id", "unknown"),
            "sarif": {
                "version": "2.1.0",
                "runs": []
            },
            "message": "Unable to fetch findings from API"
        }
    }

    fallback = fallbacks.get(response_type, {"message": f"No fallback available for {response_type}"})
    logger.info(f"Using fallback response for {response_type}: {fallback.get('message', 'Unknown fallback')}")

    return fallback