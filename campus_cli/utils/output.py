"""Output formatting utilities using Rich."""

import json
from typing import Any, Optional

from rich.console import Console
from rich.json import JSON
from rich.syntax import Syntax
from rich.table import Table

console = Console()
stderr_console = Console(stderr=True)

# Preamble shared by all --dry-run Python snippets: the campus_python
# equivalent always starts by constructing a device-mode client and
# authenticating it with a Bearer token.
_PYTHON_API_PREAMBLE = [
    "from campus_python import Campus",
    "",
    'campus = Campus(timeout=30, mode="device")',
    "",
    "# Set your access token (device flow: see campus.auth.oauth)",
    'campus.auth.client.set_bearer_authorization("<access_token>")',
    "",
]


def print_success(message: str) -> None:
    """
    Print a success message.

    Args:
        message: The message to print.
    """
    console.print(f"[green bold]✓[/green bold] {message}")


def print_error(message: str) -> None:
    """
    Print an error message to stderr.

    Args:
        message: The error message to print.
    """
    stderr_console.print(f"[red bold]✗[/red bold] {message}")


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


def print_python_api(command: str, operation: list[str]) -> None:
    """
    Print the equivalent Python API code for a --dry-run invocation.

    Shows how the same operation is performed with the campus_python
    library, using the arguments passed to the command.

    Args:
        command: The CLI command the snippet corresponds to.
        operation: The API operation lines (after client setup).
    """
    code = "\n".join([*_PYTHON_API_PREAMBLE, *operation])
    console.print("[bold]Dry run:[/bold] no API call made.")
    console.print(f"Equivalent Python code for [cyan]{command}[/cyan]:\n")
    console.print(Syntax(code, "python", word_wrap=True, background_color="default"))
    console.print(
        "\n[dim]Requires the campus-api-python package:"
        " pip install campus-api-python[/dim]"
    )
