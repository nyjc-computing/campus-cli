"""campus.audit trace queries (#54).

Read-only access to the traces the audit service records: recent
traces, full span trees, and filtered search, gated on traces:read.
Trace IDs are 32-char hex, span IDs 16-char hex (OpenTelemetry
convention).
"""

from typing import Optional

import typer
from rich.console import Console

from campus_cli.audit.client import fail_api, get_audit_client
from campus_cli.auth.common import dry_run_option
from campus_cli.utils.output import (
    AUDIT_PYTHON_API_PREAMBLE,
    print_json,
    print_python_api,
)

traces_app = typer.Typer(help="Trace queries (read-only, traces:read)")
console = Console()


def _status_markup(status: Optional[int]) -> str:
    """Color a status code: green 2xx, yellow 3xx/4xx, red 5xx/none."""
    if status is None:
        return "[dim]—[/dim]"
    if 200 <= status < 300:
        return f"[green]{status}[/green]"
    if 200 <= status < 500:
        return f"[yellow]{status}[/yellow]"
    return f"[red]{status}[/red]"


def _format_trace_summary(trace: dict) -> str:
    """Render a trace summary line: method, path, status, timing."""
    root = trace.get("root_span") or {}
    method = root.get("method", "?")
    path = root.get("path", "?")
    user = root.get("user_id") or root.get("client_id") or "anonymous"
    return (
        f"{method} {path} → {_status_markup(root.get('status_code'))}"
        f"  {trace.get('duration_ms', '?')} ms,"
        f" {trace.get('span_count', '?')} span(s), user: {user}"
    )


def _print_trace_page(result: dict) -> None:
    """Print a list/search result page with its continuation cursor."""
    traces = result.get("traces", [])
    if not traces:
        console.print("[dim]No traces found.[/dim]")
        return
    console.print(f"[bold]Showing {len(traces)} trace(s):[/bold]\n")
    for trace in traces:
        console.print(f"[cyan]{trace.get('trace_id', '?')}[/cyan]")
        console.print(f"  {_format_trace_summary(trace)}")
        console.print(f"  [dim]{trace.get('started_at', '')}[/dim]")
        console.print()
    cursor = result.get("cursor") or {}
    if cursor.get("has_more") and cursor.get("next"):
        console.print(
            "[dim]More traces available; continue with "
            f"--cursor {cursor['next']}[/dim]"
        )


def _dry_run(command: str, operation: list[str]) -> None:
    """Print a dry-run snippet carrying the audit client preamble."""
    print_python_api(command, operation, preamble=AUDIT_PYTHON_API_PREAMBLE)


def _query_operation(call: str, kwargs: dict) -> list[str]:
    """Operation lines for list/search: only the given kwargs appear."""
    given = [f"    {k}={v!r}," for k, v in kwargs.items() if v is not None]
    if given:
        head = [f"result = campus_audit.traces.{call}(", *given, ")"]
    else:
        head = [f"result = campus_audit.traces.{call}()"]
    return [
        *head,
        "for trace in result['traces']:",
        "    print(trace['trace_id'], trace['root_span']['path'])",
    ]


@traces_app.command("list")
def traces_list(
    since: Optional[str] = typer.Option(
        None, "--since", help="ISO 8601 lower bound on trace time"
    ),
    until: Optional[str] = typer.Option(
        None, "--until", help="ISO 8601 upper bound on trace time"
    ),
    limit: Optional[int] = typer.Option(None, "--limit", help="Page size"),
    cursor: Optional[str] = typer.Option(
        None, "--cursor", help="Opaque token from a previous page"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """List recent traces, newest first."""
    if dry_run:
        _dry_run(
            "campus audit traces list",
            _query_operation("list", {
                "since": since, "until": until,
                "limit": limit, "cursor": cursor,
            }),
        )
        return

    try:
        api = get_audit_client()
        result = api.traces.list(
            since=since, until=until, limit=limit, cursor=cursor
        )

        if output_json:
            print_json(result)
        else:
            _print_trace_page(result)

    except typer.Exit:
        raise
    except Exception as e:
        fail_api("list traces", e)


@traces_app.command("get")
def traces_get(
    trace_id: str = typer.Option(..., "--trace-id", help="32-char hex trace ID"),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    Show a trace's full span tree (as JSON).

    The tree is the trace: the root span with its children nested,
    each span carrying the recorded request/response detail.
    """
    if dry_run:
        _dry_run(
            "campus audit traces get",
            [
                f"tree = campus_audit.traces[{trace_id!r}].get()",
                "print(tree)",
            ],
        )
        return

    try:
        api = get_audit_client()
        tree = api.traces[trace_id].get()
        print_json(tree)

    except typer.Exit:
        raise
    except Exception as e:
        fail_api(f"get trace '{trace_id}'", e)


@traces_app.command("search")
def traces_search(
    path: Optional[str] = typer.Option(
        None, "--path", help="Filter by endpoint path"
    ),
    status: Optional[int] = typer.Option(
        None, "--status", help="Filter by HTTP status code"
    ),
    user: Optional[str] = typer.Option(
        None, "--user", help="Filter by user ID"
    ),
    client: Optional[str] = typer.Option(
        None, "--client", help="Filter by OAuth client ID"
    ),
    api_key_id: Optional[str] = typer.Option(
        None, "--api-key-id", help="Filter by audit API key ID"
    ),
    since: Optional[str] = typer.Option(
        None, "--since", help="ISO 8601 lower bound on trace time"
    ),
    until: Optional[str] = typer.Option(
        None, "--until", help="ISO 8601 upper bound on trace time"
    ),
    limit: Optional[int] = typer.Option(None, "--limit", help="Page size"),
    cursor: Optional[str] = typer.Option(
        None, "--cursor", help="Opaque token from a previous page"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    Search traces by endpoint, outcome, principal, or time.

    Filters combine (AND). The server's login-journey filter is not
    exposed here yet — campus-api-python's search() does not carry it.
    """
    if dry_run:
        _dry_run(
            "campus audit traces search",
            _query_operation("search", {
                "path": path, "status": status,
                "user_id": user, "client_id": client,
                "api_key_id": api_key_id,
                "since": since, "until": until,
                "limit": limit, "cursor": cursor,
            }),
        )
        return

    try:
        api = get_audit_client()
        result = api.traces.search(
            path=path,
            status=status,
            user_id=user,
            client_id=client,
            api_key_id=api_key_id,
            since=since,
            until=until,
            limit=limit,
            cursor=cursor,
        )

        if output_json:
            print_json(result)
        else:
            _print_trace_page(result)

    except typer.Exit:
        raise
    except Exception as e:
        fail_api("search traces", e)
