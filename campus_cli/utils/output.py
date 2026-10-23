"""Output formatting utilities using Rich."""

import json
import os
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

# Preamble for campus.audit --dry-run snippets (#54): the audit API
# (/audit/v1) authenticates with one of its own API keys, not an
# OAuth token, so its resource root is built directly.
AUDIT_PYTHON_API_PREAMBLE = [
    "from campus_python import AuditRoot, CampusRequest",
    "",
    "campus_audit = AuditRoot(json_client=CampusRequest(",
    '    base_url="<audit_url>", timeout=30, mode="device",',
    "))",
    "",
    "# Set your audit API key (campus audit login)",
    'campus_audit.client.set_bearer_authorization("<audit_api_key>")',
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


def _agent_mode() -> bool:
    """
    Whether CAMPUS_CLI_AGENT opts out of display-only formatting.

    Agent tools often allocate a pty, so terminal detection alone cannot
    be trusted to pick raw machine-readable output (#69).
    """
    return os.environ.get("CAMPUS_CLI_AGENT", "").strip().lower() not in (
        "",
        "0",
        "false",
    )


def print_json(data: Any, pretty: Optional[bool] = None) -> None:
    """
    Print data as JSON.

    Raw output is the default: plain ``json.dumps`` written straight to
    stdout, byte-exact in every string value and always spec-valid. The
    Rich highlighted renderable is display-only — it soft-wraps long
    values at the console width, inserting literal newlines into the
    data — so it is reserved for interactive terminals; pipes, scripts
    and CAMPUS_CLI_AGENT consumers always get the raw form (#69).

    Args:
        data: The data to print (must be JSON-serializable).
        pretty: Force the display renderable (True) or raw output
            (False); by default, pretty only when stdout is a TTY.
    """
    if pretty is None:
        pretty = console.is_terminal and not _agent_mode()
    if pretty:
        console.print(JSON(json.dumps(data, indent=2)))
    else:
        print(json.dumps(data, indent=2))


def print_python_api(
    command: str,
    operation: list[str],
    preamble: Optional[list[str]] = None,
) -> None:
    """
    Print the equivalent Python API code for a --dry-run invocation.

    Shows how the same operation is performed with the campus_python
    library, using the arguments passed to the command.

    Args:
        command: The CLI command the snippet corresponds to.
        operation: The API operation lines (after client setup).
        preamble: Client-setup lines opening the snippet; defaults to
                  the OAuth-token device client (audit commands pass
                  the audit API-key setup instead, #54).
    """
    code = "\n".join([*(preamble or _PYTHON_API_PREAMBLE), *operation])
    console.print("[bold]Dry run:[/bold] no API call made.")
    console.print(f"Equivalent Python code for [cyan]{command}[/cyan]:\n")
    console.print(Syntax(code, "python", word_wrap=True, background_color="default"))
    console.print(
        "\n[dim]Requires the campus-api-python package:"
        " pip install campus-api-python[/dim]"
    )
