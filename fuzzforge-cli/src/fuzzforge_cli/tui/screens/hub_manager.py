"""Hub management screens for FuzzForge TUI.

Provides modal dialogs for managing linked MCP hub repositories:
- HubManagerScreen: list, add, remove linked hubs
- LinkHubScreen: link a local directory as a hub
- CloneHubScreen: clone a git repo and link it (defaults to FuzzingLabs hub)

"""

from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Static

from fuzzforge_cli.tui.helpers import (
    FUZZFORGE_DEFAULT_HUB_NAME,
    FUZZFORGE_DEFAULT_HUB_URL,
    clone_hub,
    link_hub,
    load_hubs_registry,
    scan_hub_for_servers,
    unlink_hub,
)


class HubManagerScreen(ModalScreen[str | None]):
    """Modal screen for managing linked MCP hubs."""

    BINDINGS = [("escape", "cancel", "Close")]

    def compose(self) -> ComposeResult:
        """Compose the hub manager layout."""
        with Vertical(id="hub-manager-dialog"):
            yield Label("Hub Manager", classes="dialog-title")
            yield DataTable(id="hubs-table")
            yield Label("", id="hub-status")
            with Horizontal(classes="dialog-buttons"):
                yield Button(
                    "FuzzingLabs Hub",
                    variant="primary",
                    id="btn-clone-default",
                )
                yield Button("Link Path", variant="default", id="btn-link")
                yield Button("Clone URL", variant="default", id="btn-clone")
                yield Button("Remove", variant="primary", id="btn-remove")
                yield Button("Close", variant="default", id="btn-close")

    def on_mount(self) -> None:
        """Populate the hubs table on startup."""
        self._refresh_hubs()

    def _refresh_hubs(self) -> None:
        """Refresh the linked hubs table."""
        table = self.query_one("#hubs-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Name", "Path", "Servers", "Source")
        table.cursor_type = "row"

        registry = load_hubs_registry()
        hubs = registry.get("hubs", [])

        if not hubs:
            table.add_row(
                Text("No hubs linked", style="dim"),
                Text("Press 'FuzzingLabs Hub' to get started", style="dim"),
                "",
                "",
            )
            return

        for hub in hubs:
            name = hub.get("name", "unknown")
            path = hub.get("path", "")
            git_url = hub.get("git_url", "")
            is_default = hub.get("is_default", False)

            hub_path = Path(path)
            if hub_path.is_dir():
                servers = scan_hub_for_servers(hub_path)
                count = str(len(servers))
            else:
                count = Text("dir missing", style="yellow")

            source = git_url or "local"
            if is_default:
                name_cell = Text(f"★ {name}", style="bold")
            else:
                name_cell = Text(name)

            table.add_row(name_cell, path, count, source)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route button actions."""
        if event.button.id == "btn-close":
            self.dismiss("refreshed")
        elif event.button.id == "btn-clone-default":
            self.app.push_screen(
                CloneHubScreen(
                    FUZZFORGE_DEFAULT_HUB_URL,
                    FUZZFORGE_DEFAULT_HUB_NAME,
                    is_default=True,
                ),
                callback=self._on_hub_action,
            )
        elif event.button.id == "btn-link":
            self.app.push_screen(
                LinkHubScreen(),
                callback=self._on_hub_action,
            )
        elif event.button.id == "btn-clone":
            self.app.push_screen(
                CloneHubScreen(),
                callback=self._on_hub_action,
            )
        elif event.button.id == "btn-remove":
            self._remove_selected()

    def _on_hub_action(self, result: str | None) -> None:
        """Handle result from a sub-screen."""
        if result:
            self.query_one("#hub-status", Label).update(result)
            self.app.notify(result)
        self._refresh_hubs()

    def _remove_selected(self) -> None:
        """Remove the currently selected hub."""
        table = self.query_one("#hubs-table", DataTable)
        registry = load_hubs_registry()
        hubs = registry.get("hubs", [])

        if not hubs:
            self.app.notify("No hubs to remove", severity="warning")
            return

        idx = table.cursor_row
        if idx is None or idx < 0 or idx >= len(hubs):
            self.app.notify("Select a hub to remove", severity="warning")
            return

        name = hubs[idx].get("name", "")
        result = unlink_hub(name)
        self.query_one("#hub-status", Label).update(result)
        self._refresh_hubs()
        self.app.notify(result)

    def action_cancel(self) -> None:
        """Close the hub manager."""
        self.dismiss("refreshed")


class LinkHubScreen(ModalScreen[str | None]):
    """Modal for linking a local directory as an MCP hub."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        """Compose the link dialog layout."""
        with Vertical(id="link-dialog"):
            yield Label("Link Local Hub", classes="dialog-title")

            yield Label("Hub Name:", classes="field-label")
            yield Input(placeholder="my-hub", id="name-input")

            yield Label("Directory Path:", classes="field-label")
            yield Input(placeholder="/path/to/hub-directory", id="path-input")

            yield Label("", id="link-status")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Link", variant="primary", id="btn-link")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-link":
            self._do_link()

    def _do_link(self) -> None:
        """Execute the link operation."""
        name = self.query_one("#name-input", Input).value.strip()
        path = self.query_one("#path-input", Input).value.strip()

        if not name:
            self.app.notify("Please enter a hub name", severity="warning")
            return
        if not path:
            self.app.notify("Please enter a directory path", severity="warning")
            return

        result = link_hub(name, path)
        self.dismiss(result)

    def action_cancel(self) -> None:
        """Dismiss without action."""
        self.dismiss(None)


class CloneHubScreen(ModalScreen[str | None]):
    """Modal for cloning a git hub repository and linking it.

    When instantiated with *is_default=True* and FuzzingLabs URL,
    provides a one-click setup for the standard security hub.

    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(
        self,
        default_url: str = "",
        default_name: str = "",
        is_default: bool = False,
    ) -> None:
        super().__init__()
        self._default_url = default_url
        self._default_name = default_name
        self._is_default = is_default

    def compose(self) -> ComposeResult:
        """Compose the clone dialog layout."""
        title = "Clone FuzzingLabs Hub" if self._is_default else "Clone Git Hub"
        with Vertical(id="clone-dialog"):
            yield Label(title, classes="dialog-title")

            yield Label("Git URL:", classes="field-label")
            yield Input(
                value=self._default_url,
                placeholder="git@github.com:org/repo.git",
                id="url-input",
            )

            yield Label("Hub Name (optional):", classes="field-label")
            yield Input(
                value=self._default_name,
                placeholder="auto-detect from URL",
                id="name-input",
            )

            yield Static("", id="clone-status")
            with Horizontal(classes="dialog-buttons"):
                yield Button(
                    "Clone & Link",
                    variant="primary",
                    id="btn-clone",
                )
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-clone":
            self._start_clone()

    def _start_clone(self) -> None:
        """Validate input and start the async clone operation."""
        url = self.query_one("#url-input", Input).value.strip()
        if not url:
            self.app.notify("Please enter a git URL", severity="warning")
            return

        self.query_one("#btn-clone", Button).disabled = True
        self.query_one("#clone-status", Static).update("⏳ Cloning repository...")
        self._do_clone(url)

    @work(thread=True)
    def _do_clone(self, url: str) -> None:
        """Clone the repo in a background thread."""
        name_input = self.query_one("#name-input", Input).value.strip()
        name = name_input or None

        success, msg, path = clone_hub(url, name=name)
        if success and path:
            hub_name = name or path.name
            link_result = link_hub(
                hub_name,
                path,
                git_url=url,
                is_default=self._is_default,
            )
            self.app.call_from_thread(self.dismiss, f"✓ {link_result}")
        else:
            self.app.call_from_thread(self._on_clone_failed, msg)

    def _on_clone_failed(self, msg: str) -> None:
        """Handle a failed clone — re-enable the button and show the error."""
        self.query_one("#clone-status", Static).update(f"✗ {msg}")
        self.query_one("#btn-clone", Button).disabled = False

    def action_cancel(self) -> None:
        """Dismiss without action."""
        self.dismiss(None)
