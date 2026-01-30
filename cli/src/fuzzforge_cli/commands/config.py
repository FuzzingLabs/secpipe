"""
Configuration management commands.
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


import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm
from rich import box

from ..config import (
    get_project_config,
    get_global_config,
    save_global_config,
    FuzzForgeConfig
)
from ..exceptions import require_project, ValidationError, handle_error

console = Console()
app = typer.Typer()


@app.command("show")
def show_config(
    global_config: bool = typer.Option(
        False, "--global", "-g",
        help="Show global configuration instead of project config"
    )
):
    """
    📋 Display current configuration settings
    """
    if global_config:
        config = get_global_config()
        config_type = "Global"
        config_path = Path.home() / ".config" / "fuzzforge" / "config.yaml"
    else:
        try:
            require_project()
            config = get_project_config()
            if not config:
                raise ValidationError("project configuration", "missing", "initialized project")
        except Exception as e:
            handle_error(e, "loading project configuration")
            return  # Unreachable, but makes static analysis happy
        config_type = "Project"
        config_path = Path.cwd() / ".fuzzforge" / "config.yaml"

    console.print(f"\n⚙️  [bold]{config_type} Configuration[/bold]\n")

    # Project settings
    project_table = Table(show_header=False, box=box.SIMPLE)
    project_table.add_column("Setting", style="bold cyan")
    project_table.add_column("Value")

    project_table.add_row("Project Name", config.project.name)
    project_table.add_row("API URL", config.project.api_url)
    project_table.add_row("Default Timeout", f"{config.project.default_timeout}s")
    if config.project.default_workflow:
        project_table.add_row("Default Workflow", config.project.default_workflow)

    console.print(
        Panel.fit(
            project_table,
            title="📁 Project Settings",
            box=box.ROUNDED
        )
    )

    # Retention settings
    retention_table = Table(show_header=False, box=box.SIMPLE)
    retention_table.add_column("Setting", style="bold cyan")
    retention_table.add_column("Value")

    retention_table.add_row("Max Runs", str(config.retention.max_runs))
    retention_table.add_row("Keep Findings (days)", str(config.retention.keep_findings_days))

    console.print(
        Panel.fit(
            retention_table,
            title="🗄️  Data Retention",
            box=box.ROUNDED
        )
    )

    # Preferences
    prefs_table = Table(show_header=False, box=box.SIMPLE)
    prefs_table.add_column("Setting", style="bold cyan")
    prefs_table.add_column("Value")

    prefs_table.add_row("Auto Save Findings", "✅ Yes" if config.preferences.auto_save_findings else "❌ No")
    prefs_table.add_row("Show Progress Bars", "✅ Yes" if config.preferences.show_progress_bars else "❌ No")
    prefs_table.add_row("Table Style", config.preferences.table_style)
    prefs_table.add_row("Color Output", "✅ Yes" if config.preferences.color_output else "❌ No")

    console.print(
        Panel.fit(
            prefs_table,
            title="🎨 Preferences",
            box=box.ROUNDED
        )
    )

    console.print(f"\n📍 Config file: [dim]{config_path}[/dim]")


@app.command("set")
def set_config(
    key: str = typer.Argument(..., help="Configuration key to set (e.g., 'project.name', 'project.api_url')"),
    value: str = typer.Argument(..., help="Value to set"),
    global_config: bool = typer.Option(
        False, "--global", "-g",
        help="Set in global configuration instead of project config"
    )
):
    """
    ⚙️  Set a configuration value
    """
    if global_config:
        config = get_global_config()
        config_type = "global"
    else:
        config = get_project_config()
        if not config:
            console.print("❌ No project configuration found. Run 'ff init' first.", style="red")
            raise typer.Exit(1)
        config_type = "project"

    # Parse the key path
    key_parts = key.split('.')
    if len(key_parts) != 2:
        console.print("❌ Key must be in format 'section.setting' (e.g., 'project.name')", style="red")
        raise typer.Exit(1)

    section, setting = key_parts

    try:
        # Update configuration
        if section == "project":
            if setting == "name":
                config.project.name = value
            elif setting == "api_url":
                config.project.api_url = value
            elif setting == "default_timeout":
                config.project.default_timeout = int(value)
            elif setting == "default_workflow":
                config.project.default_workflow = value if value.lower() != "none" else None
            else:
                console.print(f"❌ Unknown project setting: {setting}", style="red")
                raise typer.Exit(1)

        elif section == "retention":
            if setting == "max_runs":
                config.retention.max_runs = int(value)
            elif setting == "keep_findings_days":
                config.retention.keep_findings_days = int(value)
            else:
                console.print(f"❌ Unknown retention setting: {setting}", style="red")
                raise typer.Exit(1)

        elif section == "preferences":
            if setting == "auto_save_findings":
                config.preferences.auto_save_findings = value.lower() in ("true", "yes", "1", "on")
            elif setting == "show_progress_bars":
                config.preferences.show_progress_bars = value.lower() in ("true", "yes", "1", "on")
            elif setting == "table_style":
                config.preferences.table_style = value
            elif setting == "color_output":
                config.preferences.color_output = value.lower() in ("true", "yes", "1", "on")
            else:
                console.print(f"❌ Unknown preferences setting: {setting}", style="red")
                raise typer.Exit(1)

        else:
            console.print(f"❌ Unknown configuration section: {section}", style="red")
            console.print("Valid sections: project, retention, preferences", style="dim")
            raise typer.Exit(1)

        # Save configuration
        if global_config:
            save_global_config(config)
        else:
            config_path = Path.cwd() / ".fuzzforge" / "config.yaml"
            config.save_to_file(config_path)

        console.print(f"✅ Set {config_type} configuration: [bold cyan]{key}[/bold cyan] = [bold]{value}[/bold]", style="green")

    except ValueError as e:
        console.print(f"❌ Invalid value for {key}: {e}", style="red")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"❌ Failed to set configuration: {e}", style="red")
        raise typer.Exit(1)


@app.command("get")
def get_config(
    key: str = typer.Argument(..., help="Configuration key to get (e.g., 'project.name')"),
    global_config: bool = typer.Option(
        False, "--global", "-g",
        help="Get from global configuration instead of project config"
    )
):
    """
    📖 Get a specific configuration value
    """
    if global_config:
        config = get_global_config()
    else:
        config = get_project_config()
        if not config:
            console.print("❌ No project configuration found. Run 'ff init' first.", style="red")
            raise typer.Exit(1)

    # Parse the key path
    key_parts = key.split('.')
    if len(key_parts) != 2:
        console.print("❌ Key must be in format 'section.setting' (e.g., 'project.name')", style="red")
        raise typer.Exit(1)

    section, setting = key_parts

    try:
        # Get configuration value
        if section == "project":
            if setting == "name":
                value = config.project.name
            elif setting == "api_url":
                value = config.project.api_url
            elif setting == "default_timeout":
                value = config.project.default_timeout
            elif setting == "default_workflow":
                value = config.project.default_workflow or "none"
            else:
                console.print(f"❌ Unknown project setting: {setting}", style="red")
                raise typer.Exit(1)

        elif section == "retention":
            if setting == "max_runs":
                value = config.retention.max_runs
            elif setting == "keep_findings_days":
                value = config.retention.keep_findings_days
            else:
                console.print(f"❌ Unknown retention setting: {setting}", style="red")
                raise typer.Exit(1)

        elif section == "preferences":
            if setting == "auto_save_findings":
                value = config.preferences.auto_save_findings
            elif setting == "show_progress_bars":
                value = config.preferences.show_progress_bars
            elif setting == "table_style":
                value = config.preferences.table_style
            elif setting == "color_output":
                value = config.preferences.color_output
            else:
                console.print(f"❌ Unknown preferences setting: {setting}", style="red")
                raise typer.Exit(1)

        else:
            console.print(f"❌ Unknown configuration section: {section}", style="red")
            raise typer.Exit(1)

        console.print(f"{key}: [bold cyan]{value}[/bold cyan]")

    except Exception as e:
        console.print(f"❌ Failed to get configuration: {e}", style="red")
        raise typer.Exit(1)


@app.command("reset")
def reset_config(
    global_config: bool = typer.Option(
        False, "--global", "-g",
        help="Reset global configuration instead of project config"
    ),
    force: bool = typer.Option(
        False, "--force", "-f",
        help="Skip confirmation prompt"
    )
):
    """
    🔄 Reset configuration to defaults
    """
    config_type = "global" if global_config else "project"

    if not force:
        if not Confirm.ask(f"Reset {config_type} configuration to defaults?", default=False, console=console):
            console.print("❌ Reset cancelled", style="yellow")
            raise typer.Exit(0)

    try:
        # Create new default configuration
        new_config = FuzzForgeConfig()

        if global_config:
            save_global_config(new_config)
        else:
            if not Path.cwd().joinpath(".fuzzforge").exists():
                console.print("❌ No project configuration found. Run 'ff init' first.", style="red")
                raise typer.Exit(1)

            config_path = Path.cwd() / ".fuzzforge" / "config.yaml"
            new_config.save_to_file(config_path)

        console.print(f"✅ {config_type.title()} configuration reset to defaults", style="green")

    except Exception as e:
        console.print(f"❌ Failed to reset configuration: {e}", style="red")
        raise typer.Exit(1)


@app.command("edit")
def edit_config(
    global_config: bool = typer.Option(
        False, "--global", "-g",
        help="Edit global configuration instead of project config"
    )
):
    """
    📝 Open configuration file in default editor
    """
    import subprocess

    if global_config:
        config_path = Path.home() / ".config" / "fuzzforge" / "config.yaml"
        config_type = "global"
    else:
        config_path = Path.cwd() / ".fuzzforge" / "config.yaml"
        config_type = "project"

        if not config_path.exists():
            console.print("❌ No project configuration found. Run 'ff init' first.", style="red")
            raise typer.Exit(1)

    # Try to find a suitable editor
    editors = ["code", "vim", "nano", "notepad"]
    editor = None

    for e in editors:
        try:
            subprocess.run([e, "--version"], capture_output=True, check=True)
            editor = e
            break
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue

    if not editor:
        console.print(f"📍 Configuration file: [bold cyan]{config_path}[/bold cyan]")
        console.print("❌ No suitable editor found. Please edit the file manually.", style="red")
        raise typer.Exit(1)

    try:
        console.print(f"📝 Opening {config_type} configuration in {editor}...")
        subprocess.run([editor, str(config_path)], check=True)
        console.print("✅ Configuration file edited", style="green")

    except subprocess.CalledProcessError as e:
        console.print(f"❌ Failed to open editor: {e}", style="red")
        raise typer.Exit(1)


@app.callback()
def config_callback():
    """
    ⚙️  Manage configuration settings
    """
    pass
