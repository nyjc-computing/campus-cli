"""Timetable read commands (campus-cli#4 Phase A)."""

import typer
from rich.console import Console

from campus_cli.auth.common import dry_run_option, get_api_client
from campus_cli.utils.output import (
    print_error,
    print_json,
    print_python_api,
    print_table,
)

timetable_app = typer.Typer(help="Timetable commands (campus.api)")
console = Console()


def _iso(value):
    """Render datetimes as ISO strings; strings and None pass through."""
    return value.isoformat() if hasattr(value, "isoformat") else value


def _format_metadata(meta) -> dict:
    """Project a TimetableMetadata model into display/JSON fields."""
    return {
        "id": meta.id,
        "filename": meta.filename,
        "start_date": meta.start_date,
        "end_date": meta.end_date,
        "created_at": _iso(meta.created_at),
    }


@timetable_app.command("list")
def timetable_list(
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """List timetables (metadata records)."""
    if dry_run:
        print_python_api(
            "campus timetable list",
            [
                "timetables = campus.api.timetable.list()",
                "for t in timetables:",
                "    print(t.id, t.filename, t.start_date, t.end_date)",
            ],
        )
        return

    try:
        api = get_api_client()
        timetables = api.api_timetables.list()
        formatted = [_format_metadata(t) for t in timetables]

        if output_json:
            print_json(formatted)
        elif not formatted:
            console.print("[dim]No timetables found.[/dim]")
        else:
            console.print(f"[bold]Found {len(formatted)} timetable(s):[/bold]\n")
            print_table(
                headers=["ID", "Filename", "Start", "End"],
                rows=[
                    [t["id"], t["filename"], t["start_date"], t["end_date"]]
                    for t in formatted
                ],
            )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to list timetables: {e}")
        raise typer.Exit(1) from e


@timetable_app.command("current")
def timetable_current(
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Show the ID of the currently-active timetable."""
    if dry_run:
        print_python_api(
            "campus timetable current",
            ["print(campus.api.timetable.get_current())"],
        )
        return

    try:
        api = get_api_client()
        current = api.api_timetables.get_current()

        if output_json:
            print_json({"current": current})
        else:
            console.print(f"[bold]Current timetable:[/bold] {current}")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to get the current timetable: {e}")
        raise typer.Exit(1) from e


@timetable_app.command("next")
def timetable_next(
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Show the ID of the next (incoming) timetable."""
    if dry_run:
        print_python_api(
            "campus timetable next",
            ["print(campus.api.timetable.get_next())"],
        )
        return

    try:
        api = get_api_client()
        nxt = api.api_timetables.get_next()

        if output_json:
            print_json({"next": nxt})
        else:
            console.print(f"[bold]Next timetable:[/bold] {nxt}")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to get the next timetable: {e}")
        raise typer.Exit(1) from e


@timetable_app.command("get")
def timetable_get(
    timetable_id: str = typer.Option(..., "--timetable-id", help="Timetable ID"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Show one timetable (metadata plus its entries)."""
    if dry_run:
        print_python_api(
            "campus timetable get",
            [
                f"timetable = campus.api.timetable[{timetable_id!r}].get()",
                "print(timetable.filename, timetable.start_date,"
                " timetable.end_date)",
            ],
        )
        return

    try:
        api = get_api_client()
        timetable = api.api_timetables[timetable_id].get()

        if output_json:
            print_json(timetable.to_resource())
        else:
            console.print(f"[bold]ID:[/bold] {timetable.id}")
            console.print(f"[bold]Filename:[/bold] {timetable.filename}")
            console.print(f"[bold]Start:[/bold] {timetable.start_date}")
            console.print(f"[bold]End:[/bold] {timetable.end_date}")
            entries = timetable.entries or []
            console.print(f"[bold]Entries:[/bold] {len(entries)}")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to get timetable '{timetable_id}': {e}")
        raise typer.Exit(1) from e


@timetable_app.command("entries")
def timetable_entries(
    timetable_id: str = typer.Option(..., "--timetable-id", help="Timetable ID"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """List one timetable's entries (weekly lesson slots)."""
    if dry_run:
        print_python_api(
            "campus timetable entries",
            [
                "entries = campus.api.timetable["
                f"{timetable_id!r}].entries.list()",
                "for e in entries:",
                "    print(e.weekday, e.timeslot, e.venue, e.label)",
            ],
        )
        return

    try:
        api = get_api_client()
        entries = api.api_timetables[timetable_id].entries.list()

        if output_json:
            print_json([
                {
                    "id": e.id,
                    "lessongroup_id": e.lessongroup_id,
                    "venue": e.venue,
                    "weekday": e.weekday,
                    "timeslot": e.timeslot,
                    "label": e.label,
                }
                for e in entries
            ])
        elif not entries:
            console.print("[dim]No entries found.[/dim]")
        else:
            console.print(f"[bold]Found {len(entries)} entry(ies):[/bold]\n")
            print_table(
                headers=["Weekday", "Timeslot", "Venue", "Label"],
                rows=[
                    [str(e.weekday), str(e.timeslot), e.venue, e.label or "-"]
                    for e in entries
                ],
            )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to list entries for timetable '{timetable_id}': {e}")
        raise typer.Exit(1) from e
