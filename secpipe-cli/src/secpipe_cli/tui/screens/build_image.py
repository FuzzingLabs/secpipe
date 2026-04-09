"""Build-image confirm dialog for SecPipe TUI.

Simple modal that asks the user to confirm before starting a background
build.  The actual build is managed by the app so the user is never
locked on this screen.

"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class _NoFocusButton(Button):
    can_focus = False


class BuildImageScreen(ModalScreen[bool]):
    """Quick confirmation before starting a background Docker/Podman build."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, server_name: str, image: str, hub_name: str) -> None:
        super().__init__()
        self._server_name = server_name
        self._image = image
        self._hub_name = hub_name

    def compose(self) -> ComposeResult:
        """Build the confirmation dialog UI."""
        with Vertical(id="build-dialog"):
            yield Label(f"Build  {self._image}", classes="dialog-title")
            yield Label(
                f"Hub: {self._hub_name}  •  Tool: {self._server_name}",
                id="build-subtitle",
            )
            yield Label(
                "The image will be built in the background.\n"
                "You'll receive a notification when it's done.",
                id="confirm-text",
            )
            with Horizontal(classes="dialog-buttons"):
                yield _NoFocusButton("Build", variant="primary", id="btn-build")
                yield _NoFocusButton("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle Build or Cancel button clicks."""
        if event.button.id == "btn-build":
            self.dismiss(result=True)
        elif event.button.id == "btn-cancel":
            self.dismiss(result=False)

    def action_cancel(self) -> None:
        """Dismiss the dialog when Escape is pressed."""
        self.dismiss(result=False)
