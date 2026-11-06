"""Assignment read commands (campus-cli#4 Phase A)."""

import typer
from rich.console import Console

from campus_cli.auth.common import dry_run_option, get_api_client
from campus_cli.utils.output import (
    print_error,
    print_json,
    print_python_api,
    print_table,
)

assignment_app = typer.Typer(help="Assignment commands (campus.api)")
console = Console()


def _iso(value):
    """Render datetimes as ISO strings; strings and None pass through."""
    return value.isoformat() if hasattr(value, "isoformat") else value


def _format_assignment(assignment) -> dict:
    """Project an Assignment model into display/JSON fields."""
    return {
        "id": assignment.id,
        "title": assignment.title,
        "description": assignment.description,
        "created_by": assignment.created_by,
        "created_at": _iso(assignment.created_at),
        "updated_at": _iso(assignment.updated_at),
        "questions": assignment.questions or [],
        "classroom_links": assignment.classroom_links or [],
    }


def _print_assignment(a: dict) -> None:
    console.print(f"[bold]ID:[/bold] {a['id']}")
    console.print(f"[bold]Title:[/bold] {a['title']}")
    if a["description"]:
        console.print(f"[bold]Description:[/bold] {a['description']}")
    if a["created_by"]:
        console.print(f"[bold]Created by:[/bold] {a['created_by']}")
    console.print(f"[bold]Questions:[/bold] {len(a['questions'])}")
    if a["classroom_links"]:
        console.print(
            f"[bold]Classroom links:[/bold] {len(a['classroom_links'])}"
        )
    if a["created_at"]:
        console.print(f"[bold]Created:[/bold] {a['created_at']}")
    if a["updated_at"]:
        console.print(f"[bold]Updated:[/bold] {a['updated_at']}")


@assignment_app.command("list")
def assignment_list(
    created_by: str | None = typer.Option(
        None, "--created-by", help="Filter by creator"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """List assignments, optionally only one creator's."""
    if dry_run:
        lines = ["assignments = campus.api.assignments.list("]
        if created_by:
            lines.append(f"    created_by={created_by!r},")
        lines += [")", "for a in assignments:", "    print(a.id, a.title)"]
        print_python_api("campus assignment list", lines)
        return

    try:
        api = get_api_client()
        assignments = api.api_assignments.list(created_by=created_by)

        if output_json:
            print_json([_format_assignment(a) for a in assignments])
        elif not assignments:
            console.print("[dim]No assignments found.[/dim]")
        else:
            console.print(
                f"[bold]Found {len(assignments)} assignment(s):[/bold]\n"
            )
            print_table(
                headers=["ID", "Title", "Created by", "Created"],
                rows=[
                    [
                        a["id"],
                        a["title"],
                        a["created_by"] or "-",
                        a["created_at"] or "-",
                    ]
                    for a in map(_format_assignment, assignments)
                ],
            )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to list assignments: {e}")
        raise typer.Exit(1) from e


@assignment_app.command("get")
def assignment_get(
    assignment_id: str = typer.Option(..., "--assignment-id", help="Assignment ID"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Show one assignment."""
    if dry_run:
        print_python_api(
            "campus assignment get",
            [
                f"assignment = campus.api.assignments[{assignment_id!r}].get()",
                "print(assignment.title)",
            ],
        )
        return

    try:
        api = get_api_client()
        assignment = api.api_assignments[assignment_id].get()
        formatted = _format_assignment(assignment)

        if output_json:
            print_json(formatted)
        else:
            _print_assignment(formatted)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to get assignment '{assignment_id}': {e}")
        raise typer.Exit(1) from e
