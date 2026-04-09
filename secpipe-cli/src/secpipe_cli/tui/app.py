"""SecPipe TUI application.

Main terminal user interface for SecPipe, providing a dashboard
with AI agent connection status, hub server availability, and
hub management capabilities.

"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Button, DataTable, Footer, Header

from secpipe_cli.tui.helpers import (
    check_agent_status,
    check_hub_image,
    find_secpipe_root,
    get_agent_configs,
    load_hub_config,
)

if TYPE_CHECKING:
    from secpipe_cli.commands.mcp import AIAgent

# Agent config entries stored alongside their linked status for row mapping
_AgentRow = tuple[str, "AIAgent", Path, str, bool]


class SingleClickDataTable(DataTable[Any]):
    """DataTable subclass that also fires ``RowClicked`` on a single mouse click.

    Textual's built-in ``RowSelected`` only fires on Enter or on a second click
    of an already-highlighted row.  ``RowClicked`` fires on every first click,
    enabling single-click-to-act UX without requiring Enter.
    """

    class RowClicked(Message):
        """Fired on every single mouse click on a data row."""

        def __init__(self, data_table: SingleClickDataTable, cursor_row: int) -> None:
            self.data_table = data_table
            self.cursor_row = cursor_row
            super().__init__()

        @property
        def control(self) -> SingleClickDataTable:
            """Return the data table that fired this event."""
            return self.data_table

    async def _on_click(self, event: events.Click) -> None:
        """Forward to parent, then post RowClicked on every mouse click.

        The hub table is handled exclusively via RowClicked.  RowSelected is
        intentionally NOT used for the hub table to avoid double-dispatch.
        """
        await super()._on_click(event)
        meta = event.style.meta
        if meta and "row" in meta and self.cursor_type == "row":
            row_index: int = int(meta["row"])
            if row_index >= 0:
                self.post_message(SingleClickDataTable.RowClicked(self, row_index))


class SecPipeApp(App[None]):
    """SecPipe AI terminal user interface."""

    TITLE = "SecPipe AI"
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
    BuildImageScreen, BuildLogScreen {
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
        width: 72;
        height: auto;
        max-height: 80%;
        border: thick #4699fc;
        background: $surface;
        padding: 2 3;
    }

    #confirm-text {
        margin: 1 0 2 0;
    }

    #build-log {
        height: 30;
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
                yield SingleClickDataTable(id="hub-table")
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
        self._hub_rows: list[tuple[str, str, str, bool] | None] = []
        # Background build tracking
        self._active_builds: dict[str, object] = {}  # image -> Popen
        self._build_logs: dict[str, list[str]] = {}   # image -> log lines
        self._build_results: dict[str, bool] = {}     # image -> success
        self.query_one("#hub-panel").border_title = "Hub Servers  [dim](click ✗ Not built to build)[/dim]"
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
        table = self.query_one("#hub-table", SingleClickDataTable)
        table.clear(columns=True)
        table.add_columns("Server", "Image", "Hub", "Status")
        table.cursor_type = "row"

        try:
            secpipe_root = find_secpipe_root()
            hub_config = load_hub_config(secpipe_root)
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

                if image in getattr(self, "_active_builds", {}):
                    status_cell = Text("⏳ Building…", style="yellow")
                elif not enabled:
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
                self._hub_rows.append((name, image, hub_name, is_ready))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle Enter-key row selection (agents table only).

        Hub table uses RowClicked exclusively — wiring it to RowSelected too
        would cause a double push on every click since Textual 8 fires
        RowSelected on ALL clicks, not just second-click-on-same-row.
        """
        if event.data_table.id == "agents-table":
            self._handle_agent_row(event.cursor_row)

    def on_single_click_data_table_row_clicked(
        self, event: SingleClickDataTable.RowClicked
    ) -> None:
        """Handle single mouse-click on a hub table row."""
        if event.data_table.id == "hub-table":
            self._handle_hub_row(event.cursor_row)

    def _handle_agent_row(self, idx: int) -> None:
        """Open agent setup/unlink for the selected agent row."""
        if idx < 0 or idx >= len(self._agent_rows):
            return

        display_name, agent, _config_path, _servers_key, is_linked = self._agent_rows[idx]

        if is_linked:
            from secpipe_cli.tui.screens.agent_setup import AgentUnlinkScreen

            self.push_screen(
                AgentUnlinkScreen(agent, display_name),
                callback=self._on_agent_changed,
            )
        else:
            from secpipe_cli.tui.screens.agent_setup import AgentSetupScreen

            self.push_screen(
                AgentSetupScreen(agent, display_name),
                callback=self._on_agent_changed,
            )

    def _handle_hub_row(self, idx: int) -> None:
        """Handle a click on a hub table row."""
        # Guard: never push two build dialogs at once (double-click protection)
        if getattr(self, "_build_dialog_open", False):
            return

        if idx < 0 or idx >= len(self._hub_rows):
            return
        row_data = self._hub_rows[idx]
        if row_data is None:
            return  # group header row — ignore

        server_name, image, hub_name, is_ready = row_data

        # If a build is already running, open the live log viewer
        if image in self._active_builds:
            from secpipe_cli.tui.screens.build_log import BuildLogScreen
            self._build_dialog_open = True
            self.push_screen(
                BuildLogScreen(image),
                callback=lambda _: setattr(self, "_build_dialog_open", False),
            )
            return

        if is_ready:
            self.notify(f"{image} is already built ✓", severity="information")
            return

        if hub_name == "manual":
            self.notify("Manual servers must be built outside SecPipe")
            return

        from secpipe_cli.tui.screens.build_image import BuildImageScreen

        self._build_dialog_open = True

        def _on_build_dialog_done(result: bool | None) -> None:
            self._build_dialog_open = False
            if result is not None:
                self._on_build_confirmed(result, server_name, image, hub_name)

        self.push_screen(
            BuildImageScreen(server_name, image, hub_name),
            callback=_on_build_dialog_done,
        )

    def _on_build_confirmed(self, confirmed: bool, server_name: str, image: str, hub_name: str) -> None:
        """Start a background build if the user confirmed."""
        if not confirmed:
            return
        self._build_logs[image] = []
        self._build_results.pop(image, None)
        self._active_builds[image] = True  # mark as pending so ⏳ shows immediately
        self._refresh_hub()  # show ⏳ Building… immediately
        self._run_build(server_name, image, hub_name)

    @work(thread=True)
    def _run_build(self, server_name: str, image: str, hub_name: str) -> None:
        """Build a Docker/Podman image in a background thread."""
        from secpipe_cli.tui.helpers import build_image, find_dockerfile_for_server

        logs = self._build_logs.setdefault(image, [])

        dockerfile = find_dockerfile_for_server(server_name, hub_name)
        if dockerfile is None:
            logs.append(f"ERROR: Dockerfile not found for '{server_name}' in hub '{hub_name}'")
            self._build_results[image] = False
            self._active_builds.pop(image, None)
            self.call_from_thread(self._on_build_done, image, success=False)
            return

        logs.append(f"Building {image} from {dockerfile.parent}")
        logs.append("")

        try:
            proc = build_image(image, dockerfile)
        except FileNotFoundError as exc:
            logs.append(f"ERROR: {exc}")
            self._build_results[image] = False
            self._active_builds.pop(image, None)
            self.call_from_thread(self._on_build_done, image, success=False)
            return

        self._active_builds[image] = proc  # replace pending marker with actual process
        self.call_from_thread(self._refresh_hub)  # show ⏳ in table

        if proc.stdout is None:
            return
        for line in proc.stdout:
            logs.append(line.rstrip())

        proc.wait()
        self._active_builds.pop(image, None)
        success = proc.returncode == 0
        self._build_results[image] = success
        self.call_from_thread(self._on_build_done, image, success=success)

    def _on_build_done(self, image: str, *, success: bool) -> None:
        """Handle completion of a background build on the main thread."""
        self._refresh_hub()
        if success:
            self.notify(f"✓ {image} built successfully", severity="information")
        else:
            self.notify(f"✗ {image} build failed — click row for log", severity="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-hub-manager":
            self.action_manage_hubs()
        elif event.button.id == "btn-fuzzinglabs-hub":
            self.action_add_fuzzinglabs_hub()

    def action_add_fuzzinglabs_hub(self) -> None:
        """Open the clone dialog pre-filled with the FuzzingLabs hub URL."""
        from secpipe_cli.tui.screens.hub_manager import CloneHubScreen

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
        from secpipe_cli.tui.screens.hub_manager import HubManagerScreen

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
