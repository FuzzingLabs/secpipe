"""
Workflow management commands.
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
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich import box
from typing import Optional

from ..config import get_project_config, FuzzForgeConfig
from ..fuzzy import enhanced_workflow_not_found_handler
from fuzzforge_sdk import FuzzForgeClient

console = Console()
app = typer.Typer()


def get_client() -> FuzzForgeClient:
    """Get configured FuzzForge client"""
    config = get_project_config() or FuzzForgeConfig()
    return FuzzForgeClient(base_url=config.get_api_url(), timeout=config.get_timeout())


@app.command("list")
def list_workflows():
    """
    📋 List all available security testing workflows
    """
    try:
        with get_client() as client:
            workflows = client.list_workflows()

        if not workflows:
            console.print("❌ No workflows available", style="red")
            return

        table = Table(box=box.ROUNDED)
        table.add_column("Name", style="bold cyan")
        table.add_column("Version", justify="center")
        table.add_column("Description")
        table.add_column("Tags", style="dim")

        for workflow in workflows:
            tags_str = ", ".join(workflow.tags) if workflow.tags else ""
            table.add_row(
                workflow.name,
                workflow.version,
                workflow.description,
                tags_str
            )

        console.print(f"\n🔧 [bold]Available Workflows ({len(workflows)})[/bold]\n")
        console.print(table)

        console.print("\n💡 Use [bold cyan]fuzzforge workflows info <name>[/bold cyan] for detailed information")

    except Exception as e:
        console.print(f"❌ Failed to fetch workflows: {e}", style="red")
        raise typer.Exit(1)


@app.command("info")
def workflow_info(
    name: str = typer.Argument(..., help="Workflow name to get information about")
):
    """
    📋 Show detailed information about a specific workflow
    """
    try:
        with get_client() as client:
            workflow = client.get_workflow_metadata(name)

        console.print(f"\n🔧 [bold]Workflow: {workflow.name}[/bold]\n")

        # Basic information
        info_table = Table(show_header=False, box=box.SIMPLE)
        info_table.add_column("Property", style="bold cyan")
        info_table.add_column("Value")

        info_table.add_row("Name", workflow.name)
        info_table.add_row("Version", workflow.version)
        info_table.add_row("Description", workflow.description)
        if workflow.author:
            info_table.add_row("Author", workflow.author)
        if workflow.tags:
            info_table.add_row("Tags", ", ".join(workflow.tags))
        info_table.add_row("Custom Docker", "✅ Yes" if workflow.has_custom_docker else "❌ No")

        console.print(
            Panel.fit(
                info_table,
                title="ℹ️  Basic Information",
                box=box.ROUNDED
            )
        )

        # Parameters
        if workflow.parameters:
            console.print("\n📝 [bold]Parameters Schema[/bold]")

            param_table = Table(box=box.ROUNDED)
            param_table.add_column("Parameter", style="bold")
            param_table.add_column("Type", style="cyan")
            param_table.add_column("Required", justify="center")
            param_table.add_column("Default")
            param_table.add_column("Description", style="dim")

            # Extract parameter information from JSON schema
            properties = workflow.parameters.get("properties", {})
            required_params = set(workflow.parameters.get("required", []))
            defaults = workflow.default_parameters

            for param_name, param_schema in properties.items():
                param_type = param_schema.get("type", "unknown")
                is_required = "✅" if param_name in required_params else "❌"
                default_val = str(defaults.get(param_name, "")) if param_name in defaults else ""
                description = param_schema.get("description", "")

                # Handle array types
                if param_type == "array":
                    items_type = param_schema.get("items", {}).get("type", "unknown")
                    param_type = f"array[{items_type}]"

                param_table.add_row(
                    param_name,
                    param_type,
                    is_required,
                    default_val[:30] + "..." if len(default_val) > 30 else default_val,
                    description[:50] + "..." if len(description) > 50 else description
                )

            console.print(param_table)

        # Required modules
        if workflow.required_modules:
            console.print(f"\n🔧 [bold]Required Modules:[/bold] {', '.join(workflow.required_modules)}")

        console.print(f"\n💡 Use [bold cyan]fuzzforge workflows parameters {name}[/bold cyan] for interactive parameter builder")

    except Exception as e:
        error_message = str(e)
        if "not found" in error_message.lower() or "404" in error_message:
            # Try fuzzy matching for workflow name
            enhanced_workflow_not_found_handler(name)
        else:
            console.print(f"❌ Failed to get workflow info: {e}", style="red")
        raise typer.Exit(1)


@app.command("parameters")
def workflow_parameters(
    name: str = typer.Argument(..., help="Workflow name"),
    output_file: Optional[str] = typer.Option(
        None, "--output", "-o",
        help="Save parameters to JSON file"
    ),
    interactive: bool = typer.Option(
        True, "--interactive/--no-interactive", "-i/-n",
        help="Interactive parameter builder"
    )
):
    """
    📝 Interactive parameter builder for workflows
    """
    try:
        with get_client() as client:
            workflow = client.get_workflow_metadata(name)
            param_response = client.get_workflow_parameters(name)

        console.print(f"\n📝 [bold]Parameter Builder: {name}[/bold]\n")

        if not workflow.parameters.get("properties"):
            console.print("ℹ️  This workflow has no configurable parameters")
            return

        parameters = {}
        properties = workflow.parameters.get("properties", {})
        required_params = set(workflow.parameters.get("required", []))
        defaults = param_response.default_parameters

        if interactive:
            console.print("🔧 Enter parameter values (press Enter for default):\n")

            for param_name, param_schema in properties.items():
                param_type = param_schema.get("type", "string")
                description = param_schema.get("description", "")
                is_required = param_name in required_params
                default_value = defaults.get(param_name)

                # Build prompt
                prompt_text = f"{param_name}"
                if description:
                    prompt_text += f" ({description})"
                if param_type:
                    prompt_text += f" [{param_type}]"
                if is_required:
                    prompt_text += " [bold red]*required*[/bold red]"

                # Get user input
                while True:
                    if default_value is not None:
                        user_input = Prompt.ask(
                            prompt_text,
                            default=str(default_value),
                            console=console
                        )
                    else:
                        user_input = Prompt.ask(
                            prompt_text,
                            console=console
                        )

                    # Validate and convert input
                    if user_input.strip() == "" and not is_required:
                        break

                    if user_input.strip() == "" and is_required:
                        console.print("❌ This parameter is required", style="red")
                        continue

                    try:
                        # Type conversion
                        if param_type == "integer":
                            parameters[param_name] = int(user_input)
                        elif param_type == "number":
                            parameters[param_name] = float(user_input)
                        elif param_type == "boolean":
                            parameters[param_name] = user_input.lower() in ("true", "yes", "1", "on")
                        elif param_type == "array":
                            # Simple comma-separated array
                            parameters[param_name] = [item.strip() for item in user_input.split(",") if item.strip()]
                        else:
                            parameters[param_name] = user_input

                        break

                    except ValueError as e:
                        console.print(f"❌ Invalid {param_type}: {e}", style="red")

            # Show summary
            console.print("\n📋 [bold]Parameter Summary:[/bold]")
            summary_table = Table(show_header=False, box=box.SIMPLE)
            summary_table.add_column("Parameter", style="cyan")
            summary_table.add_column("Value", style="white")

            for key, value in parameters.items():
                summary_table.add_row(key, str(value))

            console.print(summary_table)

        else:
            # Non-interactive mode - show schema
            console.print("📋 Parameter Schema:")
            schema_json = json.dumps(workflow.parameters, indent=2)
            console.print(Syntax(schema_json, "json", theme="monokai"))

            if defaults:
                console.print("\n📋 Default Values:")
                defaults_json = json.dumps(defaults, indent=2)
                console.print(Syntax(defaults_json, "json", theme="monokai"))

        # Save to file if requested
        if output_file:
            if parameters or not interactive:
                data_to_save = parameters if interactive else {"schema": workflow.parameters, "defaults": defaults}
                with open(output_file, 'w') as f:
                    json.dump(data_to_save, f, indent=2)
                console.print(f"\n💾 Parameters saved to: {output_file}")
            else:
                console.print("\n❌ No parameters to save", style="red")

    except Exception as e:
        console.print(f"❌ Failed to build parameters: {e}", style="red")
        raise typer.Exit(1)


@app.callback(invoke_without_command=True)
def workflows_callback(ctx: typer.Context):
    """
    🔧 Manage security testing workflows
    """
    # Check if a subcommand is being invoked
    if ctx.invoked_subcommand is not None:
        # Let the subcommand handle it
        return

    # Default to list when no subcommand provided
    list_workflows()