"""Build-log viewer screen for SecPipe TUI.

Shows live output of a background build started by the app.  Polls the
app's ``_build_logs`` buffer every 500 ms so the user can pop this screen
open at any time while the build is running and see up-to-date output.

"""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Log


class _NoFocusButton(Button):
    can_focus = False


class BuildLogScreen(ModalScreen[None]):
    """Live log viewer for a background build job managed by the app."""

    BINDINGS = [("escape", "close", "Close")]

    def __init__(self, image: str) -> None:
        super().__init__()
        self._image = image
        self._last_line: int = 0

    def compose(self) -> ComposeResult:
        """Build the log viewer UI."""
        with Vertical(id="build-dialog"):
            yield Label(f"Build log — {self._image}", classes="dialog-title")
            yield Label("", id="build-status")
            yield Log(id="build-log", auto_scroll=True)
            with Horizontal(classes="dialog-buttons"):
                yield _NoFocusButton("Close", variant="default", id="btn-close")

    def on_mount(self) -> None:
        """Initialize log polling when the screen is mounted."""
        self._flush_log()
        self.set_interval(0.5, self._poll_log)

    def _flush_log(self) -> None:
        """Write any new lines since the last flush."""
        logs: list[str] = getattr(self.app, "_build_logs", {}).get(self._image, [])
        log_widget = self.query_one("#build-log", Log)
        new_lines = logs[self._last_line :]
        for line in new_lines:
            log_widget.write_line(line)
        self._last_line += len(new_lines)

        active: dict[str, Any] = getattr(self.app, "_active_builds", {})
        status = self.query_one("#build-status", Label)
        if self._image in active:
            status.update("[yellow]⏳ Building…[/yellow]")
        else:
            # Build is done — check if we have a result stored
            results: dict[str, Any] = getattr(self.app, "_build_results", {})
            if self._image in results:
                if results[self._image]:
                    status.update(f"[green]✓ {self._image} built successfully[/green]")
                else:
                    status.update(f"[red]✗ {self._image} build failed[/red]")

    def _poll_log(self) -> None:
        """Poll for new log lines periodically."""
        self._flush_log()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle Close button click."""
        if event.button.id == "btn-close":
            self.dismiss(None)

    def action_close(self) -> None:
        """Dismiss the dialog when Escape is pressed."""
        self.dismiss(None)
