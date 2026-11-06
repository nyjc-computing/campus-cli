"""Circle read commands (campus-cli#4 Phase A)."""

import typer
from rich.console import Console

from campus_cli.auth.common import dry_run_option, get_api_client
from campus_cli.utils.output import (
    print_error,
    print_json,
    print_python_api,
    print_table,
)

circle_app = typer.Typer(help="Circle commands (campus.api)")
console = Console()

members_app = typer.Typer(help="Circle member reads")
circle_app.add_typer(members_app, name="members")


def _iso(value):
    """Render datetimes as ISO strings; strings and None pass through."""
    return value.isoformat() if hasattr(value, "isoformat") else value


def _format_circle(circle) -> dict:
    """Project a Circle model into display/JSON fields."""
    members = circle.members or {}
    return {
        "id": circle.id,
        "name": circle.name,
        "description": circle.description,
        "tag": circle.tag,
        "created_at": _iso(circle.created_at),
        "members": members,
        "member_count": len(members),
    }


def _print_circle(c: dict) -> None:
    console.print(f"[bold]ID:[/bold] {c['id']}")
    console.print(f"[bold]Name:[/bold] {c['name']}")
    if c["description"]:
        console.print(f"[bold]Description:[/bold] {c['description']}")
    if c["tag"]:
        console.print(f"[bold]Tag:[/bold] {c['tag']}")
    console.print(f"[bold]Members:[/bold] {c['member_count']}")
    if c["created_at"]:
        console.print(f"[bold]Created:[/bold] {c['created_at']}")


@circle_app.command("list")
def circle_list(
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """List circles."""
    if dry_run:
        print_python_api(
            "campus circle list",
            [
                "circles = campus.api.circles.list()",
                "for c in circles:",
                "    print(c.id, c.name)",
            ],
        )
        return

    try:
        api = get_api_client()
        circles = api.api_circles.list()
        formatted = [_format_circle(c) for c in circles]

        if output_json:
            print_json(formatted)
        elif not formatted:
            console.print("[dim]No circles found.[/dim]")
        else:
            console.print(f"[bold]Found {len(formatted)} circle(s):[/bold]\n")
            print_table(
                headers=["ID", "Name", "Tag", "Members"],
                rows=[
                    [c["id"], c["name"], c["tag"] or "-", str(c["member_count"])]
                    for c in formatted
                ],
            )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to list circles: {e}")
        raise typer.Exit(1) from e


@circle_app.command("get")
def circle_get(
    circle_id: str = typer.Option(..., "--circle-id", help="Circle ID"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Show one circle."""
    if dry_run:
        print_python_api(
            "campus circle get",
            [
                f"circle = campus.api.circles[{circle_id!r}].get()",
                "print(circle.name, circle.tag)",
            ],
        )
        return

    try:
        api = get_api_client()
        circle = api.api_circles[circle_id].get()
        formatted = _format_circle(circle)

        if output_json:
            print_json(formatted)
        else:
            _print_circle(formatted)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to get circle '{circle_id}': {e}")
        raise typer.Exit(1) from e


@members_app.command("list")
def circle_members_list(
    circle_id: str = typer.Option(..., "--circle-id", help="Circle ID"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """List a circle's members with their access values."""
    if dry_run:
        print_python_api(
            "campus circle members list",
            [
                "members = campus.api.circles["
                f"{circle_id!r}].members.list()",
                "for member_id, access in members.items():",
                "    print(member_id, access)",
            ],
        )
        return

    try:
        api = get_api_client()
        members = api.api_circles[circle_id].members.list()

        if output_json:
            print_json(members)
        elif not members:
            console.print("[dim]No members found.[/dim]")
        else:
            console.print(f"[bold]Found {len(members)} member(s):[/bold]\n")
            print_table(
                headers=["Member ID", "Access"],
                rows=[
                    [member_id, str(access)]
                    for member_id, access in members.items()
                ],
            )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to list members of circle '{circle_id}': {e}")
        raise typer.Exit(1) from e
