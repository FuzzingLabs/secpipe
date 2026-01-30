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
Real-time fuzzing monitoring example.

This example demonstrates how to:
1. Submit a fuzzing workflow
2. Monitor fuzzing progress in real-time using WebSocket or SSE
3. Display live statistics and crash reports
4. Handle real-time data updates
"""

import asyncio
import signal
import sys
from pathlib import Path
from datetime import datetime

from fuzzforge_sdk import FuzzForgeClient
from fuzzforge_sdk.utils import (
    create_workflow_submission,
    create_resource_limits,
    format_duration,
    format_execution_rate
)


class FuzzingMonitor:
    """Real-time fuzzing monitor with graceful shutdown."""

    def __init__(self, client: FuzzForgeClient):
        self.client = client
        self.running = True
        self.run_id = None

    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print(f"\n🛑 Received signal {signum}, shutting down...")
        self.running = False

    async def monitor_websocket(self, run_id: str):
        """Monitor fuzzing via WebSocket."""
        print("🔌 Starting WebSocket monitoring...")

        try:
            async for message in self.client.monitor_fuzzing_websocket(run_id):
                if not self.running:
                    break

                if message.type == "stats_update":
                    self.display_stats(message.data)
                elif message.type == "crash_report":
                    self.display_crash(message.data)
                elif message.type == "heartbeat":
                    print("💓 Heartbeat")
                else:
                    print(f"📨 Received: {message.type}")

        except KeyboardInterrupt:
            print("\n⏹️  Interrupted by user")
        except Exception as e:
            print(f"❌ WebSocket error: {e}")

    def monitor_sse(self, run_id: str):
        """Monitor fuzzing via Server-Sent Events."""
        print("📡 Starting SSE monitoring...")

        try:
            for message in self.client.monitor_fuzzing_sse(run_id):
                if not self.running:
                    break

                if message.type == "stats":
                    self.display_stats(message.data)
                elif message.type == "crash":
                    self.display_crash(message.data)
                else:
                    print(f"📨 Received: {message.type}")

        except KeyboardInterrupt:
            print("\n⏹️  Interrupted by user")
        except Exception as e:
            print(f"❌ SSE error: {e}")

    def display_stats(self, stats_data):
        """Display fuzzing statistics."""
        # Clear screen and move cursor to top
        print("\033[2J\033[H", end="")

        print("🎯 FuzzForge Live Fuzzing Monitor")
        print("=" * 50)
        print(f"Run ID: {stats_data.get('run_id', 'unknown')}")
        print(f"Workflow: {stats_data.get('workflow', 'unknown')}")
        print()

        # Statistics
        executions = stats_data.get('executions', 0)
        exec_per_sec = stats_data.get('executions_per_sec', 0.0)
        crashes = stats_data.get('crashes', 0)
        unique_crashes = stats_data.get('unique_crashes', 0)
        coverage = stats_data.get('coverage')
        corpus_size = stats_data.get('corpus_size', 0)
        elapsed_time = stats_data.get('elapsed_time', 0)

        print("📊 Statistics:")
        print(f"   Executions: {executions:,}")
        print(f"   Rate: {format_execution_rate(exec_per_sec)}")
        print(f"   Runtime: {format_duration(elapsed_time)}")
        print(f"   Corpus size: {corpus_size:,}")

        if coverage is not None:
            print(f"   Coverage: {coverage:.1f}%")

        print()
        print("💥 Crashes:")
        print(f"   Total crashes: {crashes}")
        print(f"   Unique crashes: {unique_crashes}")

        last_crash = stats_data.get('last_crash_time')
        if last_crash:
            crash_time = datetime.fromisoformat(last_crash.replace('Z', '+00:00'))
            print(f"   Last crash: {crash_time.strftime('%H:%M:%S')}")

        print()
        print("Press Ctrl+C to stop monitoring")
        print("-" * 50)

    def display_crash(self, crash_data):
        """Display new crash report."""
        print("\n🚨 NEW CRASH DETECTED!")
        print(f"   Crash ID: {crash_data.get('crash_id')}")
        print(f"   Signal: {crash_data.get('signal', 'unknown')}")
        print(f"   Type: {crash_data.get('crash_type', 'unknown')}")
        print(f"   Severity: {crash_data.get('severity', 'unknown')}")

        if crash_data.get('input_file'):
            print(f"   Input file: {crash_data['input_file']}")

        print("-" * 30)


async def main():
    """Main fuzzing monitoring example."""
    # Initialize client
    client = FuzzForgeClient(base_url="http://localhost:8000")
    monitor = FuzzingMonitor(client)

    # Set up signal handlers
    signal.signal(signal.SIGINT, monitor.signal_handler)
    signal.signal(signal.SIGTERM, monitor.signal_handler)

    try:
        # Check API status
        print("🔗 Connecting to FuzzForge API...")
        status = await client.aget_api_status()
        print(f"✅ Connected to {status.name} v{status.version}\n")

        # List workflows and find fuzzing ones
        workflows = await client.alist_workflows()
        fuzzing_workflows = [w for w in workflows if "fuzz" in w.name.lower() or "fuzzing" in w.tags]

        if not fuzzing_workflows:
            print("❌ No fuzzing workflows found")
            print("Available workflows:")
            for w in workflows:
                print(f"  • {w.name} (tags: {w.tags})")
            return

        # Select first fuzzing workflow
        selected_workflow = fuzzing_workflows[0]
        print(f"🎯 Selected fuzzing workflow: {selected_workflow.name}")

        # Create submission with fuzzing-appropriate settings
        target_path = Path.cwd().absolute()

        # Set longer timeout and resource limits for fuzzing
        resource_limits = create_resource_limits(
            cpu_limit="2",          # 2 CPU cores
            memory_limit="4Gi",     # 4GB memory
            cpu_request="1",        # Guarantee 1 core
            memory_request="2Gi"    # Guarantee 2GB
        )

        submission = create_workflow_submission(
            target_path=target_path,
            timeout=3600,      # 1 hour timeout
            resource_limits=resource_limits,
            parameters={
                "max_len": 1024,     # Maximum input length
                "timeout": 10,       # Per-execution timeout
                "runs": 1000000,     # Number of executions
            }
        )

        print("🚀 Submitting fuzzing workflow...")
        response = await client.asubmit_workflow(selected_workflow.name, submission)
        monitor.run_id = response.run_id

        print("✅ Fuzzing started!")
        print(f"   Run ID: {response.run_id}")
        print(f"   Initial status: {response.status}")
        print()

        # Wait a moment for fuzzing to initialize
        await asyncio.sleep(5)

        # Get initial stats to verify fuzzing is tracked
        try:
            stats = await client.aget_fuzzing_stats(response.run_id)
            print(f"📊 Fuzzing tracking initialized for workflow: {stats.workflow}")
        except Exception as e:
            print(f"⚠️  Warning: Fuzzing tracking not available: {e}")
            print("   Monitoring will show run status updates only")

        # Choose monitoring method
        if len(sys.argv) > 1 and sys.argv[1] == "--sse":
            print("📡 Using Server-Sent Events for monitoring...")
            monitor.monitor_sse(response.run_id)
        else:
            print("🔌 Using WebSocket for monitoring...")
            await monitor.monitor_websocket(response.run_id)

    except KeyboardInterrupt:
        print("\n⏹️  Interrupted by user")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        # Cleanup
        if monitor.run_id:
            try:
                print(f"\n🧹 Cleaning up fuzzing run {monitor.run_id}...")
                await client.acleanup_fuzzing_run(monitor.run_id)
                print("✅ Cleanup completed")
            except Exception as e:
                print(f"⚠️  Cleanup failed: {e}")

        await client.aclose()


def sync_monitor_example():
    """Example of synchronous SSE monitoring."""
    client = FuzzForgeClient(base_url="http://localhost:8000")

    try:
        # This would require a pre-existing fuzzing run
        run_id = input("Enter fuzzing run ID to monitor: ").strip()
        if not run_id:
            print("❌ Run ID required")
            return

        print(f"📡 Monitoring fuzzing run: {run_id}")
        print("Press Ctrl+C to stop")
        print()

        monitor = FuzzingMonitor(client)
        monitor.monitor_sse(run_id)

    except KeyboardInterrupt:
        print("\n⏹️  Monitoring stopped")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--sync":
        print("🔄 Running synchronous SSE monitoring...")
        sync_monitor_example()
    else:
        print("🔄 Running async WebSocket monitoring...")
        print("💡 Use --sse flag for Server-Sent Events")
        print("💡 Use --sync flag for synchronous monitoring")
        asyncio.run(main())