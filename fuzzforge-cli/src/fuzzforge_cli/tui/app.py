"""FuzzForge TUI application.

Main terminal user interface for FuzzForge, providing a dashboard
with AI agent connection status, hub server availability, and
hub management capabilities.

"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, DataTable, Footer, Header

from fuzzforge_cli.tui.helpers import (
    check_agent_status,
    check_hub_image,
    find_fuzzforge_root,
    get_agent_configs,
    load_hub_config,
)

if TYPE_CHECKING:
    from fuzzforge_cli.commands.mcp import AIAgent

# Agent config entries stored alongside their linked status for row mapping
_AgentRow = tuple[str, "AIAgent", Path, str, bool]


class FuzzForgeApp(App[None]):
    """FuzzForge AI terminal user interface."""

    TITLE = "FuzzForge AI"
    SUB_TITLE = "Security Research Orchestration"

    CSS = """
    Screen {
        background: $surface;
    }

    #main {
        height: 1fr;
        margin: 1 2;
    }

    .panel {
        width: 1fr;
        border: round #4699fc;
        padding: 1 2;
        margin: 0 0 1 0;
    }

    #hub-panel {
        height: 12;
    }

    #hub-table {
        height: 1fr;
    }

    #agents-panel {
        height: auto;
    }

    .panel-title {
        text-style: bold;
        color: #4699fc;
        text-align: left;
        margin-bottom: 1;
    }

    #hub-title-bar {
        height: auto;
        align: center middle;
        margin: 0 0 1 0;
    }

    #btn-hub-manager {
        min-width: 40;
        margin-right: 2;
    }

    #btn-fuzzinglabs-hub {
        min-width: 30;
    }

    #agents-table {
        height: auto;
    }

    /* Modal screens */
    AgentSetupScreen, AgentUnlinkScreen,
    HubManagerScreen, LinkHubScreen, CloneHubScreen,
    BuildImageScreen {
        align: center middle;
    }

    #setup-dialog, #unlink-dialog {
        width: 56;
        height: auto;
        max-height: 80%;
        border: thick #4699fc;
        background: $surface;
        padding: 2 3;
        overflow-y: auto;
    }

    #hub-manager-dialog {
        width: 100;
        height: auto;
        max-height: 85%;
        border: thick #4699fc;
        background: $surface;
        padding: 2 3;
        overflow-y: auto;
    }

    #link-dialog, #clone-dialog {
        width: 72;
        height: auto;
        max-height: 80%;
        border: thick #4699fc;
        background: $surface;
        padding: 2 3;
        overflow-y: auto;
    }

    #build-dialog {
        width: 100;
        height: 80%;
        border: thick #4699fc;
        background: $surface;
        padding: 2 3;
    }

    #build-log {
        height: 1fr;
        border: round $panel;
        margin: 1 0;
    }

    #build-subtitle {
        color: $text-muted;
        margin-bottom: 1;
    }

    #build-status {
        height: 1;
        margin-top: 1;
    }

    .dialog-title {
        text-style: bold;
        text-align: center;
        color: #4699fc;
        margin-bottom: 1;
    }

    .field-label {
        margin-top: 1;
        text-style: bold;
    }

    RadioSet {
        height: auto;
        margin: 0 0 1 2;
    }

    Input {
        margin: 0 0 1 0;
    }

    .dialog-buttons {
        layout: horizontal;
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    .dialog-buttons Button {
        margin: 0 1;
        min-width: 14;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("h", "manage_hubs", "Hub Manager"),
        Binding("r", "refresh", "Refresh"),
        Binding("enter", "select_row", "Select", show=False),
    ]

    def compose(self) -> ComposeResult:
        """Compose the dashboard layout."""
        yield Header()
        with VerticalScroll(id="main"):
            with Vertical(id="hub-panel", classes="panel"):
                yield DataTable(id="hub-table")
            with Horizontal(id="hub-title-bar"):
                yield Button(
                    "Hub Manager (h)",
                    variant="primary",
                    id="btn-hub-manager",
                )
                yield Button(
                    "FuzzingLabs Hub",
                    variant="primary",
                    id="btn-fuzzinglabs-hub",
                )
            with Vertical(id="agents-panel", classes="panel"):
                yield DataTable(id="agents-table")
        yield Footer()

    def on_mount(self) -> None:
        """Populate tables on startup."""
        self._agent_rows: list[_AgentRow] = []
        # hub row data: (server_name, image, hub_name) | None for group headers
        self._hub_rows: list[tuple[str, str, str] | None] = []
        self.query_one("#hub-panel").border_title = "Hub Servers  [dim](Enter to build)[/dim]"
        self.query_one("#agents-panel").border_title = "AI Agents"
        self._refresh_agents()
        self._refresh_hub()

    def _refresh_agents(self) -> None:
        """Refresh the AI agents status table."""
        table = self.query_one("#agents-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Agent", "Status", "Config Path")
        table.cursor_type = "row"

        self._agent_rows = []
        for display_name, agent, config_path, servers_key in get_agent_configs():
            is_linked, status_text = check_agent_status(config_path, servers_key)
            if is_linked:
                status_cell = Text(f"✓ {status_text}", style="green")
            else:
                status_cell = Text(f"✗ {status_text}", style="red")
            table.add_row(display_name, status_cell, str(config_path))
            self._agent_rows.append(
                (display_name, agent, config_path, servers_key, is_linked)
            )

    def _refresh_hub(self) -> None:
        """Refresh the hub servers table, grouped by source hub."""
        self._hub_rows = []
        table = self.query_one("#hub-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Server", "Image", "Hub", "Status")

        try:
            fuzzforge_root = find_fuzzforge_root()
            hub_config = load_hub_config(fuzzforge_root)
        except Exception:
            table.add_row(
                Text("Error loading config", style="red"), "", "", ""
            )
            return

        servers = hub_config.get("servers", [])
        if not servers:
            table.add_row(
                Text("No servers — press h", style="dim"), "", "", ""
            )
            return

        # Group servers by source hub
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for server in servers:
            source = server.get("source_hub", "manual")
            groups[source].append(server)

        for hub_name, hub_servers in groups.items():
            ready_count = 0
            total = len(hub_servers)

            statuses: list[tuple[dict[str, Any], bool, str]] = []
            for server in hub_servers:
                enabled = server.get("enabled", True)
                if not enabled:
                    statuses.append((server, False, "Disabled"))
                else:
                    is_ready, status_text = check_hub_image(
                        server.get("image", "")
                    )
                    if is_ready:
                        ready_count += 1
                    statuses.append((server, is_ready, status_text))

            # Group header row
            if hub_name == "manual":
                header = Text(
                    f"▼ 📦 Local config ({ready_count}/{total} ready)",
                    style="bold",
                )
            else:
                header = Text(
                    f"▼ 🔗 {hub_name} ({ready_count}/{total} ready)",
                    style="bold",
                )
            table.add_row(header, "", "", "")
            self._hub_rows.append(None)  # group header — not selectable

            # Tool rows
            for server, is_ready, status_text in statuses:
                name = server.get("name", "unknown")
                image = server.get("image", "unknown")
                enabled = server.get("enabled", True)

                if not enabled:
                    status_cell = Text("Disabled", style="dim")
                elif is_ready:
                    status_cell = Text("✓ Ready", style="green")
                else:
                    status_cell = Text(f"✗ {status_text}", style="red dim")

                table.add_row(
                    f"  {name}",
                    Text(image, style="dim"),
                    hub_name,
                    status_cell,
                )
                self._hub_rows.append((name, image, hub_name))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection on agents and hub tables."""
        if event.data_table.id == "agents-table":
            self._handle_agent_row(event.cursor_row)
        elif event.data_table.id == "hub-table":
            self._handle_hub_row(event.cursor_row)

    def _handle_agent_row(self, idx: int) -> None:
        """Open agent setup/unlink for the selected agent row."""
        if idx < 0 or idx >= len(self._agent_rows):
            return

        display_name, agent, _config_path, _servers_key, is_linked = self._agent_rows[idx]

        if is_linked:
            from fuzzforge_cli.tui.screens.agent_setup import AgentUnlinkScreen

            self.push_screen(
                AgentUnlinkScreen(agent, display_name),
                callback=self._on_agent_changed,
            )
        else:
            from fuzzforge_cli.tui.screens.agent_setup import AgentSetupScreen

            self.push_screen(
                AgentSetupScreen(agent, display_name),
                callback=self._on_agent_changed,
            )

    def _handle_hub_row(self, idx: int) -> None:
        """Open the build dialog for the selected hub tool row."""
        if idx < 0 or idx >= len(self._hub_rows):
            return
        row_data = self._hub_rows[idx]
        if row_data is None:
            return  # group header row — ignore

        server_name, image, hub_name = row_data
        if hub_name == "manual":
            self.notify("Manual servers must be built outside FuzzForge")
            return

        from fuzzforge_cli.tui.screens.build_image import BuildImageScreen

        self.push_screen(
            BuildImageScreen(server_name, image, hub_name),
            callback=self._on_image_built,
        )

    def _on_image_built(self, success: bool) -> None:
        """Refresh hub status after a build attempt."""
        self._refresh_hub()
        if success:
            self.notify("Image built successfully", severity="information")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-hub-manager":
            self.action_manage_hubs()
        elif event.button.id == "btn-fuzzinglabs-hub":
            self.action_add_fuzzinglabs_hub()

    def action_add_fuzzinglabs_hub(self) -> None:
        """Open the clone dialog pre-filled with the FuzzingLabs hub URL."""
        from fuzzforge_cli.tui.screens.hub_manager import CloneHubScreen

        self.push_screen(
            CloneHubScreen(
                default_url="https://github.com/FuzzingLabs/mcp-security-hub",
                default_name="mcp-security-hub",
                is_default=True,
            ),
            callback=self._on_hub_changed,
        )

    def action_manage_hubs(self) -> None:
        """Open the hub manager."""
        from fuzzforge_cli.tui.screens.hub_manager import HubManagerScreen

        self.push_screen(HubManagerScreen(), callback=self._on_hub_changed)

    def _on_agent_changed(self, result: str | None) -> None:
        """Handle agent setup/unlink completion."""
        if result:
            self.notify(result)
        self._refresh_agents()

    def _on_hub_changed(self, result: str | None) -> None:
        """Handle hub manager completion — refresh the hub table."""
        self._refresh_hub()

    def action_refresh(self) -> None:
        """Refresh all status panels."""
        self._refresh_agents()
        self._refresh_hub()
        self.notify("Status refreshed")
