"""Agent setup and unlink modal screens for FuzzForge TUI.

Provides context-aware modals that receive the target agent directly
from the dashboard row selection — no redundant agent picker needed.

"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, RadioButton, RadioSet

from fuzzforge_cli.commands.mcp import AIAgent
from fuzzforge_cli.tui.helpers import install_agent_config, uninstall_agent_config


class AgentSetupScreen(ModalScreen[str | None]):
    """Modal for linking a specific agent — only asks for engine choice."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, agent: AIAgent, display_name: str) -> None:
        super().__init__()
        self._agent = agent
        self._display_name = display_name

    def compose(self) -> ComposeResult:
        """Compose the setup dialog layout."""
        with Vertical(id="setup-dialog"):
            yield Label(f"Setup {self._display_name}", classes="dialog-title")

            yield Label("Container Engine:", classes="field-label")
            yield RadioSet(
                RadioButton("Docker", value=True),
                RadioButton("Podman"),
                id="engine-select",
            )

            with Horizontal(classes="dialog-buttons"):
                yield Button("Install", variant="primary", id="btn-install")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-install":
            self._do_install()

    def action_cancel(self) -> None:
        """Dismiss the dialog without action."""
        self.dismiss(None)

    def _do_install(self) -> None:
        """Execute the installation."""
        engine_set = self.query_one("#engine-select", RadioSet)
        engine = "docker" if engine_set.pressed_index <= 0 else "podman"
        result = install_agent_config(self._agent, engine, force=True)
        self.dismiss(result)


class AgentUnlinkScreen(ModalScreen[str | None]):
    """Confirmation modal for unlinking a specific agent."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, agent: AIAgent, display_name: str) -> None:
        super().__init__()
        self._agent = agent
        self._display_name = display_name

    def compose(self) -> ComposeResult:
        """Compose the unlink confirmation layout."""
        with Vertical(id="unlink-dialog"):
            yield Label(f"Unlink {self._display_name}?", classes="dialog-title")
            yield Label(
                f"This will remove the FuzzForge MCP configuration from {self._display_name}.",
            )

            with Horizontal(classes="dialog-buttons"):
                yield Button("Unlink", variant="warning", id="btn-unlink")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-unlink":
            result = uninstall_agent_config(self._agent)
            self.dismiss(result)

    def action_cancel(self) -> None:
        """Dismiss without action."""
        self.dismiss(None)
