"""Circle read commands (campus-cli#4 Phase A)."""

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


@circle_app.command("new")
def circle_new(
    name: str = typer.Option(..., "--name", "-n", help="Circle name (unique)"),
    tag: str = typer.Option(..., "--tag", help="Circle tag, e.g. 'class', 'project'"),
    description: str | None = typer.Option(
        None, "--description", "-d", help="Circle description"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Create a circle (the server rejects colliding names with 409)."""
    if dry_run:
        new_kwargs = [
            f"    name={name!r},",
            f"    tag={tag!r},",
        ]
        if description:
            new_kwargs.append(f"    description={description!r},")
        print_python_api(
            "campus circle new",
            [
                "circle = campus.api.circles.new(",
                *new_kwargs,
                ")",
                "print(circle.id)",
            ],
        )
        return

    try:
        api = get_api_client()
        circle = api.api_circles.new(
            name=name, tag=tag, description=description
        )
        formatted = _format_circle(circle)

        if output_json:
            print_json(formatted)
        else:
            print_success(f"Circle '{name}' created.")
            _print_circle(formatted)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to create circle: {e}")
        raise typer.Exit(1) from e


@circle_app.command("update")
def circle_update(
    circle_id: str = typer.Option(..., "--circle-id", help="Circle ID"),
    name: str = typer.Option(
        ..., "--name", "-n",
        help="New circle name (the server requires name on every PATCH)"
    ),
    description: str | None = typer.Option(
        None, "--description", "-d",
        help="New description (unchanged when omitted)"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Update a circle's name and/or description."""
    if dry_run:
        update_kwargs = [f"name={name!r}"]
        if description:
            update_kwargs.append(f"description={description!r}")
        print_python_api(
            "campus circle update",
            [
                f"campus.api.circles[{circle_id!r}].update(",
                *(f"    {kwarg}," for kwarg in update_kwargs),
                ")",
            ],
        )
        return

    try:
        api = get_api_client()
        api.api_circles[circle_id].update(name=name, description=description)
        circle = api.api_circles[circle_id].get()
        formatted = _format_circle(circle)

        if output_json:
            print_json(formatted)
        else:
            print_success(f"Circle '{circle_id}' updated.")
            _print_circle(formatted)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to update circle '{circle_id}': {e}")
        raise typer.Exit(1) from e


@circle_app.command("delete")
def circle_delete(
    circle_id: str = typer.Option(..., "--circle-id", help="Circle ID"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Delete a circle."""
    if dry_run:
        print_python_api(
            "campus circle delete",
            [f"campus.api.circles[{circle_id!r}].delete()"],
        )
        return

    confirm_destructive(f"delete circle '{circle_id}'", confirm)

    try:
        api = get_api_client()
        api.api_circles[circle_id].delete()
        print_success(f"Circle '{circle_id}' deleted.")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to delete circle '{circle_id}': {e}")
        raise typer.Exit(1) from e


@members_app.command("add")
def members_add(
    circle_id: str = typer.Option(..., "--circle-id", help="Circle ID"),
    member_id: str = typer.Option(..., "--member-id", help="Member (user) ID"),
    access: int = typer.Option(..., "--access", help="Access value"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Add a member with an access value (errors if already a member)."""
    if dry_run:
        print_python_api(
            "campus circle members add",
            [
                "members = campus.api.circles["
                f"{circle_id!r}].members",
                f"members.add({member_id!r}, {access})",
            ],
        )
        return

    try:
        api = get_api_client()
        api.api_circles[circle_id].members.add(member_id, access)
        print_success(f"Member '{member_id}' added to circle '{circle_id}'.")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to add member to circle '{circle_id}': {e}")
        raise typer.Exit(1) from e


@members_app.command("set")
def members_set(
    circle_id: str = typer.Option(..., "--circle-id", help="Circle ID"),
    member_id: str = typer.Option(..., "--member-id", help="Member (user) ID"),
    access: int = typer.Option(..., "--access", help="Access value"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Set a member's access value (upsert — no error when unchanged)."""
    if dry_run:
        print_python_api(
            "campus circle members set",
            [
                "members = campus.api.circles["
                f"{circle_id!r}].members",
                f"members.set({member_id!r}, {access})",
            ],
        )
        return

    try:
        api = get_api_client()
        api.api_circles[circle_id].members.set(member_id, access)
        print_success(
            f"Access for '{member_id}' set to {access} on circle"
            f" '{circle_id}'."
        )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to set member access on circle '{circle_id}': {e}")
        raise typer.Exit(1) from e


@members_app.command("remove")
def members_remove(
    circle_id: str = typer.Option(..., "--circle-id", help="Circle ID"),
    member_id: str = typer.Option(..., "--member-id", help="Member (user) ID"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Remove a member from a circle."""
    if dry_run:
        print_python_api(
            "campus circle members remove",
            [
                "members = campus.api.circles["
                f"{circle_id!r}].members",
                f"members.remove({member_id!r})",
            ],
        )
        return

    confirm_destructive(
        f"remove member '{member_id}' from circle '{circle_id}'", confirm
    )

    try:
        api = get_api_client()
        api.api_circles[circle_id].members.remove(member_id)
        print_success(
            f"Member '{member_id}' removed from circle '{circle_id}'."
        )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to remove member from circle '{circle_id}': {e}")
        raise typer.Exit(1) from e
