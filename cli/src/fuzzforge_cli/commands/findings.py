"""
Findings and security results management commands.
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
import csv
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich import box

from ..config import get_project_config, FuzzForgeConfig
from ..database import get_project_db, ensure_project_db, FindingRecord
from ..exceptions import (
    retry_on_network_error, validate_run_id,
    require_project, ValidationError
)
from fuzzforge_sdk import FuzzForgeClient

console = Console()
app = typer.Typer()


@retry_on_network_error(max_retries=3, delay=1.0)
def get_client() -> FuzzForgeClient:
    """Get configured FuzzForge client with retry on network errors"""
    config = get_project_config() or FuzzForgeConfig()
    return FuzzForgeClient(base_url=config.get_api_url(), timeout=config.get_timeout())


def severity_style(severity: str) -> str:
    """Get rich style for severity level"""
    return {
        "error": "bold red",
        "warning": "bold yellow",
        "note": "bold blue",
        "info": "bold cyan"
    }.get(severity.lower(), "white")


@app.command("get")
def get_findings(
    run_id: str = typer.Argument(..., help="Run ID to get findings for"),
    save: bool = typer.Option(
        True, "--save/--no-save",
        help="Save findings to local database"
    ),
    format: str = typer.Option(
        "table", "--format", "-f",
        help="Output format: table, json, sarif"
    )
):
    """
    🔍 Retrieve and display security findings for a run
    """
    try:
        require_project()
        validate_run_id(run_id)

        if format not in ["table", "json", "sarif"]:
            raise ValidationError("format", format, "one of: table, json, sarif")
        with get_client() as client:
            console.print(f"🔍 Fetching findings for run: {run_id}")
            findings = client.get_run_findings(run_id)

        # Save to database if requested
        if save:
            try:
                db = ensure_project_db()

                # Extract summary from SARIF
                sarif_data = findings.sarif
                runs_data = sarif_data.get("runs", [])
                summary = {}

                if runs_data:
                    results = runs_data[0].get("results", [])
                    summary = {
                        "total_issues": len(results),
                        "by_severity": {},
                        "by_rule": {},
                        "tools": []
                    }

                    for result in results:
                        level = result.get("level", "note")
                        rule_id = result.get("ruleId", "unknown")

                        summary["by_severity"][level] = summary["by_severity"].get(level, 0) + 1
                        summary["by_rule"][rule_id] = summary["by_rule"].get(rule_id, 0) + 1

                    # Extract tool info
                    tool = runs_data[0].get("tool", {})
                    driver = tool.get("driver", {})
                    if driver.get("name"):
                        summary["tools"].append({
                            "name": driver.get("name"),
                            "version": driver.get("version"),
                            "rules": len(driver.get("rules", []))
                        })

                finding_record = FindingRecord(
                    run_id=run_id,
                    sarif_data=sarif_data,
                    summary=summary,
                    created_at=datetime.now()
                )
                db.save_findings(finding_record)
                console.print("✅ Findings saved to local database", style="green")
            except Exception as e:
                console.print(f"⚠️  Failed to save findings to database: {e}", style="yellow")

        # Display findings
        if format == "json":
            findings_json = json.dumps(findings.sarif, indent=2)
            console.print(Syntax(findings_json, "json", theme="monokai"))

        elif format == "sarif":
            sarif_json = json.dumps(findings.sarif, indent=2)
            console.print(sarif_json)

        else:  # table format
            display_findings_table(findings.sarif)

            # Suggest export command and show command
            console.print(f"\n💡 View full details of a finding: [bold cyan]ff finding show {run_id} --rule <rule-id>[/bold cyan]")
            console.print(f"💡 Export these findings: [bold cyan]ff findings export {run_id} --format sarif[/bold cyan]")
            console.print("   Supported formats: [cyan]sarif[/cyan] (standard), [cyan]json[/cyan], [cyan]csv[/cyan], [cyan]html[/cyan]")

    except Exception as e:
        console.print(f"❌ Failed to get findings: {e}", style="red")
        raise typer.Exit(1)


def show_finding(
    run_id: str = typer.Argument(..., help="Run ID to get finding from"),
    rule_id: str = typer.Option(..., "--rule", "-r", help="Rule ID of the specific finding to show")
):
    """
    🔍 Show detailed information about a specific finding

    This function is registered as a command in main.py under the finding (singular) command group.
    """
    try:
        require_project()
        validate_run_id(run_id)

        # Try to get from database first, fallback to API
        db = get_project_db()
        findings_data = None
        if db:
            findings_data = db.get_findings(run_id)

        if not findings_data:
            with get_client() as client:
                console.print(f"🔍 Fetching findings for run: {run_id}")
                findings = client.get_run_findings(run_id)
                sarif_data = findings.sarif
        else:
            sarif_data = findings_data.sarif_data

        # Find the specific finding by rule_id
        runs = sarif_data.get("runs", [])
        if not runs:
            console.print("❌ No findings data available", style="red")
            raise typer.Exit(1)

        run_data = runs[0]
        results = run_data.get("results", [])
        tool = run_data.get("tool", {}).get("driver", {})

        # Search for matching finding
        matching_finding = None
        for result in results:
            if result.get("ruleId") == rule_id:
                matching_finding = result
                break

        if not matching_finding:
            console.print(f"❌ No finding found with rule ID: {rule_id}", style="red")
            console.print(f"💡 Use [bold cyan]ff findings get {run_id}[/bold cyan] to see all findings", style="dim")
            raise typer.Exit(1)

        # Display detailed finding
        display_finding_detail(matching_finding, tool, run_id)

    except Exception as e:
        console.print(f"❌ Failed to get finding: {e}", style="red")
        raise typer.Exit(1)


def display_finding_detail(finding: Dict[str, Any], tool: Dict[str, Any], run_id: str):
    """Display detailed information about a single finding"""
    rule_id = finding.get("ruleId", "unknown")
    level = finding.get("level", "note")
    message = finding.get("message", {})
    message_text = message.get("text", "No summary available")
    message_markdown = message.get("markdown", message_text)

    # Get location
    locations = finding.get("locations", [])
    location_str = "Unknown location"
    code_snippet = None

    if locations:
        physical_location = locations[0].get("physicalLocation", {})
        artifact_location = physical_location.get("artifactLocation", {})
        region = physical_location.get("region", {})

        file_path = artifact_location.get("uri", "")
        if file_path:
            location_str = file_path
            if region.get("startLine"):
                location_str += f":{region['startLine']}"
                if region.get("startColumn"):
                    location_str += f":{region['startColumn']}"

        # Get code snippet if available
        if region.get("snippet", {}).get("text"):
            code_snippet = region["snippet"]["text"].strip()

    # Get severity style
    severity_color = {
        "error": "red",
        "warning": "yellow",
        "note": "blue",
        "info": "cyan"
    }.get(level.lower(), "white")

    # Build detailed content
    content_lines = []
    content_lines.append(f"[bold]Rule ID:[/bold] {rule_id}")
    content_lines.append(f"[bold]Severity:[/bold] [{severity_color}]{level.upper()}[/{severity_color}]")
    content_lines.append(f"[bold]Location:[/bold] {location_str}")
    content_lines.append(f"[bold]Tool:[/bold] {tool.get('name', 'Unknown')} v{tool.get('version', 'unknown')}")
    content_lines.append(f"[bold]Run ID:[/bold] {run_id}")
    content_lines.append("")
    content_lines.append(f"[bold]Summary:[/bold]")
    content_lines.append(message_text)
    content_lines.append("")
    content_lines.append(f"[bold]Description:[/bold]")
    content_lines.append(message_markdown)

    if code_snippet:
        content_lines.append("")
        content_lines.append(f"[bold]Code Snippet:[/bold]")
        content_lines.append(f"[dim]{code_snippet}[/dim]")

    content = "\n".join(content_lines)

    # Display in panel
    console.print()
    console.print(Panel(
        content,
        title=f"🔍 Finding Detail",
        border_style=severity_color,
        box=box.ROUNDED,
        padding=(1, 2)
    ))
    console.print()
    console.print(f"💡 Export this run: [bold cyan]ff findings export {run_id} --format sarif[/bold cyan]")


def display_findings_table(sarif_data: Dict[str, Any]):
    """Display SARIF findings in a rich table format"""
    runs = sarif_data.get("runs", [])
    if not runs:
        console.print("ℹ️  No findings data available", style="dim")
        return

    run_data = runs[0]
    results = run_data.get("results", [])
    tool = run_data.get("tool", {})
    driver = tool.get("driver", {})

    # Tool information
    console.print("\n🔍 [bold]Security Analysis Results[/bold]")
    if driver.get("name"):
        console.print(f"Tool: {driver.get('name')} v{driver.get('version', 'unknown')}")

    if not results:
        console.print("✅ No security issues found!", style="green")
        return

    # Summary statistics
    summary_by_level = {}
    for result in results:
        level = result.get("level", "note")
        summary_by_level[level] = summary_by_level.get(level, 0) + 1

    summary_table = Table(show_header=False, box=box.SIMPLE)
    summary_table.add_column("Severity", width=15, justify="left", style="bold")
    summary_table.add_column("Count", width=8, justify="right", style="bold")

    for level, count in sorted(summary_by_level.items()):
        # Create Rich Text object with color styling
        level_text = level.upper()
        severity_text = Text(level_text, style=severity_style(level))
        count_text = Text(str(count))

        summary_table.add_row(severity_text, count_text)

    console.print(
        Panel.fit(
            summary_table,
            title=f"📊 Summary ({len(results)} total issues)",
            box=box.ROUNDED
        )
    )

    # Detailed results - Rich Text-based table with proper emoji alignment
    results_table = Table(box=box.ROUNDED)
    results_table.add_column("Severity", width=12, justify="left", no_wrap=True)
    results_table.add_column("Rule", justify="left", style="bold cyan", no_wrap=True)
    results_table.add_column("Message", width=45, justify="left", no_wrap=True)
    results_table.add_column("Location", width=20, justify="left", style="dim", no_wrap=True)

    for result in results[:50]:  # Limit to first 50 results
        level = result.get("level", "note")
        rule_id = result.get("ruleId", "unknown")
        message = result.get("message", {}).get("text", "No message")

        # Extract location information
        locations = result.get("locations", [])
        location_str = ""
        if locations:
            physical_location = locations[0].get("physicalLocation", {})
            artifact_location = physical_location.get("artifactLocation", {})
            region = physical_location.get("region", {})

            file_path = artifact_location.get("uri", "")
            if file_path:
                location_str = Path(file_path).name
                if region.get("startLine"):
                    location_str += f":{region['startLine']}"
                    if region.get("startColumn"):
                        location_str += f":{region['startColumn']}"

        # Create Rich Text objects with color styling
        severity_text = Text(level.upper(), style=severity_style(level))
        severity_text.truncate(12, overflow="ellipsis")

        # Show full rule ID without truncation
        message_text = Text(message)
        message_text.truncate(45, overflow="ellipsis")

        location_text = Text(location_str)
        location_text.truncate(20, overflow="ellipsis")

        results_table.add_row(
            severity_text,
            rule_id,  # Pass string directly to show full UUID
            message_text,
            location_text
        )

    console.print("\n📋 [bold]Detailed Results[/bold]")
    if len(results) > 50:
        console.print(f"Showing first 50 of {len(results)} results")
    console.print()
    console.print(results_table)


@app.command("history")
def findings_history(
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum number of findings to show")
):
    """
    📚 Show findings history from local database
    """
    db = get_project_db()
    if not db:
        console.print("❌ No FuzzForge project found. Run 'ff init' first.", style="red")
        raise typer.Exit(1)

    try:
        findings = db.list_findings(limit=limit)

        if not findings:
            console.print("❌ No findings found in database", style="red")
            return

        table = Table(box=box.ROUNDED)
        table.add_column("Run ID", style="bold cyan", width=36)  # Full UUID width
        table.add_column("Date", justify="center")
        table.add_column("Total Issues", justify="center", style="bold")
        table.add_column("Errors", justify="center", style="red")
        table.add_column("Warnings", justify="center", style="yellow")
        table.add_column("Notes", justify="center", style="blue")
        table.add_column("Tools", style="dim")

        for finding in findings:
            summary = finding.summary
            total_issues = summary.get("total_issues", 0)
            by_severity = summary.get("by_severity", {})
            tools = summary.get("tools", [])

            tool_names = ", ".join([tool.get("name", "Unknown") for tool in tools])

            table.add_row(
                finding.run_id,  # Show full Run ID
                finding.created_at.strftime("%m-%d %H:%M"),
                str(total_issues),
                str(by_severity.get("error", 0)),
                str(by_severity.get("warning", 0)),
                str(by_severity.get("note", 0)),
                tool_names[:30] + "..." if len(tool_names) > 30 else tool_names
            )

        console.print(f"\n📚 [bold]Findings History ({len(findings)})[/bold]\n")
        console.print(table)

        console.print("\n💡 Use [bold cyan]fuzzforge finding <run-id>[/bold cyan] to view detailed findings")

    except Exception as e:
        console.print(f"❌ Failed to get findings history: {e}", style="red")
        raise typer.Exit(1)


@app.command("export")
def export_findings(
    run_id: str = typer.Argument(..., help="Run ID to export findings for"),
    format: str = typer.Option(
        "sarif", "--format", "-f",
        help="Export format: sarif (standard), json, csv, html"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o",
        help="Output file path (defaults to findings-<run-id>-<timestamp>.<format>)"
    )
):
    """
    📤 Export security findings in various formats

    SARIF is the standard format for security findings and is recommended
    for interoperability with other security tools. Filenames are automatically
    made unique with timestamps to prevent overwriting previous exports.
    """
    db = get_project_db()
    if not db:
        console.print("❌ No FuzzForge project found. Run 'ff init' first.", style="red")
        raise typer.Exit(1)

    try:
        # Get findings from database first, fallback to API
        findings_data = db.get_findings(run_id)
        if not findings_data:
            console.print(f"📡 Fetching findings from API for run: {run_id}")
            with get_client() as client:
                findings = client.get_run_findings(run_id)
                sarif_data = findings.sarif
        else:
            sarif_data = findings_data.sarif_data

        # Generate output filename with timestamp for uniqueness
        if not output:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            output = f"findings-{run_id[:8]}-{timestamp}.{format}"

        output_path = Path(output)

        # Export based on format
        if format == "sarif":
            with open(output_path, 'w') as f:
                json.dump(sarif_data, f, indent=2)

        elif format == "json":
            # Simplified JSON format
            simplified_data = extract_simplified_findings(sarif_data)
            with open(output_path, 'w') as f:
                json.dump(simplified_data, f, indent=2)

        elif format == "csv":
            export_to_csv(sarif_data, output_path)

        elif format == "html":
            export_to_html(sarif_data, output_path, run_id)

        else:
            console.print(f"❌ Unsupported format: {format}", style="red")
            raise typer.Exit(1)

        console.print(f"✅ Findings exported to: [bold cyan]{output_path}[/bold cyan]")

    except Exception as e:
        console.print(f"❌ Failed to export findings: {e}", style="red")
        raise typer.Exit(1)


def extract_simplified_findings(sarif_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract simplified findings structure from SARIF"""
    runs = sarif_data.get("runs", [])
    if not runs:
        return {"findings": [], "summary": {}}

    run_data = runs[0]
    results = run_data.get("results", [])
    tool = run_data.get("tool", {}).get("driver", {})

    simplified = {
        "tool": {
            "name": tool.get("name", "Unknown"),
            "version": tool.get("version", "Unknown")
        },
        "summary": {
            "total_issues": len(results),
            "by_severity": {}
        },
        "findings": []
    }

    for result in results:
        level = result.get("level", "note")
        simplified["summary"]["by_severity"][level] = simplified["summary"]["by_severity"].get(level, 0) + 1

        # Extract location
        location_info = {}
        locations = result.get("locations", [])
        if locations:
            physical_location = locations[0].get("physicalLocation", {})
            artifact_location = physical_location.get("artifactLocation", {})
            region = physical_location.get("region", {})

            location_info = {
                "file": artifact_location.get("uri", ""),
                "line": region.get("startLine"),
                "column": region.get("startColumn")
            }

        simplified["findings"].append({
            "rule_id": result.get("ruleId", "unknown"),
            "severity": level,
            "message": result.get("message", {}).get("text", ""),
            "location": location_info
        })

    return simplified


def export_to_csv(sarif_data: Dict[str, Any], output_path: Path):
    """Export findings to CSV format"""
    runs = sarif_data.get("runs", [])
    if not runs:
        return

    results = runs[0].get("results", [])

    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['rule_id', 'severity', 'message', 'file', 'line', 'column']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for result in results:
            location_info = {"file": "", "line": "", "column": ""}
            locations = result.get("locations", [])
            if locations:
                physical_location = locations[0].get("physicalLocation", {})
                artifact_location = physical_location.get("artifactLocation", {})
                region = physical_location.get("region", {})

                location_info = {
                    "file": artifact_location.get("uri", ""),
                    "line": region.get("startLine", ""),
                    "column": region.get("startColumn", "")
                }

            writer.writerow({
                "rule_id": result.get("ruleId", ""),
                "severity": result.get("level", "note"),
                "message": result.get("message", {}).get("text", ""),
                **location_info
            })


def export_to_html(sarif_data: Dict[str, Any], output_path: Path, run_id: str):
    """Export findings to HTML format"""
    runs = sarif_data.get("runs", [])
    if not runs:
        return

    run_data = runs[0]
    results = run_data.get("results", [])
    tool = run_data.get("tool", {}).get("driver", {})

    # Simple HTML template
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Security Findings - {run_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .header {{ background: #f4f4f4; padding: 20px; border-radius: 5px; }}
        .summary {{ margin: 20px 0; }}
        .findings {{ margin: 20px 0; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #f2f2f2; }}
        .error {{ color: #d32f2f; }}
        .warning {{ color: #f57c00; }}
        .note {{ color: #1976d2; }}
        .info {{ color: #388e3c; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Security Findings Report</h1>
        <p><strong>Run ID:</strong> {run_id}</p>
        <p><strong>Tool:</strong> {tool.get('name', 'Unknown')} v{tool.get('version', 'Unknown')}</p>
        <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>

    <div class="summary">
        <h2>Summary</h2>
        <p><strong>Total Issues:</strong> {len(results)}</p>
    </div>

    <div class="findings">
        <h2>Detailed Findings</h2>
        <table>
            <thead>
                <tr>
                    <th>Rule ID</th>
                    <th>Severity</th>
                    <th>Message</th>
                    <th>Location</th>
                </tr>
            </thead>
            <tbody>
"""

    for result in results:
        level = result.get("level", "note")
        rule_id = result.get("ruleId", "unknown")
        message = result.get("message", {}).get("text", "")

        # Extract location
        location_str = ""
        locations = result.get("locations", [])
        if locations:
            physical_location = locations[0].get("physicalLocation", {})
            artifact_location = physical_location.get("artifactLocation", {})
            region = physical_location.get("region", {})

            file_path = artifact_location.get("uri", "")
            if file_path:
                location_str = file_path
                if region.get("startLine"):
                    location_str += f":{region['startLine']}"

        html_content += f"""
                <tr>
                    <td>{rule_id}</td>
                    <td class="{level}">{level}</td>
                    <td>{message}</td>
                    <td>{location_str}</td>
                </tr>
        """

    html_content += """
            </tbody>
        </table>
    </div>
</body>
</html>
    """

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)


@app.command("all")
def all_findings(
    workflow: Optional[str] = typer.Option(
        None, "--workflow", "-w",
        help="Filter by workflow name"
    ),
    severity: Optional[str] = typer.Option(
        None, "--severity", "-s",
        help="Filter by severity levels (comma-separated: error,warning,note,info)"
    ),
    since: Optional[str] = typer.Option(
        None, "--since",
        help="Show findings since date (YYYY-MM-DD)"
    ),
    limit: Optional[int] = typer.Option(
        None, "--limit", "-l",
        help="Maximum number of findings to show"
    ),
    export_format: Optional[str] = typer.Option(
        None, "--export", "-e",
        help="Export format: json, csv, html"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o",
        help="Output file for export"
    ),
    stats_only: bool = typer.Option(
        False, "--stats",
        help="Show statistics only"
    ),
    show_findings: bool = typer.Option(
        False, "--show-findings", "-f",
        help="Show actual findings content, not just summary"
    ),
    max_findings: int = typer.Option(
        50, "--max-findings",
        help="Maximum number of individual findings to display"
    )
):
    """
    📊 Show all findings for the entire project
    """
    db = get_project_db()
    if not db:
        console.print("❌ No FuzzForge project found. Run 'ff init' first.", style="red")
        raise typer.Exit(1)

    try:
        # Parse filters
        severity_list = None
        if severity:
            severity_list = [s.strip().lower() for s in severity.split(",")]

        since_date = None
        if since:
            try:
                since_date = datetime.strptime(since, "%Y-%m-%d")
            except ValueError:
                console.print(f"❌ Invalid date format: {since}. Use YYYY-MM-DD", style="red")
                raise typer.Exit(1)

        # Get aggregated stats
        stats = db.get_aggregated_stats()

        # Show statistics
        if stats_only or not export_format:
            # Create summary panel
            summary_text = f"""[bold]📊 Project Security Summary[/bold]

[cyan]Total Findings Records:[/cyan] {stats['total_findings_records']}
[cyan]Total Runs Analyzed:[/cyan] {stats['total_runs']}
[cyan]Total Security Issues:[/cyan] {stats['total_issues']}
[cyan]Recent Findings (7 days):[/cyan] {stats['recent_findings']}

[bold]Severity Distribution:[/bold]
  🔴 Errors: {stats['severity_distribution'].get('error', 0)}
  🟡 Warnings: {stats['severity_distribution'].get('warning', 0)}
  🔵 Notes: {stats['severity_distribution'].get('note', 0)}
  ℹ️  Info: {stats['severity_distribution'].get('info', 0)}

[bold]By Workflow:[/bold]"""

            for wf_name, count in stats['workflows'].items():
                summary_text += f"\n  • {wf_name}: {count} findings"

            console.print(Panel(summary_text, box=box.ROUNDED, title="FuzzForge Project Analysis", border_style="cyan"))

        if stats_only:
            return

        # Get all findings with filters
        findings = db.get_all_findings(
            workflow=workflow,
            severity=severity_list,
            since_date=since_date,
            limit=limit
        )

        if not findings:
            console.print("ℹ️  No findings match the specified filters", style="dim")
            return

        # Export if requested
        if export_format:
            if not output:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output = f"all_findings_{timestamp}.{export_format}"

            export_all_findings(findings, export_format, output)
            console.print(f"✅ Exported {len(findings)} findings to: {output}", style="green")
            return

        # Display findings table
        table = Table(box=box.ROUNDED, title=f"All Project Findings ({len(findings)} records)")
        table.add_column("Run ID", style="bold cyan", width=36)  # Full UUID width
        table.add_column("Workflow", style="dim", width=20)
        table.add_column("Date", justify="center")
        table.add_column("Issues", justify="center", style="bold")
        table.add_column("Errors", justify="center", style="red")
        table.add_column("Warnings", justify="center", style="yellow")
        table.add_column("Notes", justify="center", style="blue")

        # Get run info for each finding
        runs_info = {}
        for finding in findings:
            run_id = finding.run_id
            if run_id not in runs_info:
                run_info = db.get_run(run_id)
                runs_info[run_id] = run_info

        for finding in findings:
            run_id = finding.run_id
            run_info = runs_info.get(run_id)
            workflow_name = run_info.workflow if run_info else "unknown"

            summary = finding.summary
            total_issues = summary.get("total_issues", 0)
            by_severity = summary.get("by_severity", {})

            # Count issues from SARIF data if summary is incomplete
            if total_issues == 0 and "runs" in finding.sarif_data:
                for run in finding.sarif_data["runs"]:
                    total_issues += len(run.get("results", []))

            table.add_row(
                run_id,  # Show full Run ID
                workflow_name[:17] + "..." if len(workflow_name) > 20 else workflow_name,
                finding.created_at.strftime("%Y-%m-%d %H:%M"),
                str(total_issues),
                str(by_severity.get("error", 0)),
                str(by_severity.get("warning", 0)),
                str(by_severity.get("note", 0))
            )

        console.print(table)

        # Show actual findings if requested
        if show_findings:
            display_detailed_findings(findings, max_findings)

        console.print("\n💡 Use filters to refine results: --workflow, --severity, --since")
        console.print("💡 Show findings content: --show-findings")
        console.print("💡 Export findings: --export json --output report.json")
        console.print("💡 View specific findings: [bold cyan]fuzzforge finding <run-id>[/bold cyan]")

    except Exception as e:
        console.print(f"❌ Failed to get all findings: {e}", style="red")
        raise typer.Exit(1)


def display_detailed_findings(findings: List[FindingRecord], max_findings: int):
    """Display detailed findings content"""
    console.print(f"\n📋 [bold]Detailed Findings Content[/bold] (showing up to {max_findings} findings)\n")

    findings_count = 0

    for finding_record in findings:
        if findings_count >= max_findings:
            remaining = sum(len(run.get("results", []))
                          for f in findings[findings.index(finding_record):]
                          for run in f.sarif_data.get("runs", []))
            if remaining > 0:
                console.print(f"\n... and {remaining} more findings (use --max-findings to show more)")
            break

        # Get run info for this finding
        sarif_data = finding_record.sarif_data
        if not sarif_data or "runs" not in sarif_data:
            continue

        for run in sarif_data["runs"]:
            tool = run.get("tool", {})
            driver = tool.get("driver", {})
            tool_name = driver.get("name", "Unknown Tool")

            results = run.get("results", [])
            if not results:
                continue

            # Group results by severity
            for result in results:
                if findings_count >= max_findings:
                    break

                findings_count += 1

                # Extract key information
                rule_id = result.get("ruleId", "unknown")
                level = result.get("level", "note").upper()
                message_text = result.get("message", {}).get("text", "No description")

                # Get location information
                locations = result.get("locations", [])
                location_str = "Unknown location"
                if locations:
                    physical = locations[0].get("physicalLocation", {})
                    artifact = physical.get("artifactLocation", {})
                    region = physical.get("region", {})

                    file_path = artifact.get("uri", "")
                    line_number = region.get("startLine", "")

                    if file_path:
                        location_str = f"{file_path}"
                        if line_number:
                            location_str += f":{line_number}"

                # Get severity style
                severity_style = {
                    "ERROR": "bold red",
                    "WARNING": "bold yellow",
                    "NOTE": "bold blue",
                    "INFO": "bold cyan"
                }.get(level, "white")

                # Create finding panel
                finding_content = f"""[bold]Rule:[/bold] {rule_id}
[bold]Location:[/bold] {location_str}
[bold]Tool:[/bold] {tool_name}
[bold]Run:[/bold] {finding_record.run_id[:12]}...

[bold]Description:[/bold]
{message_text}"""

                # Add code context if available
                region = locations[0].get("physicalLocation", {}).get("region", {}) if locations else {}
                if region.get("snippet", {}).get("text"):
                    code_snippet = region["snippet"]["text"].strip()
                    finding_content += f"\n\n[bold]Code:[/bold]\n[dim]{code_snippet}[/dim]"

                console.print(Panel(
                    finding_content,
                    title=f"[{severity_style}]{level}[/{severity_style}] Finding #{findings_count}",
                    border_style=severity_style.split()[-1] if " " in severity_style else severity_style,
                    box=box.ROUNDED
                ))

                console.print()  # Add spacing between findings


def export_all_findings(findings: List[FindingRecord], format: str, output_path: str):
    """Export all findings to specified format"""
    output_file = Path(output_path)

    if format == "json":
        # Combine all SARIF data
        all_results = []
        for finding in findings:
            if "runs" in finding.sarif_data:
                for run in finding.sarif_data["runs"]:
                    for result in run.get("results", []):
                        result_entry = {
                            "run_id": finding.run_id,
                            "created_at": finding.created_at.isoformat(),
                            **result
                        }
                        all_results.append(result_entry)

        with open(output_file, 'w') as f:
            json.dump({
                "total_findings": len(findings),
                "export_date": datetime.now().isoformat(),
                "results": all_results
            }, f, indent=2)

    elif format == "csv":
        # Export to CSV
        with open(output_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Run ID", "Date", "Severity", "Rule ID", "Message", "File", "Line"])

            for finding in findings:
                if "runs" in finding.sarif_data:
                    for run in finding.sarif_data["runs"]:
                        for result in run.get("results", []):
                            locations = result.get("locations", [])
                            location_info = locations[0] if locations else {}
                            physical = location_info.get("physicalLocation", {})
                            artifact = physical.get("artifactLocation", {})
                            region = physical.get("region", {})

                            writer.writerow([
                                finding.run_id[:12],
                                finding.created_at.strftime("%Y-%m-%d %H:%M"),
                                result.get("level", "note"),
                                result.get("ruleId", ""),
                                result.get("message", {}).get("text", ""),
                                artifact.get("uri", ""),
                                region.get("startLine", "")
                            ])

    elif format == "html":
        # Generate HTML report
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>FuzzForge Security Findings Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .stats {{ background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #4CAF50; color: white; }}
        .error {{ color: red; font-weight: bold; }}
        .warning {{ color: orange; font-weight: bold; }}
        .note {{ color: blue; }}
        .info {{ color: gray; }}
    </style>
</head>
<body>
    <h1>FuzzForge Security Findings Report</h1>
    <div class="stats">
        <p><strong>Generated:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        <p><strong>Total Findings:</strong> {len(findings)}</p>
    </div>
    <table>
        <tr>
            <th>Run ID</th>
            <th>Date</th>
            <th>Severity</th>
            <th>Rule</th>
            <th>Message</th>
            <th>Location</th>
        </tr>"""

        for finding in findings:
            if "runs" in finding.sarif_data:
                for run in finding.sarif_data["runs"]:
                    for result in run.get("results", []):
                        level = result.get("level", "note")
                        locations = result.get("locations", [])
                        location_info = locations[0] if locations else {}
                        physical = location_info.get("physicalLocation", {})
                        artifact = physical.get("artifactLocation", {})
                        region = physical.get("region", {})

                        html_content += f"""
        <tr>
            <td>{finding.run_id[:12]}</td>
            <td>{finding.created_at.strftime("%Y-%m-%d %H:%M")}</td>
            <td class="{level}">{level.upper()}</td>
            <td>{result.get("ruleId", "")}</td>
            <td>{result.get("message", {}).get("text", "")}</td>
            <td>{artifact.get("uri", "")} : {region.get("startLine", "")}</td>
        </tr>"""

        html_content += """
    </table>
</body>
</html>"""

        with open(output_file, 'w') as f:
            f.write(html_content)


@app.callback(invoke_without_command=True)
def findings_callback(ctx: typer.Context):
    """
    🔍 View and export security findings
    """
    # Check if a subcommand is being invoked
    if ctx.invoked_subcommand is not None:
        # Let the subcommand handle it
        return

    # Default to history when no subcommand provided
    findings_history(limit=20)