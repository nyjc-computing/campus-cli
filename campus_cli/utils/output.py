"""Output formatting utilities using Rich."""

import json
from typing import Any, Optional

from rich.console import Console
from rich.json import JSON
from rich.table import Table


console = Console()


def print_success(message: str) -> None:
    """
    Print a success message.

    Args:
        message: The message to print.
    """
    console.print(f"[green bold]✓[/green bold] {message}")


def print_error(message: str) -> None:
    """
    Print an error message.

    Args:
        message: The error message to print.
    """
    console.print(f"[red bold]✗[/red bold] {message}", stderr=True)


def print_warning(message: str) -> None:
    """
    Print a warning message.

    Args:
        message: The warning message to print.
    """
    console.print(f"[yellow bold]⚠[/yellow bold] {message}")


def print_table(
    headers: list[str],
    rows: list[list[str]],
    title: Optional[str] = None,
) -> None:
    """
    Print data in a formatted table.

    Args:
        headers: Column headers.
        rows: Data rows.
        title: Optional table title.
    """
    table = Table(title=title, show_header=True, header_style="bold magenta")

    for header in headers:
        table.add_column(header)

    for row in rows:
        table.add_row(*row)

    console.print(table)


def print_json(data: Any, pretty: bool = True) -> None:
    """
    Print data as formatted JSON.

    Args:
        data: The data to print (must be JSON-serializable).
        pretty: Whether to pretty-print the JSON.
    """
    if pretty:
        console.print(JSON(json.dumps(data, indent=2)))
    else:
        console.print(json.dumps(data))
