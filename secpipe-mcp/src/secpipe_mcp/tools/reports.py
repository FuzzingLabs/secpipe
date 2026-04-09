"""Report generation tools for SecPipe MCP."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from secpipe_mcp.dependencies import get_project_path, get_storage

mcp: FastMCP = FastMCP()

# Maximum characters of tool output to embed per execution in markdown reports.
_OUTPUT_TRUNCATE_CHARS: int = 2000


# ------------------------------------------------------------------
# Formatting helpers
# ------------------------------------------------------------------


def _format_size(size: int) -> str:
    """Format a byte count as a human-friendly string."""
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:  # noqa: PLR2004
            return f"{size} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size //= 1024
    return f"{size:.1f} TB"


def _truncate(text: str, max_chars: int = _OUTPUT_TRUNCATE_CHARS) -> str:
    """Truncate text and append an indicator when truncated."""
    if len(text) <= max_chars:
        return text
    omitted = len(text) - max_chars
    return text[:max_chars] + f"\n... [{omitted} chars omitted]"


def _extract_output_text(result: dict[str, Any]) -> str:
    """Extract a human-readable output string from an execution result dict.

    Handles both flat dicts (``{"output": "..."}`` or ``{"content": [...]}``),
    and the nested format stored by ``record_execution`` where the MCP tool
    response is stored one level deeper under the ``"result"`` key.
    """
    # Flat output field (most hub tools set this)
    output = result.get("output", "")
    if output and isinstance(output, str):
        return output

    # MCP content list format — check both at this level and one level down
    for candidate in (result, result.get("result") or {}):
        content = candidate.get("content", [])
        if isinstance(content, list):
            texts = [item.get("text", "") for item in content if isinstance(item, dict)]
            combined = "\n".join(t for t in texts if t)
            if combined:
                return combined

    parts: list[str] = []
    if result.get("stdout"):
        parts.append(f"stdout:\n{result['stdout']}")
    if result.get("stderr"):
        parts.append(f"stderr:\n{result['stderr']}")
    return "\n".join(parts)


# ------------------------------------------------------------------
# Report builders
# ------------------------------------------------------------------


def _report_header(
    title: str,
    project_path: Path,
    assets_path: Path | None,
    now: str,
) -> list[str]:
    """Build the header block of the Markdown report."""
    lines = [
        f"# {title}",
        "",
        f"**Generated:** {now}  ",
        f"**Project:** `{project_path}`  ",
    ]
    if assets_path:
        lines.append(f"**Assets:** `{assets_path}`  ")
    lines += ["", "---", ""]
    return lines


def _report_summary(
    executions: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
) -> list[str]:
    """Build the summary table block of the Markdown report."""
    success_count = sum(1 for e in executions if e.get("success"))
    fail_count = len(executions) - success_count
    tool_ids = list(dict.fromkeys(
        f"{e.get('server', '?')}:{e.get('tool', '?')}" for e in executions
    ))
    timestamps = [e["timestamp"] for e in executions if e.get("timestamp")]

    lines = [
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total executions | {len(executions)} |",
        f"| Successful | {success_count} |",
        f"| Failed | {fail_count} |",
        f"| Artifacts produced | {len(artifacts)} |",
        f"| Unique tools | {len(set(tool_ids))} |",
    ]
    if len(timestamps) >= 2:  # noqa: PLR2004
        lines.append(f"| Time range | {timestamps[0]} → {timestamps[-1]} |")
    elif timestamps:
        lines.append(f"| Time | {timestamps[0]} |")
    lines.append("")

    if tool_ids:
        lines += [", ".join(f"`{t}`" for t in tool_ids), ""]
        lines[-2] = f"**Tools used:** {lines[-2]}"

    lines += ["---", ""]
    return lines


def _report_timeline(
    executions: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
) -> list[str]:
    """Build the execution timeline block of the Markdown report."""
    if not executions:
        return []

    lines: list[str] = ["## Execution Timeline", ""]
    for idx, meta in enumerate(executions, 1):
        server = meta.get("server", "unknown")
        tool = meta.get("tool", "unknown")
        ts = meta.get("timestamp", "")
        status = "✓ Success" if meta.get("success") else "✗ Failed"

        lines.append(f"### [{idx}] {server} :: {tool} — {ts}")
        lines += ["", f"- **Status:** {status}"]

        arguments = meta.get("arguments") or {}
        if arguments:
            lines.append("- **Arguments:**")
            for k, v in arguments.items():
                lines.append(f"  - `{k}`: `{v}`")

        result = meta.get("result") or {}
        output_text = _extract_output_text(result).strip()
        if output_text:
            truncated = _truncate(output_text)
            lines += ["- **Output:**", "  ```"]
            lines.extend(f"  {line}" for line in truncated.splitlines())
            lines.append("  ```")

        exec_artifacts = [
            a for a in artifacts
            if a.get("source_server") == server and a.get("source_tool") == tool
        ]
        if exec_artifacts:
            lines.append(f"- **Artifacts produced:** {len(exec_artifacts)} file(s)")

        lines.append("")
    return lines


def _report_artifacts(artifacts: list[dict[str, Any]]) -> list[str]:
    """Build the artifacts section of the Markdown report."""
    if not artifacts:
        return []

    lines: list[str] = ["---", "", "## Artifacts", "", f"**{len(artifacts)} file(s) total**", ""]

    by_type: dict[str, list[dict[str, Any]]] = {}
    for a in artifacts:
        by_type.setdefault(a.get("type", "unknown"), []).append(a)

    for art_type, arts in sorted(by_type.items()):
        lines += [
            f"### {art_type} ({len(arts)})",
            "",
            "| Path | Size | Source |",
            "|------|------|--------|",
        ]
        for a in arts:
            path = a.get("path", "")
            size = _format_size(a.get("size", 0))
            source = f"`{a.get('source_server', '?')}:{a.get('source_tool', '?')}`"
            lines.append(f"| `{path}` | {size} | {source} |")
        lines.append("")
    return lines


def _build_markdown_report(
    title: str,
    project_path: Path,
    assets_path: Path | None,
    executions: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
) -> str:
    """Build a Markdown-formatted analysis report."""
    now = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines: list[str] = (
        _report_header(title, project_path, assets_path, now)
        + _report_summary(executions, artifacts)
        + _report_timeline(executions, artifacts)
        + _report_artifacts(artifacts)
        + ["---", "", "*Generated by SecPipe*", ""]
    )
    return "\n".join(lines)


def _build_json_report(
    title: str,
    project_path: Path,
    assets_path: Path | None,
    executions: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
) -> str:
    """Build a JSON-formatted analysis report."""
    success_count = sum(1 for e in executions if e.get("success"))
    report = {
        "title": title,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "project_path": str(project_path),
        "assets_path": str(assets_path) if assets_path else None,
        "summary": {
            "total_executions": len(executions),
            "successful": success_count,
            "failed": len(executions) - success_count,
            "artifact_count": len(artifacts),
        },
        "executions": executions,
        "artifacts": artifacts,
    }
    return json.dumps(report, indent=2, default=str)


def _write_to_path(content: str, path: Path) -> None:
    """Write report content to an explicit output path (sync helper)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


# ------------------------------------------------------------------
# MCP tools
# ------------------------------------------------------------------


@mcp.tool
async def generate_report(
    title: str | None = None,
    report_format: str = "markdown",
    output_path: str | None = None,
) -> dict[str, Any]:
    """Generate a comprehensive analysis report for the current project.

    Aggregates all execution history, tool outputs, and tracked artifacts
    into a structured report. The report is saved to `.secpipe/reports/`
    and its content is returned so the agent can read it immediately.

    :param title: Optional report title. Defaults to the project folder name.
    :param report_format: Output format — ``"markdown"`` (default) or ``"json"``.
    :param output_path: Optional absolute path to save the report. When omitted,
        the report is saved automatically to `.secpipe/reports/`.
    :return: Report content, save path, and counts of included items.

    """
    storage = get_storage()
    project_path = get_project_path()

    try:
        fmt = report_format.lower().strip()
        if fmt not in ("markdown", "json"):
            return {
                "success": False,
                "error": f"Unsupported format '{fmt}'. Use 'markdown' or 'json'.",
            }

        executions = storage.list_execution_metadata(project_path)
        artifacts = storage.list_artifacts(project_path)
        assets_path = storage.get_project_assets_path(project_path)

        resolved_title = title or f"SecPipe Analysis Report — {project_path.name}"

        if fmt == "json":
            content = _build_json_report(
                resolved_title, project_path, assets_path, executions, artifacts
            )
        else:
            content = _build_markdown_report(
                resolved_title, project_path, assets_path, executions, artifacts
            )

        if output_path:
            save_path = Path(output_path)
            _write_to_path(content, save_path)
        else:
            save_path = storage.save_report(project_path, content, fmt)

        return {
            "success": True,
            "report_path": str(save_path),
            "format": fmt,
            "executions_included": len(executions),
            "artifacts_included": len(artifacts),
            "content": content,
        }

    except Exception as exception:
        message: str = f"Failed to generate report: {exception}"
        raise ToolError(message) from exception


@mcp.tool
async def list_reports() -> dict[str, Any]:
    """List all generated reports for the current project.

    Reports are stored in `.secpipe/reports/` and are ordered newest-first.

    :return: List of report files with filename, path, size, and creation time.

    """
    storage = get_storage()
    project_path = get_project_path()

    try:
        reports = storage.list_reports(project_path)
        return {
            "success": True,
            "reports": reports,
            "count": len(reports),
        }

    except Exception as exception:
        message: str = f"Failed to list reports: {exception}"
        raise ToolError(message) from exception
