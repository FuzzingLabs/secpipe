#!/usr/bin/env python3
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

"""
Automated workflow testing example using FuzzForge SDK.

This example demonstrates how to:
1. Use the WorkflowTester for automated testing
2. Test all workflows against vulnerable test projects
3. Generate comprehensive test reports
4. Handle test failures and debugging

Usage:
    python test_all_workflows.py [--detailed] [--workflow WORKFLOW_NAME]
"""

import sys
import argparse
import logging
from pathlib import Path

from fuzzforge_sdk import (
    FuzzForgeClient,
    WorkflowTester,
    format_test_summary,
    DEFAULT_TEST_CONFIG
)
from fuzzforge_sdk.exceptions import FuzzForgeError


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )


def main():
    """Main test execution function."""
    parser = argparse.ArgumentParser(
        description="Automated workflow testing for FuzzForge",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test all workflows with detailed output
  python test_all_workflows.py --detailed

  # Test only static analysis workflow
  python test_all_workflows.py --workflow static_analysis_scan

  # Test with verbose logging
  python test_all_workflows.py --verbose --detailed

  # Show available test configurations
  python test_all_workflows.py --show-config
        """
    )

    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="FuzzForge API base URL (default: http://localhost:8000)"
    )

    parser.add_argument(
        "--test-projects-path",
        help="Path to test projects directory (auto-detected if not provided)"
    )

    parser.add_argument(
        "--workflow",
        help="Test only specific workflow"
    )

    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed test results"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Show test configurations and exit"
    )

    parser.add_argument(
        "--timeout",
        type=int,
        help="Override default timeout for workflow tests (seconds)"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    # Show configuration and exit if requested
    if args.show_config:
        print("🔧 FuzzForge Workflow Test Configurations:")
        print("=" * 60)
        for workflow_name, config in DEFAULT_TEST_CONFIG.items():
            print(f"📋 {workflow_name}:")
            print(f"   Test Project: {config['test_project']}")
            print(f"   Expected Findings: ≥{config['expected_min_findings']}")
            print(f"   Timeout: {config['timeout']}s")
            print(f"   Description: {config['description']}")
            print()
        return

    try:
        # Initialize client and tester
        print(f"🔗 Connecting to FuzzForge API at {args.base_url}")
        client = FuzzForgeClient(base_url=args.base_url)

        # Verify API connection
        status = client.get_api_status()
        print(f"✅ Connected to {status.name} v{status.version}")

        # Initialize tester
        tester = WorkflowTester(
            client=client,
            test_projects_base_path=args.test_projects_path
        )

        # Check if test projects path was found
        if not Path(tester.test_projects_base_path).exists():
            print(f"❌ Test projects path not found: {tester.test_projects_base_path}")
            print("Please ensure test projects are available or specify --test-projects-path")
            sys.exit(1)

        print(f"📁 Using test projects from: {tester.test_projects_base_path}")
        print()

        # Run tests
        if args.workflow:
            # Test single workflow
            print(f"🧪 Testing workflow: {args.workflow}")
            print("-" * 40)

            # Override timeout if specified
            kwargs = {}
            if args.timeout:
                kwargs['timeout'] = args.timeout

            result = tester.test_workflow(args.workflow, **kwargs)

            # Display result
            status_icon = "✅" if result.passed else "❌"
            print(f"{status_icon} {result.workflow_name}")
            print(f"   Project: {Path(result.test_project_path).name}")
            print(f"   Findings: {result.findings_count} (expected ≥{result.expected_min_findings})")
            print(f"   Duration: {result.execution_time:.1f}s")

            if result.error:
                print(f"   ❌ Error: {result.error}")

            if result.run_id:
                print(f"   🔍 Run ID: {result.run_id}")

            print()

            # Exit with appropriate code
            sys.exit(0 if result.passed else 1)

        else:
            # Test all workflows
            print("🧪 Testing all available workflows...")
            print("-" * 40)

            # Get available workflows
            workflows = client.list_workflows()
            print(f"Found {len(workflows)} workflows: {', '.join(w.name for w in workflows)}")
            print()

            # Run comprehensive test suite
            summary = tester.test_all_workflows()

            # Display results
            print(format_test_summary(summary, detailed=args.detailed))

            # Exit with appropriate code
            sys.exit(0 if summary.failed == 0 else 1)

    except KeyboardInterrupt:
        print("\n⚠️  Test execution interrupted by user")
        sys.exit(130)

    except FuzzForgeError as e:
        logger.error(f"FuzzForge API error: {e}")
        print(f"❌ FuzzForge API error: {e}")
        sys.exit(1)

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


def test_single_workflow_example():
    """
    Example function showing how to test a single workflow programmatically.

    This demonstrates the SDK usage for integration into other scripts.
    """
    # Initialize client and tester
    client = FuzzForgeClient(base_url="http://localhost:8000")
    tester = WorkflowTester(client)

    # Test a specific workflow
    result = tester.test_workflow(
        workflow_name="static_analysis_scan",
        expected_min_findings=3,  # Override default expectation
        timeout=300  # 5 minute timeout
    )

    # Handle results
    if result.passed:
        print(f"✅ Test passed! Found {result.findings_count} vulnerabilities")
        return True
    else:
        print(f"❌ Test failed: {result.error}")
        return False


def validate_deployments_example():
    """
    Example function showing how to validate workflow deployments.

    Useful for health checks and deployment verification.
    """
    client = FuzzForgeClient(base_url="http://localhost:8000")
    tester = WorkflowTester(client)

    # Check all workflows are deployed
    workflows = client.list_workflows()

    print("🔍 Validating workflow deployments:")
    all_valid = True

    for workflow in workflows:
        is_valid = tester.validate_workflow_deployment(workflow.name)
        status_icon = "✅" if is_valid else "❌"
        print(f"   {status_icon} {workflow.name}")

        if not is_valid:
            all_valid = False

    return all_valid


if __name__ == "__main__":
    main()