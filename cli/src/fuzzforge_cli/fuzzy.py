"""
Fuzzy matching and smart suggestions for FuzzForge CLI.

Provides "Did you mean...?" functionality and intelligent command/parameter suggestions.
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

import difflib
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


class FuzzyMatcher:
    """Fuzzy matching engine for CLI commands and parameters."""

    def __init__(self):
        # Known commands and subcommands
        self.commands = {
            "init": ["project"],
            "workflows": ["list", "info"],
            "runs": ["submit", "status", "list", "rerun"],
            "findings": ["get", "list", "export", "all"],
            "config": ["set", "get", "list", "init"],
            "ai": ["ask", "summarize", "explain"],
            "ingest": ["project", "findings"],
        }

        # Common workflow names
        self.workflow_names = [
            "security_assessment",
            "language_fuzzing",
            "infrastructure_scan",
            "static_analysis_scan",
            "penetration_testing_scan",
            "secret_detection_scan",
        ]

        # Common parameter names
        self.parameter_names = [
            "target_path",
            "volume_mode",
            "timeout",
            "workflow",
            "param",
            "param-file",
            "interactive",
            "wait",
            "format",
            "output",
            "severity",
            "since",
            "limit",
            "stats",
            "export",
        ]

        # Common values
        self.common_values = {
            "volume_mode": ["ro", "rw"],
            "format": ["json", "csv", "html", "sarif"],
            "severity": ["critical", "high", "medium", "low", "info"],
        }

    def find_closest_command(
        self, user_input: str, command_group: Optional[str] = None
    ) -> Optional[Tuple[str, float]]:
        """Find the closest matching command."""
        if command_group and command_group in self.commands:
            # Search within a specific command group
            candidates = self.commands[command_group]
        else:
            # Search all main commands
            candidates = list(self.commands.keys())

        matches = difflib.get_close_matches(user_input, candidates, n=1, cutoff=0.6)

        if matches:
            match = matches[0]
            # Calculate similarity ratio
            ratio = difflib.SequenceMatcher(None, user_input, match).ratio()
            return match, ratio

        return None

    def find_closest_workflow(self, user_input: str) -> Optional[Tuple[str, float]]:
        """Find the closest matching workflow name."""
        matches = difflib.get_close_matches(
            user_input, self.workflow_names, n=1, cutoff=0.6
        )

        if matches:
            match = matches[0]
            ratio = difflib.SequenceMatcher(None, user_input, match).ratio()
            return match, ratio

        return None

    def find_closest_parameter(self, user_input: str) -> Optional[Tuple[str, float]]:
        """Find the closest matching parameter name."""
        # Remove leading dashes
        clean_input = user_input.lstrip("-")

        matches = difflib.get_close_matches(
            clean_input, self.parameter_names, n=1, cutoff=0.6
        )

        if matches:
            match = matches[0]
            ratio = difflib.SequenceMatcher(None, clean_input, match).ratio()
            return match, ratio

        return None

    def suggest_parameter_values(self, parameter: str, user_input: str) -> List[str]:
        """Suggest parameter values based on known options."""
        if parameter in self.common_values:
            values = self.common_values[parameter]
            if user_input:
                # Filter values that start with user input
                return [v for v in values if v.startswith(user_input.lower())]
            else:
                return values

        return []

    def get_command_suggestions(
        self, user_command: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Get suggestions for a user command that may have typos."""
        if not user_command:
            return None

        suggestions = {"type": None, "original": user_command, "suggestions": []}

        # Check main command
        main_cmd = user_command[0]
        if main_cmd not in self.commands:
            closest = self.find_closest_command(main_cmd)
            if closest:
                match, confidence = closest
                suggestions["type"] = "main_command"
                suggestions["suggestions"].append(
                    {"text": match, "confidence": confidence, "type": "command"}
                )

        # Check subcommand if present
        elif len(user_command) > 1:
            sub_cmd = user_command[1]
            if main_cmd in self.commands and sub_cmd not in self.commands[main_cmd]:
                closest = self.find_closest_command(sub_cmd, main_cmd)
                if closest:
                    match, confidence = closest
                    suggestions["type"] = "subcommand"
                    suggestions["suggestions"].append(
                        {
                            "text": f"{main_cmd} {match}",
                            "confidence": confidence,
                            "type": "subcommand",
                        }
                    )

        return suggestions if suggestions["suggestions"] else None

    def suggest_workflow_fix(self, user_workflow: str) -> Optional[str]:
        """Suggest a workflow name correction."""
        closest = self.find_closest_workflow(user_workflow)
        if closest:
            match, confidence = closest
            if confidence > 0.6:  # Only suggest if reasonably confident
                return match
        return None


def display_command_suggestion(suggestions: Dict[str, Any]):
    """Display command suggestions to the user."""
    if not suggestions or not suggestions["suggestions"]:
        return

    original = " ".join(suggestions["original"])
    suggestion_type = suggestions["type"]

    # Create suggestion text
    text = Text()
    text.append("❓ Command not found: ", style="red")
    text.append(f"'{original}'", style="bold red")
    text.append("\n\n")

    text.append("💡 Did you mean:\n", style="yellow")

    for i, suggestion in enumerate(suggestions["suggestions"], 1):
        confidence_percent = int(suggestion["confidence"] * 100)
        text.append(f"  {i}. ", style="bold cyan")
        text.append(f"{suggestion['text']}", style="bold white")
        text.append(f" ({confidence_percent}% match)", style="dim")
        text.append("\n")

    # Add helpful context
    if suggestion_type == "main_command":
        text.append(
            "\n💡 Use 'fuzzforge --help' to see all available commands", style="dim"
        )
    elif suggestion_type == "subcommand":
        main_cmd = suggestions["original"][0]
        text.append(
            f"\n💡 Use 'fuzzforge {main_cmd} --help' to see available subcommands",
            style="dim",
        )

    console.print(
        Panel(text, title="🤔 Command Suggestion", border_style="yellow", expand=False)
    )


def display_workflow_suggestion(original: str, suggestion: str):
    """Display workflow name suggestion."""
    text = Text()
    text.append("❓ Workflow not found: ", style="red")
    text.append(f"'{original}'", style="bold red")
    text.append("\n\n")

    text.append("💡 Did you mean: ", style="yellow")
    text.append(f"'{suggestion}'", style="bold green")
    text.append("?\n\n")

    text.append(
        "💡 Use 'fuzzforge workflows' to see all available workflows", style="dim"
    )

    console.print(
        Panel(text, title="🔧 Workflow Suggestion", border_style="yellow", expand=False)
    )


def display_parameter_suggestion(original: str, suggestion: str):
    """Display parameter name suggestion."""
    text = Text()
    text.append("❓ Unknown parameter: ", style="red")
    text.append(f"'{original}'", style="bold red")
    text.append("\n\n")

    text.append("💡 Did you mean: ", style="yellow")
    text.append(f"'--{suggestion}'", style="bold green")
    text.append("?\n\n")

    text.append("💡 Use '--help' to see all available parameters", style="dim")

    console.print(
        Panel(text, title="⚙️ Parameter Suggestion", border_style="yellow", expand=False)
    )


def enhanced_command_not_found_handler(command_parts: List[str]):
    """Handle command not found with fuzzy matching suggestions."""
    matcher = FuzzyMatcher()
    suggestions = matcher.get_command_suggestions(command_parts)

    if suggestions:
        display_command_suggestion(suggestions)
    else:
        # Fallback to generic help
        console.print("❌ [red]Command not found[/red]")
        console.print("💡 Use 'fuzzforge --help' to see available commands")


def enhanced_workflow_not_found_handler(workflow_name: str):
    """Handle workflow not found with suggestions."""
    matcher = FuzzyMatcher()
    suggestion = matcher.suggest_workflow_fix(workflow_name)

    if suggestion:
        display_workflow_suggestion(workflow_name, suggestion)
    else:
        console.print(f"❌ [red]Workflow '{workflow_name}' not found[/red]")
        console.print("💡 Use 'fuzzforge workflows' to see available workflows")


def enhanced_parameter_not_found_handler(parameter_name: str):
    """Handle unknown parameter with suggestions."""
    matcher = FuzzyMatcher()
    closest = matcher.find_closest_parameter(parameter_name)

    if closest:
        match, confidence = closest
        if confidence > 0.6:
            display_parameter_suggestion(parameter_name, match)
            return

    console.print(f"❌ [red]Unknown parameter: '{parameter_name}'[/red]")
    console.print("💡 Use '--help' to see available parameters")


# Global fuzzy matcher instance
fuzzy_matcher = FuzzyMatcher()
