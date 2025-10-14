#!/usr/bin/env python3
"""
Quick smoke test for SDK exception handling after exceptions.py modifications.
Tests that the modified _fetch_container_diagnostics() no-op doesn't break exception flows.
"""

import sys
from pathlib import Path

# Add SDK to path
sdk_path = Path(__file__).parent / "src"
sys.path.insert(0, str(sdk_path))

from fuzzforge_sdk.exceptions import (
    FuzzForgeError,
    FuzzForgeHTTPError,
    WorkflowNotFoundError,
    RunNotFoundError,
    ErrorContext,
    DeploymentError,
    WorkflowExecutionError,
    ValidationError,
)


def test_basic_import():
    """Test that all exception classes can be imported."""
    print("✓ All exception classes imported successfully")


def test_error_context():
    """Test ErrorContext instantiation."""
    context = ErrorContext(
        url="http://localhost:8000/test",
        related_run_id="test-run-123",
        workflow_name="test_workflow"
    )
    assert context.url == "http://localhost:8000/test"
    assert context.related_run_id == "test-run-123"
    assert context.workflow_name == "test_workflow"
    print("✓ ErrorContext instantiation works")


def test_base_exception():
    """Test base FuzzForgeError."""
    context = ErrorContext(related_run_id="test-run-456")

    error = FuzzForgeError("Test error message", context=context)

    assert error.message == "Test error message"
    assert error.context.related_run_id == "test-run-456"
    print("✓ FuzzForgeError creation works")


def test_http_error():
    """Test HTTP error creation."""
    error = FuzzForgeHTTPError(
        message="Test HTTP error",
        status_code=500,
        response_text='{"error": "Internal server error"}'
    )

    assert error.status_code == 500
    assert error.message == "Test HTTP error"
    assert error.context.response_data == {"error": "Internal server error"}
    print("✓ FuzzForgeHTTPError creation works")


def test_workflow_not_found():
    """Test WorkflowNotFoundError with suggestions."""
    error = WorkflowNotFoundError(
        workflow_name="nonexistent_workflow",
        available_workflows=["security_assessment", "secret_detection"]
    )

    assert error.workflow_name == "nonexistent_workflow"
    assert len(error.context.suggested_fixes) > 0
    print("✓ WorkflowNotFoundError with suggestions works")


def test_run_not_found():
    """Test RunNotFoundError."""
    error = RunNotFoundError(run_id="missing-run-123")

    assert error.run_id == "missing-run-123"
    assert error.context.related_run_id == "missing-run-123"
    assert len(error.context.suggested_fixes) > 0
    print("✓ RunNotFoundError creation works")


def test_deployment_error():
    """Test DeploymentError."""
    error = DeploymentError(
        workflow_name="test_workflow",
        message="Deployment failed",
        deployment_id="deploy-123",
        container_name="test-container-456"  # Kept for backward compatibility
    )

    assert error.workflow_name == "test_workflow"
    assert error.deployment_id == "deploy-123"
    print("✓ DeploymentError creation works")


def test_workflow_execution_error():
    """Test WorkflowExecutionError."""
    error = WorkflowExecutionError(
        workflow_name="security_assessment",
        run_id="run-789",
        message="Execution timeout"
    )

    assert error.workflow_name == "security_assessment"
    assert error.run_id == "run-789"
    assert error.context.related_run_id == "run-789"
    print("✓ WorkflowExecutionError creation works")


def test_validation_error():
    """Test ValidationError."""
    error = ValidationError(
        field_name="target_path",
        message="Path does not exist",
        provided_value="/nonexistent/path",
        expected_format="Valid directory path"
    )

    assert error.field_name == "target_path"
    assert error.provided_value == "/nonexistent/path"
    assert len(error.context.suggested_fixes) > 0
    print("✓ ValidationError with suggestions works")


def test_exception_string_representation():
    """Test exception summary and string conversion."""
    error = FuzzForgeHTTPError(
        message="Test error",
        status_code=404,
        response_text="Not found"
    )

    summary = error.get_summary()
    assert "404" in summary
    assert "Test error" in summary

    str_repr = str(error)
    assert str_repr == summary
    print("✓ Exception string representation works")


def test_exception_detailed_info():
    """Test detailed error information."""
    context = ErrorContext(
        url="http://localhost:8000/test",
        workflow_name="test_workflow"
    )
    error = FuzzForgeError("Test error", context=context)

    info = error.get_detailed_info()
    assert info["message"] == "Test error"
    assert info["type"] == "FuzzForgeError"
    assert info["url"] == "http://localhost:8000/test"
    assert info["workflow_name"] == "test_workflow"
    print("✓ Exception detailed info works")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("SDK Exception Handling Smoke Tests")
    print("="*60 + "\n")

    tests = [
        test_basic_import,
        test_error_context,
        test_base_exception,
        test_http_error,
        test_workflow_not_found,
        test_run_not_found,
        test_deployment_error,
        test_workflow_execution_error,
        test_validation_error,
        test_exception_string_representation,
        test_exception_detailed_info,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"✗ {test_func.__name__} FAILED: {e}")
            failed += 1

    print("\n" + "="*60)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*60 + "\n")

    if failed > 0:
        print("❌ SDK exception handling has issues")
        return 1
    else:
        print("✅ SDK exception handling works correctly")
        print("✅ The no-op _fetch_container_diagnostics() doesn't break exception flows")
        return 0


if __name__ == "__main__":
    sys.exit(main())
