"""
Automated testing utilities for FuzzForge workflows.

This module provides high-level testing capabilities for validating
workflow functionality, performance, and expected results.
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


import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

from .client import FuzzForgeClient
from .utils import validate_absolute_path, create_workflow_submission
from .exceptions import ValidationError

logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Result of a single workflow test."""
    workflow_name: str
    test_project_path: str
    passed: bool
    run_id: Optional[str] = None
    findings_count: int = 0
    execution_time: float = 0.0
    error: Optional[str] = None
    expected_min_findings: int = 0
    details: Dict[str, Any] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


@dataclass
class TestSummary:
    """Summary of multiple workflow tests."""
    total: int
    passed: int
    failed: int
    tests: List[TestResult]
    start_time: datetime
    end_time: Optional[datetime] = None
    total_duration: float = 0.0

    @property
    def failed_tests(self) -> List[TestResult]:
        """Get list of failed tests."""
        return [test for test in self.tests if not test.passed]

    @property
    def success_rate(self) -> float:
        """Get success rate as percentage."""
        if self.total == 0:
            return 0.0
        return (self.passed / self.total) * 100


# Default test configurations for each workflow
DEFAULT_TEST_CONFIG = {
    "static_analysis_scan": {
        "test_project": "static_analysis_vulnerable",
        "expected_min_findings": 3,  # Expect at least 3 findings
        "timeout": 300,  # 5 minutes
        "description": "Tests OpenGrep and Bandit static analysis tools"
    },
    "secret_detection_scan": {
        "test_project": "secret_detection_vulnerable",
        "expected_min_findings": 5,  # Expect at least 5 secrets
        "timeout": 180,  # 3 minutes
        "description": "Tests TruffleHog and Gitleaks secret detection"
    },
    "infrastructure_scan": {
        "test_project": "infrastructure_vulnerable",
        "expected_min_findings": 8,  # Expect at least 8 IaC issues
        "timeout": 240,  # 4 minutes
        "description": "Tests Checkov, Hadolint, and other IaC security tools"
    },
    "penetration_testing_scan": {
        "test_project": "penetration_testing_vulnerable",
        "expected_min_findings": 4,  # Expect at least 4 vulnerabilities
        "timeout": 420,  # 7 minutes (needs time to start services)
        "description": "Tests Nuclei penetration testing tools"
    },
    "security_assessment": {
        "test_project": "security_assessment_comprehensive",
        "expected_min_findings": 10,  # Expect at least 10 mixed findings
        "timeout": 600,  # 10 minutes (comprehensive scan)
        "description": "Comprehensive security assessment across all categories"
    }
}


class WorkflowTester:
    """
    High-level testing utilities for FuzzForge workflows.

    This class provides methods to easily test individual workflows or
    run comprehensive test suites against all available workflows.
    """

    def __init__(self, client: FuzzForgeClient, test_projects_base_path: Optional[str] = None):
        """
        Initialize the workflow tester.

        Args:
            client: FuzzForge client instance
            test_projects_base_path: Base path to test projects directory
        """
        self.client = client
        self.test_projects_base_path = test_projects_base_path

        if not test_projects_base_path:
            # Try to auto-detect test projects path
            current_dir = Path.cwd()
            candidates = [
                current_dir / "test_projects",
                current_dir.parent / "test_projects",
                current_dir / ".." / "test_projects",
                Path("/app/test_projects"),  # Inside Docker container (last resort)
            ]

            for candidate in candidates:
                if candidate.exists() and candidate.is_dir():
                    self.test_projects_base_path = str(candidate.resolve())
                    logger.info(f"Auto-detected test projects at: {self.test_projects_base_path}")
                    break

            if not self.test_projects_base_path:
                logger.warning("Could not auto-detect test projects path. Please specify explicitly.")
                self.test_projects_base_path = str(current_dir / "test_projects")

    def test_workflow(
        self,
        workflow_name: str,
        test_project_path: Optional[str] = None,
        expected_min_findings: Optional[int] = None,
        timeout: int = 300,
        **workflow_params
    ) -> TestResult:
        """
        Test a single workflow against a test project.

        Args:
            workflow_name: Name of the workflow to test
            test_project_path: Path to test project (or relative to base path)
            expected_min_findings: Minimum expected findings for test to pass
            timeout: Timeout in seconds
            **workflow_params: Additional workflow parameters

        Returns:
            TestResult with test outcome and details
        """
        start_time = time.time()

        try:
            # Get test configuration
            config = DEFAULT_TEST_CONFIG.get(workflow_name, {})
            if expected_min_findings is None:
                expected_min_findings = config.get("expected_min_findings", 0)
            if timeout == 300:  # Use config timeout if default
                timeout = config.get("timeout", 300)

            # Resolve test project path
            if test_project_path is None:
                test_project_name = config.get("test_project")
                if not test_project_name:
                    raise ValidationError(f"No test project configured for workflow: {workflow_name}")
                test_project_path = str(Path(self.test_projects_base_path) / test_project_name)
            elif not Path(test_project_path).is_absolute():
                test_project_path = str(Path(self.test_projects_base_path) / test_project_path)

            # Validate path exists
            test_path = validate_absolute_path(test_project_path)

            logger.info(f"Testing workflow '{workflow_name}' with project: {test_path}")

            # Create workflow submission
            submission = create_workflow_submission(
                **workflow_params
            )

            # Submit workflow
            response = self.client.submit_workflow(workflow_name, submission)
            run_id = response.run_id

            logger.info(f"Workflow submitted with run_id: {run_id}")

            # Wait for completion
            final_status = self.client.wait_for_completion(
                run_id=run_id,
                timeout=timeout,
                poll_interval=5
            )

            # Get findings
            findings = self.client.get_run_findings(run_id)
            findings_count = 0

            # Count findings from SARIF data if available
            if hasattr(findings, 'sarif') and findings.sarif:
                findings_count = findings.sarif.get('total_findings', 0)

            execution_time = time.time() - start_time

            # Determine if test passed
            passed = (
                final_status.is_completed and
                not final_status.is_failed and
                findings_count >= expected_min_findings
            )

            result = TestResult(
                workflow_name=workflow_name,
                test_project_path=test_project_path,
                passed=passed,
                run_id=run_id,
                findings_count=findings_count,
                execution_time=execution_time,
                expected_min_findings=expected_min_findings,
                details={
                    "status": final_status.status,
                    "sarif_summary": getattr(findings, 'sarif', {}),
                    "config_used": config.get("description", ""),
                    "timeout_used": timeout
                }
            )

            if not passed:
                if final_status.is_failed:
                    result.error = f"Workflow execution failed with status: {final_status.status}"
                elif findings_count < expected_min_findings:
                    result.error = f"Found {findings_count} findings, expected at least {expected_min_findings}"

            logger.info(f"Test {'PASSED' if passed else 'FAILED'}: {workflow_name}")
            return result

        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Test execution failed: {str(e)}"
            logger.error(error_msg)

            return TestResult(
                workflow_name=workflow_name,
                test_project_path=test_project_path or "unknown",
                passed=False,
                execution_time=execution_time,
                expected_min_findings=expected_min_findings or 0,
                error=error_msg
            )

    def test_all_workflows(
        self,
        workflows: Optional[List[str]] = None,
        parallel: bool = False
    ) -> TestSummary:
        """
        Test all available workflows.

        Args:
            workflows: List of specific workflows to test (defaults to all available)
            parallel: Whether to run tests in parallel (not yet implemented)

        Returns:
            TestSummary with results from all tests
        """
        start_time = datetime.now()

        try:
            # Get available workflows if not specified
            if workflows is None:
                workflow_list = self.client.list_workflows()
                workflows = [w.name for w in workflow_list]
                logger.info(f"Testing {len(workflows)} workflows: {', '.join(workflows)}")

            results = []

            # Test each workflow
            for workflow_name in workflows:
                logger.info(f"Testing workflow: {workflow_name}")
                result = self.test_workflow(workflow_name)
                results.append(result)

            end_time = datetime.now()
            total_duration = (end_time - start_time).total_seconds()

            passed = len([r for r in results if r.passed])
            failed = len(results) - passed

            summary = TestSummary(
                total=len(results),
                passed=passed,
                failed=failed,
                tests=results,
                start_time=start_time,
                end_time=end_time,
                total_duration=total_duration
            )

            logger.info(f"Testing complete: {passed}/{len(results)} workflows passed")
            return summary

        except Exception as e:
            logger.error(f"Test suite execution failed: {e}")
            end_time = datetime.now()
            return TestSummary(
                total=0,
                passed=0,
                failed=1,
                tests=[],
                start_time=start_time,
                end_time=end_time,
                total_duration=(end_time - start_time).total_seconds()
            )

    def validate_workflow_deployment(self, workflow_name: str) -> bool:
        """
        Validate that a workflow is properly deployed and available.

        Args:
            workflow_name: Name of the workflow to validate

        Returns:
            True if workflow is available, False otherwise
        """
        try:
            workflows = self.client.list_workflows()
            available_workflows = [w.name for w in workflows]
            return workflow_name in available_workflows
        except Exception as e:
            logger.error(f"Failed to validate workflow deployment: {e}")
            return False

    def get_test_project_path(self, project_name: str) -> str:
        """
        Get the full path to a test project.

        Args:
            project_name: Name of the test project

        Returns:
            Full path to the test project
        """
        return str(Path(self.test_projects_base_path) / project_name)


def format_test_summary(summary: TestSummary, detailed: bool = False) -> str:
    """
    Format a test summary for display.

    Args:
        summary: Test summary to format
        detailed: Whether to include detailed results

    Returns:
        Formatted string representation
    """
    lines = []

    # Header
    lines.append("=" * 60)
    lines.append("FuzzForge Workflow Test Results")
    lines.append("=" * 60)

    # Summary stats
    lines.append(f"Total Tests: {summary.total}")
    lines.append(f"Passed: {summary.passed} ✅")
    lines.append(f"Failed: {summary.failed} ❌")
    lines.append(f"Success Rate: {summary.success_rate:.1f}%")
    lines.append(f"Total Duration: {summary.total_duration:.1f}s")
    lines.append("")

    if detailed and summary.tests:
        lines.append("Detailed Results:")
        lines.append("-" * 40)

        for test in summary.tests:
            status_icon = "✅" if test.passed else "❌"
            lines.append(f"{status_icon} {test.workflow_name}")
            lines.append(f"   Project: {Path(test.test_project_path).name}")
            lines.append(f"   Findings: {test.findings_count} (expected ≥{test.expected_min_findings})")
            lines.append(f"   Duration: {test.execution_time:.1f}s")

            if test.error:
                lines.append(f"   Error: {test.error}")
            lines.append("")

    # Failed tests summary
    if summary.failed_tests:
        lines.append("Failed Tests:")
        lines.append("-" * 40)
        for test in summary.failed_tests:
            lines.append(f"❌ {test.workflow_name}: {test.error or 'Unknown error'}")
        lines.append("")

    return "\n".join(lines)