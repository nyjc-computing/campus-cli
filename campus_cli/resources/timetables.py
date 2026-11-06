"""Timetable commands (campus-cli#4 Phases A and C)."""

import json
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


@timetable_app.command("set-current")
def timetable_set_current(
    timetable_id: str = typer.Option(..., "--timetable-id", help="Timetable ID"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation"),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    Set the currently-active timetable (deployment-wide).

    Everyone reading 'campus timetable current' sees this immediately.
    """
    if dry_run:
        print_python_api(
            "campus timetable set-current",
            [f"campus.api.timetable.set_current({timetable_id!r})"],
        )
        return

    confirm_destructive(
        f"set timetable '{timetable_id}' as the CURRENT timetable"
        " (deployment-wide)", confirm
    )

    try:
        api = get_api_client()
        api.api_timetables.set_current(timetable_id)
        print_success(f"Timetable '{timetable_id}' is now current.")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to set the current timetable: {e}")
        raise typer.Exit(1) from e


@timetable_app.command("set-next")
def timetable_set_next(
    timetable_id: str = typer.Option(..., "--timetable-id", help="Timetable ID"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Stage the next (incoming) timetable (deployment-wide)."""
    if dry_run:
        print_python_api(
            "campus timetable set-next",
            [f"campus.api.timetable.set_next({timetable_id!r})"],
        )
        return

    confirm_destructive(
        f"set timetable '{timetable_id}' as the NEXT timetable"
        " (deployment-wide)", confirm
    )

    try:
        api = get_api_client()
        api.api_timetables.set_next(timetable_id)
        print_success(f"Timetable '{timetable_id}' is now staged as next.")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to set the next timetable: {e}")
        raise typer.Exit(1) from e


metadata_app = typer.Typer(help="Timetable metadata")
timetable_app.add_typer(metadata_app, name="metadata")


@metadata_app.command("update")
def metadata_update(
    timetable_id: str = typer.Option(..., "--timetable-id", help="Timetable ID"),
    start_date: str = typer.Option(..., "--start-date", help="Start date (ISO)"),
    end_date: str = typer.Option(..., "--end-date", help="End date (ISO)"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Update a timetable's start and end dates."""
    if dry_run:
        print_python_api(
            "campus timetable metadata update",
            [
                "metadata = campus.api.timetable["
                f"{timetable_id!r}].metadata",
                f"metadata.update(start_date={start_date!r},"
                f" end_date={end_date!r})",
            ],
        )
        return

    try:
        api = get_api_client()
        api.api_timetables[timetable_id].metadata.update(
            start_date=start_date, end_date=end_date
        )
        meta = _format_metadata(api.api_timetables[timetable_id].get())

        if output_json:
            print_json(meta)
        else:
            print_success(
                f"Timetable '{timetable_id}' metadata updated:"
                f" {meta['start_date']} .. {meta['end_date']}"
            )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to update timetable '{timetable_id}' metadata: {e}")
        raise typer.Exit(1) from e



@timetable_app.command("new")
def timetable_new(
    metadata: str = typer.Option(
        ..., "--metadata", "-m",
        help='Timetable metadata as inline JSON, e.g. {"start_date":'
        ' "2027-01-01", "end_date": "2027-06-01", "filename": "2027.json"}'
    ),
    data_file: str = typer.Option(
        ..., "--data-file", "-d",
        help="Path to the timetable data JSON (must contain a"
        " 'lessongroups' key)"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    Create a timetable from metadata JSON and a data JSON file.

    The data document must carry its lesson groups under the key
    'lessongroups' (no underscore - the server rejects
    'lesson_groups' with 400).
    """
    try:
        meta = json.loads(metadata)
    except json.JSONDecodeError as e:
        print_error(f"--metadata is not valid JSON: {e}")
        raise typer.Exit(1) from e
    if not isinstance(meta, dict):
        print_error("--metadata must be a JSON object.")
        raise typer.Exit(1)

    data_path = Path(data_file)
    if not data_path.is_file():
        print_error(f"--data-file not found: {data_file}")
        raise typer.Exit(1)
    try:
        data = json.loads(data_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print_error(f"--data-file is not valid JSON: {e}")
        raise typer.Exit(1) from e
    if not isinstance(data, dict):
        print_error("--data-file must contain a JSON object.")
        raise typer.Exit(1)
    if "lessongroups" not in data:
        hint = (
            " ('lesson_groups' found instead - rename it)"
            if "lesson_groups" in data else ""
        )
        print_error(
            f"--data-file must contain a 'lessongroups' key{hint}."
        )
        raise typer.Exit(1)

    if dry_run:
        print_python_api(
            "campus timetable new",
            [
                "timetable = campus.api.timetable.new(",
                f"    metadata={meta!r},",
                f"    data={{'lessongroups':"
                f" [{len(data['lessongroups'])} groups from"
                f" {data_file!r}]}},",
                ")",
                "print(timetable)",
            ],
        )
        return

    try:
        api = get_api_client()
        created = api.api_timetables.new(metadata=meta, data=data)

        if output_json:
            print_json(created)
        else:
            print_success(
                f"Timetable created from '{data_file}'"
                f" ({len(data['lessongroups'])} lessongroup(s))."
            )
            print_json(created)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to create timetable: {e}")
        raise typer.Exit(1) from e
