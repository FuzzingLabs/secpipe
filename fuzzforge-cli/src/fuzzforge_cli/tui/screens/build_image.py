"""Build-image modal screen for FuzzForge TUI.

Provides a modal dialog that runs ``docker/podman build`` for a single
hub tool and streams the build log into a scrollable log area.

"""

from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Log

from fuzzforge_cli.tui.helpers import build_image, find_dockerfile_for_server


class BuildImageScreen(ModalScreen[bool]):
    """Modal that builds a Docker/Podman image and streams the build log."""

    BINDINGS = [("escape", "cancel", "Close")]

    def __init__(self, server_name: str, image: str, hub_name: str) -> None:
        super().__init__()
        self._server_name = server_name
        self._image = image
        self._hub_name = hub_name

    def compose(self) -> ComposeResult:
        """Compose the build dialog layout."""
        with Vertical(id="build-dialog"):
            yield Label(f"Build  {self._image}", classes="dialog-title")
            yield Label(
                f"Hub: {self._hub_name}  •  Tool: {self._server_name}",
                id="build-subtitle",
            )
            yield Log(id="build-log", auto_scroll=True)
            yield Label("", id="build-status")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Close", variant="default", id="btn-close", disabled=True)

    def on_mount(self) -> None:
        """Start the build as soon as the screen is shown."""
        self._start_build()

    def action_cancel(self) -> None:
        """Only dismiss when the build is not running (Close button enabled)."""
        close_btn = self.query_one("#btn-close", Button)
        if not close_btn.disabled:
            self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle Close button."""
        if event.button.id == "btn-close":
            self.dismiss(self._succeeded)

    @work(thread=True)
    def _start_build(self) -> None:
        """Run the build in a background thread and stream output."""
        self._succeeded = False
        log = self.query_one("#build-log", Log)
        status = self.query_one("#build-status", Label)

        dockerfile = find_dockerfile_for_server(self._server_name, self._hub_name)
        if dockerfile is None:
            log.write_line(f"ERROR: Dockerfile not found for '{self._server_name}' in hub '{self._hub_name}'")
            status.update("[red]Build failed — Dockerfile not found[/red]")
            self.query_one("#btn-close", Button).disabled = False
            return

        log.write_line(f"$ {self._get_engine()} build -t {self._image} {dockerfile.parent}")
        log.write_line("")

        try:
            proc = build_image(self._image, dockerfile)
        except FileNotFoundError as exc:
            log.write_line(f"ERROR: {exc}")
            status.update("[red]Build failed — engine not found[/red]")
            self.query_one("#btn-close", Button).disabled = False
            return

        assert proc.stdout is not None
        for line in proc.stdout:
            log.write_line(line.rstrip())

        proc.wait()

        if proc.returncode == 0:
            self._succeeded = True
            status.update(f"[green]✓ Built {self._image} successfully[/green]")
        else:
            status.update(f"[red]✗ Build failed (exit {proc.returncode})[/red]")

        self.query_one("#btn-close", Button).disabled = False

    @staticmethod
    def _get_engine() -> str:
        import os
        engine = os.environ.get("FUZZFORGE_ENGINE__TYPE", "docker").lower()
        return "podman" if engine == "podman" else "docker"
