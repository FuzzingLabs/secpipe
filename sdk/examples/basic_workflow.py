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
Basic workflow submission example.

This example demonstrates how to:
1. Connect to FuzzForge API
2. List available workflows
3. Submit a workflow for analysis
4. Monitor the run status
5. Retrieve findings when complete
"""

import asyncio
import time
from pathlib import Path

from fuzzforge_sdk import FuzzForgeClient
from fuzzforge_sdk.utils import create_workflow_submission, format_sarif_summary, format_duration


def main():
    """Run basic workflow submission example."""
    # Initialize the client
    client = FuzzForgeClient(base_url="http://localhost:8000")

    try:
        # Check API status
        print("🔗 Connecting to FuzzForge API...")
        status = client.get_api_status()
        print(f"✅ Connected to {status.name} v{status.version}")
        print(f"📊 {status.workflows_loaded} workflows loaded\n")

        # List available workflows
        print("📋 Available workflows:")
        workflows = client.list_workflows()
        for workflow in workflows:
            print(f"  • {workflow.name} v{workflow.version}")
            print(f"    {workflow.description}")
            if workflow.tags:
                print(f"    Tags: {', '.join(workflow.tags)}")
            print()

        if not workflows:
            print("❌ No workflows available")
            return

        # Select the first workflow for demo
        selected_workflow = workflows[0]
        print(f"🎯 Selected workflow: {selected_workflow.name}")

        # Get workflow metadata
        metadata = client.get_workflow_metadata(selected_workflow.name)
        print("📝 Workflow metadata:")
        print(f"  Author: {metadata.author}")
        print(f"  Required modules: {metadata.required_modules}")
        print()

        # Prepare target path (use current directory as example)
        target_path = Path.cwd().absolute()
        print(f"🎯 Target path: {target_path}")

        # Create workflow submission
        submission = create_workflow_submission(
            target_path=target_path,
            timeout=300,  # 5 minutes
        )

        # Submit the workflow
        print(f"🚀 Submitting workflow '{selected_workflow.name}'...")
        response = client.submit_workflow(selected_workflow.name, submission)
        print("✅ Workflow submitted!")
        print(f"   Run ID: {response.run_id}")
        print(f"   Status: {response.status}")
        print()

        # Monitor the run
        print("⏱️  Monitoring run progress...")
        start_time = time.time()

        while True:
            status = client.get_run_status(response.run_id)
            elapsed = time.time() - start_time

            print(f"   Status: {status.status} (elapsed: {format_duration(int(elapsed))})")

            if status.is_completed:
                print("✅ Run completed successfully!")
                break
            elif status.is_failed:
                print("❌ Run failed!")
                print(f"   Final status: {status.status}")
                return
            elif not status.is_running:
                print("⏸️  Run is not active")
                print(f"   Current status: {status.status}")

            # Wait before next check
            time.sleep(5)

        print()

        # Get findings
        print("📊 Retrieving findings...")
        try:
            findings = client.get_run_findings(response.run_id)
            print(f"✅ Findings retrieved for workflow: {findings.workflow}")

            # Display SARIF summary
            sarif_summary = format_sarif_summary(findings.sarif)
            print(f"📈 {sarif_summary}")

            # Display metadata
            if findings.metadata:
                print("🔍 Metadata:")
                for key, value in findings.metadata.items():
                    print(f"   {key}: {value}")

            print()

            # Extract and display detailed findings
            from fuzzforge_sdk.utils import extract_sarif_results
            results = extract_sarif_results(findings.sarif)

            if results:
                print("🔍 Detailed Findings:")
                print("=" * 60)

                for i, result in enumerate(results, 1):
                    print(f"\n📋 Finding #{i}")

                    # Rule information
                    rule_id = result.get('ruleId', 'unknown')
                    level = result.get('level', 'warning')
                    message = result.get('message', {})

                    print(f"   Rule ID: {rule_id}")
                    print(f"   Severity: {level.upper()}")

                    # Message
                    if isinstance(message, dict):
                        msg_text = message.get('text', 'No message')
                    else:
                        msg_text = str(message)
                    print(f"   Message: {msg_text}")

                    # Location information
                    locations = result.get('locations', [])
                    if locations:
                        for loc in locations:
                            physical_loc = loc.get('physicalLocation', {})
                            artifact_loc = physical_loc.get('artifactLocation', {})
                            region = physical_loc.get('region', {})

                            file_path = artifact_loc.get('uri', 'unknown file')
                            start_line = region.get('startLine', 'unknown')
                            start_col = region.get('startColumn', 'unknown')

                            print(f"   Location: {file_path}:{start_line}:{start_col}")

                            # Show code snippet if available
                            snippet = region.get('snippet', {})
                            if snippet and isinstance(snippet, dict):
                                snippet_text = snippet.get('text', '').strip()
                                if snippet_text:
                                    print(f"   Code: {snippet_text}")

                    # Additional properties
                    properties = result.get('properties', {})
                    if properties:
                        print("   Properties:")
                        for prop_key, prop_value in properties.items():
                            print(f"     {prop_key}: {prop_value}")

                    print("-" * 40)

                print(f"\n📁 Total findings: {len(results)}")

            print("\n💾 Tip: Use save_sarif_to_file() to save findings to disk")

        except Exception as e:
            print(f"❌ Failed to retrieve findings: {e}")

    except KeyboardInterrupt:
        print("\n⏹️  Interrupted by user")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.close()


async def async_main():
    """Run basic workflow submission example (async version)."""
    # Initialize the async client
    async with FuzzForgeClient(base_url="http://localhost:8000") as client:
        try:
            # Check API status
            print("🔗 Connecting to FuzzForge API...")
            status = await client.aget_api_status()
            print(f"✅ Connected to {status.name} v{status.version}")
            print(f"📊 {status.workflows_loaded} workflows loaded\n")

            # List available workflows
            print("📋 Available workflows:")
            workflows = await client.alist_workflows()
            for workflow in workflows:
                print(f"  • {workflow.name} v{workflow.version}")
                print(f"    {workflow.description}")
                if workflow.tags:
                    print(f"    Tags: {', '.join(workflow.tags)}")
                print()

            if not workflows:
                print("❌ No workflows available")
                return

            # Select the first workflow for demo
            selected_workflow = workflows[0]
            print(f"🎯 Selected workflow: {selected_workflow.name}")

            # Prepare target path
            target_path = Path.cwd().absolute()
            submission = create_workflow_submission(
                target_path=target_path,
                timeout=300,
            )

            # Submit the workflow
            print(f"🚀 Submitting workflow '{selected_workflow.name}'...")
            response = await client.asubmit_workflow(selected_workflow.name, submission)
            print(f"✅ Workflow submitted! Run ID: {response.run_id}")

            # Wait for completion
            print("⏱️  Waiting for completion...")
            final_status = await client.await_for_completion(
                response.run_id,
                poll_interval=3.0,
                timeout=600.0  # 10 minutes max
            )
            print(f"✅ Run completed with status: {final_status.status}")

            # Get findings
            findings = await client.aget_run_findings(response.run_id)
            sarif_summary = format_sarif_summary(findings.sarif)
            print(f"📈 {sarif_summary}")

            # Extract and display detailed findings
            from fuzzforge_sdk.utils import extract_sarif_results
            results = extract_sarif_results(findings.sarif)

            if results:
                print("\n🔍 Detailed Findings:")
                print("=" * 60)

                for i, result in enumerate(results, 1):
                    print(f"\n📋 Finding #{i}")
                    rule_id = result.get('ruleId', 'unknown')
                    level = result.get('level', 'warning')
                    message = result.get('message', {})

                    print(f"   Rule ID: {rule_id}")
                    print(f"   Severity: {level.upper()}")

                    if isinstance(message, dict):
                        msg_text = message.get('text', 'No message')
                    else:
                        msg_text = str(message)
                    print(f"   Message: {msg_text}")

                    locations = result.get('locations', [])
                    if locations:
                        for loc in locations:
                            physical_loc = loc.get('physicalLocation', {})
                            artifact_loc = physical_loc.get('artifactLocation', {})
                            region = physical_loc.get('region', {})

                            file_path = artifact_loc.get('uri', 'unknown file')
                            start_line = region.get('startLine', 'unknown')
                            start_col = region.get('startColumn', 'unknown')

                            print(f"   Location: {file_path}:{start_line}:{start_col}")

                    print("-" * 40)

        except Exception as e:
            print(f"❌ Error: {e}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--async":
        print("🔄 Running async version...")
        asyncio.run(async_main())
    else:
        print("🔄 Running synchronous version...")
        print("💡 Use --async flag to run async version")
        main()