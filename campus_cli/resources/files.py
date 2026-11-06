"""File-storage commands (campus-cli#4 Phase B).

Files are content-addressed by-slug records in campus.api: the slug is
the stable address, replacing content under a slug keeps the address.
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

file_app = typer.Typer(help="File commands (campus.api)")
console = Console()


def _rec(record) -> dict:
    """Normalize a record (dict for files, model for hosted apps)."""
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
                r.get("content_type") or "-",
                str(r.get("content_size", "-")),
            ]
            for r in records
        ],
    )


@file_app.command("list")
def file_list(
    prefix: str | None = typer.Option(
        None, "--prefix", help="Only slugs starting with this prefix"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """List file records (optionally by slug prefix)."""
    if dry_run:
        lines = ["files = campus.api.files.list("]
        if prefix:
            lines.append(f"    prefix={prefix!r},")
        lines += [")", "for f in files:", "    print(f.get('slug'))"]
        print_python_api("campus file list", lines)
        return

    try:
        api = get_api_client()
        records = [_rec(r) for r in api.api_files.list(prefix=prefix)]

        if output_json:
            print_json(records)
        elif not records:
            console.print("[dim]No files found.[/dim]")
        else:
            console.print(f"[bold]Found {len(records)} file(s):[/bold]\n")
            _print_record_table(records)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to list files: {e}")
        raise typer.Exit(1) from e


@file_app.command("get-meta")
def file_get_meta(
    slug: str = typer.Option(..., "--slug", help="File slug"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Show a file record's metadata."""
    if dry_run:
        print_python_api(
            "campus file get-meta",
            [
                f"meta = campus.api.files.get_meta({slug!r})",
                "print(meta)",
            ],
        )
        return

    try:
        api = get_api_client()
        record = _rec(api.api_files.get_meta(slug))

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
        print_error(f"Failed to get metadata for file '{slug}': {e}")
        raise typer.Exit(1) from e


@file_app.command("get-content")
def file_get_content(
    slug: str = typer.Option(..., "--slug", help="File slug"),
    output: Path | None = typer.Option(  # noqa: B008
        None, "--output", "-o", help="Write the bytes to this path"
    ),
    dry_run: bool = dry_run_option(),
) -> None:
    """Fetch a file's raw content (to stdout or --output path)."""
    if dry_run:
        out = f", output={str(output)!r}" if output else ""
        print_python_api(
            "campus file get-content",
            [
                f"content = campus.api.files.get_content({slug!r})",
                f"# write to{output or ' stdout'}{out.strip(', ')}",
                "print(content)",
            ],
        )
        return

    try:
        api = get_api_client()
        content = api.api_files.get_content(slug)

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
        print_error(f"Failed to get content for file '{slug}': {e}")
        raise typer.Exit(1) from e


@file_app.command("put")
def file_put(
    slug: str = typer.Option(..., "--slug", help="File slug (stable address)"),
    file: Path = typer.Option(  # noqa: B008
        ..., "--file", "-f", help="Local file whose bytes to upload"
    ),
    content_type: str | None = typer.Option(
        None, "--content-type", help="MIME type (defaults upstream to"
        " application/octet-stream)"
    ),
    name: str | None = typer.Option(
        None, "--name", help="Display name (stored on new records)"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Create or replace a file's content by slug (upsert)."""
    data = Path(file).read_bytes()

    if dry_run:
        put_kwargs = [f"    {slug!r},", f"    <{len(data)} bytes>,"]
        if content_type:
            put_kwargs.append(f"    content_type={content_type!r},")
        if name:
            put_kwargs.append(f"    name={name!r},")
        print_python_api(
            "campus file put",
            [
                "record = campus.api.files.put_by_slug(",
                *put_kwargs,
                ")",
                "print(record)",
            ],
        )
        return

    try:
        api = get_api_client()
        record = _rec(api.api_files.put_by_slug(
            slug, data, content_type=content_type, name=name,
        ))

        if output_json:
            print_json(record)
        else:
            print_success(
                f"Stored {len(data)} bytes under slug '{slug}'."
            )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to store file '{slug}': {e}")
        raise typer.Exit(1) from e


@file_app.command("delete")
def file_delete(
    slug: str = typer.Option(..., "--slug", help="File slug"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Delete a file record by slug."""
    if dry_run:
        print_python_api(
            "campus file delete",
            [f"campus.api.files.delete_by_slug({slug!r})"],
        )
        return

    confirm_destructive(f"delete file '{slug}'", confirm)

    try:
        api = get_api_client()
        api.api_files.delete_by_slug(slug)
        print_success(f"File '{slug}' deleted.")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to delete file '{slug}': {e}")
        raise typer.Exit(1) from e
