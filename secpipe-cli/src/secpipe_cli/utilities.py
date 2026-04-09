"""CLI utility functions."""

from rich.console import Console
from rich.table import Table
from typer import Exit


def on_error(message: str) -> None:
    """Display an error message and exit.

    :param message: Error message to display.

    """
    table = Table()
    table.add_column("Error")
    table.add_row(message)
    Console().print(table)
    raise Exit(code=1)
