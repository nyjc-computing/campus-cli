"""Hosted-app commands (campus-cli#4 Phase B).

HostedApps are single-file HTML apps published to Campus app hosting
(classroom#81): the slug is the app's stable address, and content
defaults to text/html upstream.
"""

from pathlib import Path

import typer
from rich.console import Console

from campus_cli.auth.common import (
    confirm_destructive,
    dry_run_option,
    get_api_client,
)
from campus_cli.utils.output import (
    print_error,
    print_json,
    print_python_api,
    print_success,
    print_table,
)

app_app = typer.Typer(help="Hosted-app commands (campus.api)")
console = Console()

DEFAULT_CONTENT_TYPE = "text/html"


def _rec(record) -> dict:
    """Normalize a record (model for hosted apps, dict defensively)."""
    if hasattr(record, "to_resource"):
        return record.to_resource()
    return record


def _print_record_table(records: list[dict]) -> None:
    print_table(
        headers=["Slug", "Name", "Content type", "Size"],
        rows=[
            [
                r.get("slug", "-"),
                r.get("name") or "-",
                r.get("content_type") or DEFAULT_CONTENT_TYPE,
                str(r.get("content_size", "-")),
            ]
            for r in records
        ],
    )


@app_app.command("list")
def app_list(
    prefix: str | None = typer.Option(
        None, "--prefix", help="Only slugs starting with this prefix"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """List hosted apps (optionally by slug prefix)."""
    if dry_run:
        lines = ["apps = campus.api.hostedapps.list("]
        if prefix:
            lines.append(f"    prefix={prefix!r},")
        lines += [")", "for a in apps:", "    print(a.get('slug'))"]
        print_python_api("campus app list", lines)
        return

    try:
        api = get_api_client()
        records = [_rec(r) for r in api.api_hostedapps.list(prefix=prefix)]

        if output_json:
            print_json(records)
        elif not records:
            console.print("[dim]No hosted apps found.[/dim]")
        else:
            console.print(f"[bold]Found {len(records)} app(s):[/bold]\n")
            _print_record_table(records)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to list hosted apps: {e}")
        raise typer.Exit(1) from e


@app_app.command("get-meta")
def app_get_meta(
    slug: str = typer.Option(..., "--slug", help="App slug"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Show a hosted app's metadata."""
    if dry_run:
        print_python_api(
            "campus app get-meta",
            [
                f"meta = campus.api.hostedapps.get_meta({slug!r})",
                "print(meta)",
            ],
        )
        return

    try:
        api = get_api_client()
        record = _rec(api.api_hostedapps.get_meta(slug))

        if output_json:
            print_json(record)
        else:
            console.print(f"[bold]Slug:[/bold] {record.get('slug', slug)}")
            for key in ("name", "content_type", "content_size"):
                if record.get(key) is not None:
                    console.print(f"[bold]{key}:[/bold] {record[key]}")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to get metadata for app '{slug}': {e}")
        raise typer.Exit(1) from e


@app_app.command("get-content")
def app_get_content(
    slug: str = typer.Option(..., "--slug", help="App slug"),
    output: Path | None = typer.Option(  # noqa: B008
        None, "--output", "-o", help="Write the bytes to this path"
    ),
    dry_run: bool = dry_run_option(),
) -> None:
    """Fetch a hosted app's raw HTML (to stdout or --output path)."""
    if dry_run:
        print_python_api(
            "campus app get-content",
            [
                f"content = campus.api.hostedapps.get_content({slug!r})",
                "print(content)",
            ],
        )
        return

    try:
        api = get_api_client()
        content = api.api_hostedapps.get_content(slug)

        if output:
            Path(output).write_bytes(content)
            print_success(
                f"Wrote {len(content)} bytes to '{output}' (slug '{slug}')."
            )
        else:
            console.print(content.decode("utf-8", errors="replace"))

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to get content for app '{slug}': {e}")
        raise typer.Exit(1) from e


@app_app.command("put")
def app_put(
    slug: str = typer.Option(..., "--slug", help="App slug (stable address)"),
    file: Path = typer.Option(  # noqa: B008
        ..., "--file", "-f", help="Local single-file HTML app to publish"
    ),
    content_type: str | None = typer.Option(
        None, "--content-type",
        help="MIME type (defaults to text/html upstream)"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Publish or replace a hosted app by slug (upsert)."""
    data = Path(file).read_bytes()

    if dry_run:
        put_kwargs = [f"    {slug!r},", f"    <{len(data)} bytes>,"]
        if content_type:
            put_kwargs.append(f"    content_type={content_type!r},")
        print_python_api(
            "campus app put",
            [
                "record = campus.api.hostedapps.put_by_slug(",
                *put_kwargs,
                ")",
                "print(record)",
            ],
        )
        return

    try:
        api = get_api_client()
        record = _rec(api.api_hostedapps.put_by_slug(
            slug, data, content_type=content_type,
        ))

        if output_json:
            print_json(record)
        else:
            print_success(
                f"Published {len(data)} bytes under slug '{slug}'."
            )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to publish app '{slug}': {e}")
        raise typer.Exit(1) from e


@app_app.command("delete")
def app_delete(
    slug: str = typer.Option(..., "--slug", help="App slug"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Delete a hosted app by slug."""
    if dry_run:
        print_python_api(
            "campus app delete",
            [f"campus.api.hostedapps.delete_by_slug({slug!r})"],
        )
        return

    confirm_destructive(f"delete hosted app '{slug}'", confirm)

    try:
        api = get_api_client()
        api.api_hostedapps.delete_by_slug(slug)
        print_success(f"Hosted app '{slug}' deleted.")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to delete hosted app '{slug}': {e}")
        raise typer.Exit(1) from e
