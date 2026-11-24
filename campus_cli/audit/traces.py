"""campus.audit trace queries (#54).

Read-only access to the traces the audit service records: recent
traces, full span trees, and filtered search, gated on traces:read.
Trace IDs are 32-char hex, span IDs 16-char hex (OpenTelemetry
convention).

With --json, failures ship the campus flat error envelope
({"error", "error_description", "status"}) on stdout with exit 1
instead of a sentence on stderr; the envelope's code and status are
null for CLI-side failures (guards, argument validation).
"""

import re
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
    """Render a trace summary line: method, path, status, timing.

    Appends a compact browser/origin marker when the span carries it
    (campus-cli#93): UA family (e.g. ``Chrome/157``) and response
    body size from Content-Length. Older spans without the fields
    render exactly as before.
    """
    root = trace.get("root_span") or {}
    method = root.get("method", "?")
    path = root.get("path", "?")
    user = root.get("user_id") or root.get("client_id") or "anonymous"
    line = (
        f"{method} {path} → {_status_markup(root.get('status_code'))}"
        f"  {trace.get('duration_ms', '?')} ms,"
        f" {trace.get('span_count', '?')} span(s), user: {user}"
    )
    extras = []
    ua_family = _ua_family(root.get("user_agent"))
    if ua_family:
        extras.append(ua_family)
    length = _content_length(root)
    if length is not None:
        extras.append(_human_bytes(length))
    if extras:
        line += "  · " + " · ".join(extras)
    return line


# Browser families worth surfacing compactly; Edg is Edge's UA token.
_UA_FAMILY_RE = re.compile(r"(Chrome|Firefox|Edg|Safari|curl|Python|Wget|git)/(\d+)")


def _ua_family(user_agent: Optional[str]) -> Optional[str]:
    """Compact UA marker: ``Chrome/157`` style, else a truncated string."""
    if not user_agent:
        return None
    match = _UA_FAMILY_RE.search(user_agent)
    if not match:
        return user_agent[:20]
    name = match.group(1)
    return ("Edge" if name == "Edg" else name) + "/" + match.group(2)


def _first_header(headers: Optional[dict], name: str) -> Optional[str]:
    """Case-insensitive header lookup on a stored headers dict."""
    if not headers:
        return None
    lowered = name.lower()
    for key, value in headers.items():
        if isinstance(key, str) and key.lower() == lowered:
            return value if value else None
    return None


def _content_length(root: dict) -> Optional[int]:
    """Response body size from the stored Content-Length header."""
    raw = _first_header(root.get("response_headers"), "Content-Length")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _human_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"~{size / 1024:.1f} kB"
    return f"~{size / (1024 * 1024):.1f} MB"


def _print_trace_detail(tree: dict) -> None:
    """Human-readable single-trace detail (campus-cli#93).

    Root-span essentials first — origin (UA/referer) and size were the
    missing triage signals in the classroom#123 post-mortem — then the
    span tree's shape; `--json` still prints the raw tree for scripts.
    """
    root = tree.get("root_span") or {}
    console.print(f"[cyan]{tree.get('trace_id', '?')}[/cyan]")
    console.print(f"  {_format_trace_summary(tree)}")
    console.print(f"  [dim]{tree.get('started_at', '')}[/dim]")
    fields = [
        ("user", root.get("user_id") or root.get("client_id") or "anonymous"),
        ("client_ip", root.get("client_ip")),
        ("user_agent", root.get("user_agent")),
        ("referer", _first_header(root.get("request_headers"), "Referer")),
        ("response_bytes", _content_length(root)),
    ]
    for label, value in fields:
        if value is not None:
            console.print(f"  {label}: {value}")
    children = root.get("children") or []
    if children:
        console.print(f"  [dim]{len(children)} child span(s):[/dim]")
        for child in children:
            console.print(
                f"    {_child_line(child)}"
            )


def _child_line(child: dict) -> str:
    """One line per child span in the detail view."""
    return (
        f"{child.get('method', '?')} {child.get('path', '?')} → "
        f"{_status_markup(child.get('status_code'))}  "
        f"{child.get('duration_ms', '?')} ms"
    )


def _unwrap_payload(result):
    """Return the parsed JSON payload for either SDK response shape.

    SDK v0.11.0 query methods are annotated ``-> JsonResponse`` but
    return the ``CampusResponse`` wrapper (campus-cli#112); older pins
    returned parsed payloads directly. Duck-type on ``.json()`` so the
    CLI renders correctly against both.
    """
    return result.json() if hasattr(result, "json") else result


def _print_trace_page(result: dict, *, paginated: bool = True) -> None:
    """Print a list/search result page with its continuation cursor.

    ``paginated=False`` (traces list) suppresses the --cursor hint:
    the SDK's list call takes no cursor kwarg (campus-cli#112), so a
    list page cannot be continued — narrow with the time filters or
    use search.
    """
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
        if paginated:
            console.print(
                "[dim]More traces available; continue with "
                f"--cursor {cursor['next']}[/dim]"
            )
        else:
            console.print(
                "[dim]More traces available; narrow with --since/--until "
                "or use search to continue.[/dim]"
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
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """List recent traces, newest first."""
    if dry_run:
        _dry_run(
            "campus audit traces list",
            _query_operation("list", {
                "since": since, "until": until, "limit": limit,
            }),
        )
        return

    try:
        api = get_audit_client(as_json=output_json)
        result = _unwrap_payload(
            api.traces.list(since=since, until=until, limit=limit)
        )

        if output_json:
            print_json(result)
        else:
            _print_trace_page(result, paginated=False)

    except typer.Exit:
        raise
    except Exception as e:
        fail_api("list traces", e, as_json=output_json)


@traces_app.command("get")
def traces_get(
    trace_id: str = typer.Option(..., "--trace-id", help="32-char hex trace ID"),
    output_json: bool = typer.Option(False, "--json", help="Raw span tree as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    Show a trace's detail: root-span essentials (origin, UA, size) plus
    its child spans. Use --json for the raw span tree.

    The tree is the trace: the root span with its children nested,
    each span carrying the recorded request/response detail.
    """
    if dry_run:
        _dry_run(
            "campus audit traces get",
            [
                f"tree = campus_audit.traces[{trace_id!r}].get_tree()",
                "print(tree)",
            ],
        )
        return

    try:
        api = get_audit_client(as_json=output_json)
        tree = _unwrap_payload(api.traces[trace_id].get_tree())
        if output_json:
            print_json(tree)
        else:
            _print_trace_detail(tree)

    except typer.Exit:
        raise
    except Exception as e:
        fail_api(f"get trace '{trace_id}'", e, as_json=output_json)


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
    journey: Optional[str] = typer.Option(
        None, "--journey", help="Filter by login-journey ID"
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
    """Search traces by journey, endpoint, outcome, principal, or time.

    Filters combine (AND).
    """
    if dry_run:
        _dry_run(
            "campus audit traces search",
            _query_operation("search", {
                "path": path, "status": status,
                "user_id": user, "client_id": client,
                "api_key_id": api_key_id,
                "journey_id": journey,
                "since": since, "until": until,
                "limit": limit, "cursor": cursor,
            }),
        )
        return

    try:
        api = get_audit_client(as_json=output_json)
        result = _unwrap_payload(
            api.traces.search(
                path=path,
                status=status,
                user_id=user,
                client_id=client,
                api_key_id=api_key_id,
                journey_id=journey,
                since=since,
                until=until,
                limit=limit,
                cursor=cursor,
            )
        )

        if output_json:
            print_json(result)
        else:
            _print_trace_page(result)

    except typer.Exit:
        raise
    except Exception as e:
        fail_api("search traces", e, as_json=output_json)
