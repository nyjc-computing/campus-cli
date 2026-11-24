"""User management commands (#42).

Reads (list/get) run through campus.api's read-only directory facade
(#1226): staff read the full user base via the staff:viewer baseline
— no grant row needed — and other authenticated callers get their
circle-visible slice plus their own record. Mutation commands
unchanged: the campus#883 grant store authority model still applies,
each needing a matching grant row AND the matching users:* scope on
the token — either leg alone confers nothing (campus invariant A8).
The env-nominated super-admin root needs neither. Inspect and
administer rows with `campus grant`:

- activate: users:mod (implies read)
- new/edit: users:write (implies mod and read)
- delete:   users:admin (implies write)
"""

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
)

user_app = typer.Typer(help="User management commands")
console = Console()


def _iso(value) -> str | None:
    """Render a datetime-or-ISO-string field verbatim as a string."""
    return value.isoformat() if hasattr(value, "isoformat") else value


def _format_user(user) -> dict:
    """Format a user for output.

    Args:
        user: A campus.model.User instance (auth management surface)
            or a directory record dict (the campus.api facade)

    Returns:
        Dict representation of the user
    """
    if isinstance(user, dict):
        return {
            "id": user.get("id"),
            "email": user.get("email"),
            "name": user.get("name"),
            "created_at": _iso(user.get("created_at")),
            "activated_at": _iso(user.get("activated_at")),
        }
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "created_at": _iso(user.created_at),
        "activated_at": _iso(user.activated_at),
    }


def _print_user_details(user_data: dict) -> None:
    """Print user details in a formatted way.

    Args:
        user_data: Dict with user information
    """
    console.print(f"[bold]User ID:[/bold] {user_data.get('id', 'N/A')}")
    console.print(f"[bold]Email:[/bold] {user_data.get('email', 'N/A')}")
    console.print(f"[bold]Name:[/bold] {user_data.get('name', 'N/A')}")
    if user_data.get("created_at"):
        console.print(f"[bold]Created:[/bold] {user_data['created_at']}")
    activated_at = user_data.get("activated_at")
    if activated_at:
        console.print(f"[bold]Activated:[/bold] {activated_at}")
    else:
        console.print("[bold]Status:[/bold] [yellow]inactive[/yellow]")


@user_app.command("list")
def user_list(
    q: str = typer.Option("", "--q", help="Substring filter over name/email"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    List Campus users (searchable).

    Reads run through campus.api's directory facade (#1226): staff
    see the full base via the staff:viewer baseline — no grant row —
    while other authenticated callers see the members of circles they
    can read, plus their own record.
    """
    if dry_run:
        print_python_api(
            "campus user list",
            [
                "page = campus.api.users.list()",
                "for user in page['users']:",
                "    print(user['id'], user['name'])",
            ],
        )
        return

    try:
        api = get_api_client()
        # The facade pages server-side (default 50, cap 200): walk the
        # cursor to preserve list-everything semantics.
        users = []
        cursor = None
        for _page in range(100):
            page = api.api_users.list(q=q or None, limit=200, cursor=cursor)
            users.extend(page["users"])
            cursor = page.get("next_cursor")
            if not cursor:
                break

        if output_json:
            print_json([_format_user(u) for u in users])
        else:
            if not users:
                console.print("[dim]No users found.[/dim]")
                return

            console.print(f"[bold]Found {len(users)} user(s):[/bold]\n")
            for user in users:
                formatted = _format_user(user)
                console.print(f"[cyan]{formatted['id']}[/cyan]")
                console.print(f"  Name: {formatted['name']}")
                status = (
                    "active"
                    if formatted["activated_at"]
                    else "[yellow]inactive[/yellow]"
                )
                console.print(f"  Status: {status}")
                console.print()

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to list users: {e}")
        raise typer.Exit(1) from e


@user_app.command("new")
def user_new(
    email: str = typer.Option(
        ..., "--email", "-e", help="User email (also the user ID)"
    ),
    name: str = typer.Option(..., "--name", "-n", help="User display name"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    Create a new Campus user.

    Requires users:write authority: a users:write grant row AND
    the users:write scope on your token (see `campus grant list`;
    the super-admin root needs neither). The user starts inactive;
    activate them with 'campus user activate'.
    """
    if dry_run:
        print_python_api(
            "campus user new",
            [
                "user = campus.auth.users.new(",
                f"    email={email!r},",
                f"    name={name!r},",
                ")",
                "print(user.id)",
            ],
        )
        return

    try:
        api = get_api_client()
        user = api.auth_users.new(email=email, name=name)

        result = _format_user(user)

        if output_json:
            print_json(result)
        else:
            print_success(f"User '{email}' created successfully!")
            _print_user_details(result)
            console.print(
                "\n[dim]New users start inactive: activate with"
                " 'campus user activate'.[/dim]"
            )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to create user: {e}")
        raise typer.Exit(1) from e


@user_app.command("get")
def user_get(
    user_id: str = typer.Option(..., "--user-id", "-u", help="User ID (email)"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    Get details of a Campus user.

    Reads run through campus.api's directory facade (#1226): every
    authenticated user sees their own record; staff see any record.
    An invisible record is indistinguishable from an absent one (404).
    """
    if dry_run:
        print_python_api(
            "campus user get",
            [
                f"user = campus.api.users.get({user_id!r})",
                "print(user['name'], user['activated_at'])",
            ],
        )
        return

    try:
        api = get_api_client()
        user = api.api_users.get(user_id)

        result = _format_user(user)

        if output_json:
            print_json(result)
        else:
            _print_user_details(result)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to get user: {e}")
        raise typer.Exit(1) from e


@user_app.command("activate")
def user_activate(
    user_id: str = typer.Option(..., "--user-id", "-u", help="User ID (email)"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    Activate a Campus user.

    Requires users:mod authority or higher: a users:mod grant row
    AND the matching scope on your token (see `campus grant list`;
    the super-admin root needs neither).
    """
    if dry_run:
        print_python_api(
            "campus user activate",
            [
                f"user = campus.auth.users[{user_id!r}].activate()",
                "print(user.activated_at)",
            ],
        )
        return

    try:
        api = get_api_client()
        user = api.auth_users[user_id].activate()

        result = _format_user(user)

        if output_json:
            print_json(result)
        else:
            print_success(f"User '{user_id}' activated successfully!")
            _print_user_details(result)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to activate user: {e}")
        raise typer.Exit(1) from e


@user_app.command("edit")
def user_edit(
    user_id: str = typer.Option(..., "--user-id", "-u", help="User ID (email)"),
    name: str = typer.Option(..., "--name", "-n", help="New display name"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    Rename a Campus user.

    Requires users:write authority: a users:write grant row AND
    the users:write scope on your token (see `campus grant list`;
    the super-admin root needs neither). Name is the only editable
    field: a user's ID IS its email, so identity fields stay fixed.
    """
    if dry_run:
        print_python_api(
            "campus user edit",
            [
                f"user = campus.auth.users[{user_id!r}].update(",
                f"    name={name!r},",
                ")",
                "print(user.name)",
            ],
        )
        return

    try:
        api = get_api_client()
        user = api.auth_users[user_id].update(name=name)

        result = _format_user(user)

        if output_json:
            print_json(result)
        else:
            print_success(f"User '{user_id}' updated successfully!")
            _print_user_details(result)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to update user: {e}")
        raise typer.Exit(1) from e


@user_app.command("delete")
def user_delete(
    user_id: str = typer.Option(..., "--user-id", "-u", help="User ID (email)"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation"),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    Delete a Campus user.

    Permanently deletes the user record. Requires users:admin
    authority: a users:admin grant row AND the users:admin scope on
    your token (see `campus grant list`; the super-admin root needs
    neither).
    """
    if dry_run:
        print_python_api(
            "campus user delete",
            [f"campus.auth.users[{user_id!r}].delete()"],
        )
        return

    confirm_destructive(f"delete user '{user_id}'", confirm)

    try:
        api = get_api_client()
        api.auth_users[user_id].delete()
        print_success(f"User '{user_id}' deleted successfully.")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to delete user: {e}")
        raise typer.Exit(1) from e
