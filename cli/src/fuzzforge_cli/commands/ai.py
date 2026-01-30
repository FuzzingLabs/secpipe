"""AI integration commands for the FuzzForge CLI."""
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


from __future__ import annotations

import asyncio
import os

import typer
from rich.console import Console


console = Console()
app = typer.Typer(name="ai", help="Interact with the FuzzForge AI system")


@app.command("agent")
def ai_agent() -> None:
    """Launch the full AI agent CLI with A2A orchestration."""
    console.print("[cyan]🤖 Opening Project FuzzForge AI Agent session[/cyan]\n")
    try:
        from fuzzforge_ai.cli import FuzzForgeCLI
        cli = FuzzForgeCLI()
        asyncio.run(cli.run())
    except ImportError as exc:
        console.print(f"[red]Failed to import AI CLI:[/red] {exc}")
        raise typer.Exit(1) from exc


# Memory + health commands
@app.command("status")
def ai_status() -> None:
    """Show AI system health and configuration."""
    # TODO: Implement AI status checking
    # This command is a placeholder for future health monitoring functionality
    console.print("🚧 [yellow]AI status command is not yet implemented.[/yellow]")
    console.print("\nPlanned features:")
    console.print("  • LLM provider connectivity")
    console.print("  • API key validation")
    console.print("  • Registered agents status")
    console.print("  • Memory/session persistence health")
    console.print("\nFor now, use [cyan]ff ai agent[/cyan] to launch the AI agent.")


@app.command("server")
def ai_server(
    port: int = typer.Option(10100, "--port", "-p", help="Server port (default: 10100)"),
) -> None:
    """Start AI system as an A2A server."""
    console.print(f"[cyan]🚀 Starting FuzzForge AI Server on port {port}[/cyan]")
    console.print("[dim]Other agents can register this instance at the A2A endpoint[/dim]\n")

    try:
        os.environ["FUZZFORGE_PORT"] = str(port)
        from fuzzforge_ai.__main__ import main as start_server

        start_server()
    except Exception as exc:  # pragma: no cover
        console.print(f"[red]Failed to start AI server:[/red] {exc}")
        raise typer.Exit(1) from exc


# ---------------------------------------------------------------------------
# Helper functions (largely adapted from the OSS implementation)
# ---------------------------------------------------------------------------


@app.callback(invoke_without_command=True)
def ai_callback(ctx: typer.Context):
    """
    🤖 AI integration features
    """
    # Check if a subcommand is being invoked
    if ctx.invoked_subcommand is not None:
        # Let the subcommand handle it
        return

    # Show not implemented message for default command
    console.print("🚧 [yellow]AI command is not fully implemented yet.[/yellow]")
    console.print("Please use specific subcommands:")
    console.print("  • [cyan]ff ai agent[/cyan] - Launch the full AI agent CLI")
    console.print("  • [cyan]ff ai status[/cyan] - Show AI system health and configuration")
    console.print("  • [cyan]ff ai server[/cyan] - Start AI system as an A2A server")


