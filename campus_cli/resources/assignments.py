"""Assignment read commands (campus-cli#4 Phase A)."""

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

assignment_app = typer.Typer(help="Assignment commands (campus.api)")
console = Console()

links_app = typer.Typer(help="Assignment Google Classroom links")
assignment_app.add_typer(links_app, name="links")


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


@assignment_app.command("new")
def assignment_new(
    title: str = typer.Option(..., "--title", "-t", help="Assignment title"),
    description: str | None = typer.Option(
        None, "--description", "-d", help="Assignment description"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    Create an assignment.

    Questions are structured payloads (Phase C, campus-cli#4); attach
    Google Classroom course/coursework links with
    'campus assignment links add'.
    """
    if dry_run:
        new_kwargs = [f"    title={title!r},"]
        if description:
            new_kwargs.append(f"    description={description!r},")
        print_python_api(
            "campus assignment new",
            [
                "assignment = campus.api.assignments.new(",
                *new_kwargs,
                ")",
                "print(assignment.id)",
            ],
        )
        return

    try:
        api = get_api_client()
        assignment = api.api_assignments.new(
            title=title, description=description
        )
        formatted = _format_assignment(assignment)

        if output_json:
            print_json(formatted)
        else:
            print_success(f"Assignment '{title}' created.")
            _print_assignment(formatted)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to create assignment: {e}")
        raise typer.Exit(1) from e


@assignment_app.command("update")
def assignment_update(
    assignment_id: str = typer.Option(..., "--assignment-id", help="Assignment ID"),
    title: str | None = typer.Option(None, "--title", "-t", help="New title"),
    description: str | None = typer.Option(
        None, "--description", "-d", help="New description"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Update an assignment's title and/or description."""
    if not (title or description):
        print_error("Give at least one of --title or --description.")
        raise typer.Exit(1)

    if dry_run:
        update_kwargs = []
        if title:
            update_kwargs.append(f"title={title!r}")
        if description:
            update_kwargs.append(f"description={description!r}")
        print_python_api(
            "campus assignment update",
            [
                f"campus.api.assignments[{assignment_id!r}].update(",
                *(f"    {kwarg}," for kwarg in update_kwargs),
                ")",
            ],
        )
        return

    try:
        api = get_api_client()
        fields: dict = {}
        if title:
            fields["title"] = title
        if description:
            fields["description"] = description
        api.api_assignments[assignment_id].update(**fields)
        assignment = api.api_assignments[assignment_id].get()
        formatted = _format_assignment(assignment)

        if output_json:
            print_json(formatted)
        else:
            print_success(f"Assignment '{assignment_id}' updated.")
            _print_assignment(formatted)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to update assignment '{assignment_id}': {e}")
        raise typer.Exit(1) from e


@assignment_app.command("delete")
def assignment_delete(
    assignment_id: str = typer.Option(..., "--assignment-id", help="Assignment ID"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Delete an assignment."""
    if dry_run:
        print_python_api(
            "campus assignment delete",
            [f"campus.api.assignments[{assignment_id!r}].delete()"],
        )
        return

    confirm_destructive(f"delete assignment '{assignment_id}'", confirm)

    try:
        api = get_api_client()
        api.api_assignments[assignment_id].delete()
        print_success(f"Assignment '{assignment_id}' deleted.")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to delete assignment '{assignment_id}': {e}")
        raise typer.Exit(1) from e


@links_app.command("add")
def links_add(
    assignment_id: str = typer.Option(..., "--assignment-id", help="Assignment ID"),
    course_id: str = typer.Option(
        ..., "--course-id", help="Google Classroom course ID"
    ),
    coursework_id: str = typer.Option(
        ..., "--coursework-id", help="Google Classroom coursework ID"
    ),
    attachment_id: str | None = typer.Option(
        None, "--attachment-id", help="Classroom attachment ID (optional)"
    ),
    dry_run: bool = dry_run_option(),
) -> None:
    """Attach a Google Classroom course/coursework link to an assignment."""
    if dry_run:
        add_kwargs = [
            f"    course_id={course_id!r},",
            f"    coursework_id={coursework_id!r},",
        ]
        if attachment_id:
            add_kwargs.append(f"    attachment_id={attachment_id!r},")
        print_python_api(
            "campus assignment links add",
            [
                f"links = campus.api.assignments[{assignment_id!r}].links",
                "links.add(",
                *add_kwargs,
                ")",
            ],
        )
        return

    try:
        api = get_api_client()
        api.api_assignments[assignment_id].links.add(
            course_id=course_id,
            coursework_id=coursework_id,
            attachment_id=attachment_id,
        )
        print_success(
            f"Classroom link added to assignment '{assignment_id}'."
        )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(
            f"Failed to add Classroom link to assignment '{assignment_id}': {e}"
        )
        raise typer.Exit(1) from e
