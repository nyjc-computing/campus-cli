"""Venue commands (campus#1099): documents-backed venue CRUD.

Venues are managed with a deliberately fluid schema: freeform
`metadata` carries the venue's facts (name, capacity, location, ...)
and `notes` carries freeform markdown. Metadata replaces as a whole
dict on update (merge is the caller's job); `--clear-notes` sends
notes: null upstream. Mutations require the venues.admin role circle.
"""

import json

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

venues_app = typer.Typer(
    help="Venue commands: documents-backed venue CRUD (campus.api)"
)
console = Console()


def _parse_metadata(metadata: str | None) -> dict | None:
    """Parse the --metadata JSON string into a dict."""
    if metadata is None:
        return None
    try:
        parsed = json.loads(metadata)
    except json.JSONDecodeError as e:
        print_error(f"--metadata must be valid JSON: {e}")
        raise typer.Exit(1) from e
    if not isinstance(parsed, dict):
        print_error("--metadata must be a JSON object")
        raise typer.Exit(1)
    return parsed


@venues_app.command("create")
def venue_create(
    metadata: str = typer.Option(
        None, "--metadata",
        help="Initial metadata as a JSON object string"
        " (e.g. '{\"name\": \"B1-01\"}')",
    ),
    notes: str = typer.Option(
        None, "--notes", help="Freeform markdown notes"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Create a venue (venues.admin)."""
    metadata_dict = _parse_metadata(metadata)
    if dry_run:
        args = []
        if metadata_dict is not None:
            args.append(f"metadata={metadata_dict!r}")
        if notes is not None:
            args.append(f"notes={notes!r}")
        print_python_api(
            "campus venue create",
            [
                f"venue = campus.api.venues.create({', '.join(args)})",
                "print(venue.to_resource())",
            ],
        )
        return

    confirm_destructive("create a venue", confirm)

    try:
        api = get_api_client()
        venue = api.api_venues.create(
            metadata=metadata_dict,
            notes=notes,
        )
        record = venue.to_resource()

        if output_json:
            print_json(record)
        else:
            print_success(f"Venue created: {record['id']}")
            print_json(record)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to create the venue: {e}")
        raise typer.Exit(1) from e


@venues_app.command("get")
def venue_get(
    venue_id: str = typer.Option(..., "--venue-id", help="The venue ID"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Show a venue."""
    if dry_run:
        print_python_api(
            "campus venue get",
            [f"print(campus.api.venues[{venue_id!r}].get().to_resource())"],
        )
        return

    try:
        api = get_api_client()
        venue = api.api_venues[venue_id].get()
        record = venue.to_resource()

        if output_json:
            print_json(record)
        else:
            print_json(record)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to get the venue '{venue_id}': {e}")
        raise typer.Exit(1) from e


@venues_app.command("list")
def venue_list(
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """List all venues, oldest first."""
    if dry_run:
        print_python_api(
            "campus venue list",
            [
                "venues = campus.api.venues.list()",
                "for v in venues:",
                "    r = v.to_resource()",
                "    print(r['id'], r['metadata'].get('name'), r['notes'])",
            ],
        )
        return

    try:
        api = get_api_client()
        records = [v.to_resource() for v in api.api_venues.list()]

        if output_json:
            print_json(records)
        elif not records:
            console.print("[dim]No venues.[/dim]")
        else:
            console.print(f"[bold]{len(records)} venue(s):[/bold]\n")
            print_table(
                headers=["ID", "Name", "Notes"],
                rows=[
                    [
                        r["id"],
                        str(r["metadata"].get("name") or "-"),
                        (
                            f"{r['notes'][:40]}..."
                            if r.get("notes") and len(r["notes"]) > 40
                            else (r.get("notes") or "-")
                        ),
                    ]
                    for r in records
                ],
            )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to list venues: {e}")
        raise typer.Exit(1) from e


@venues_app.command("update")
def venue_update(
    venue_id: str = typer.Option(..., "--venue-id", help="The venue ID"),
    metadata: str = typer.Option(
        None, "--metadata",
        help="Replacement metadata as a JSON object string"
        " (replaces the whole dict; merge is your job)",
    ),
    notes: str = typer.Option(
        None, "--notes", help="Replacement markdown notes"
    ),
    clear_notes: bool = typer.Option(
        False, "--clear-notes",
        help="Clear the notes (sends notes: null; --notes is ignored)"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Patch a venue; given fields replace, absent fields stay (venues.admin)."""
    metadata_dict = _parse_metadata(metadata)
    if metadata_dict is None and notes is None and not clear_notes:
        print_error(
            "Nothing to update: give --metadata and/or --notes,"
            " or --clear-notes"
        )
        raise typer.Exit(1)
    if dry_run:
        args = []
        if metadata_dict is not None:
            args.append(f"metadata={metadata_dict!r}")
        if clear_notes:
            args.append("clear_notes=True")
        elif notes is not None:
            args.append(f"notes={notes!r}")
        print_python_api(
            "campus venue update",
            [
                "venue = campus.api.venues["
                f"{venue_id!r}].update({', '.join(args)})",
                "print(venue.to_resource())",
            ],
        )
        return

    confirm_destructive(f"update venue '{venue_id}'", confirm)

    try:
        api = get_api_client()
        venue = api.api_venues[venue_id].update(
            metadata=metadata_dict,
            notes=None if clear_notes else notes,
            clear_notes=clear_notes,
        )
        record = venue.to_resource()

        if output_json:
            print_json(record)
        else:
            print_success(f"Venue updated: {record['id']}")
            print_json(record)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to update the venue '{venue_id}': {e}")
        raise typer.Exit(1) from e


@venues_app.command("delete")
def venue_delete(
    venue_id: str = typer.Option(..., "--venue-id", help="The venue ID"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Delete a venue (venues.admin)."""
    if dry_run:
        print_python_api(
            "campus venue delete",
            [f"campus.api.venues[{venue_id!r}].delete()"],
        )
        return

    confirm_destructive(f"delete venue '{venue_id}'", confirm)

    try:
        api = get_api_client()
        api.api_venues[venue_id].delete()

        if output_json:
            print_json({"deleted": venue_id})
        else:
            print_success(f"Venue deleted: {venue_id}")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to delete the venue '{venue_id}': {e}")
        raise typer.Exit(1) from e
