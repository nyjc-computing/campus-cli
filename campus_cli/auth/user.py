"""User management commands (#42).

Every command requires the matching users:* management scope on the
token (login with `campus auth login --scope users:...`) AND the
account to be listed in the deployment's AUTH_USERS_ADMIN_USER_IDS
(campus invariant A8, per-vocabulary designation):

- list/get: users:read
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
    """Format a user model for output.

    Args:
        user: The campus.model.User instance

    Returns:
        Dict representation of the user
    """
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
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    List all Campus users.

    Requires the users:read scope (login with
    `campus auth login --scope users:read`).
    """
    if dry_run:
        print_python_api(
            "campus user list",
            [
                "users = campus.auth.users.list()",
                "for user in users:",
                "    print(user.id, user.name)",
            ],
        )
        return

    try:
        api = get_api_client()
        users = api.auth_users.list()

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

    Requires the users:write scope (login with
    `campus auth login --scope users:write`). The user starts
    inactive; activate them with 'campus user activate'.
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

    Requires the users:read scope (login with
    `campus auth login --scope users:read`).
    """
    if dry_run:
        print_python_api(
            "campus user get",
            [
                f"user = campus.auth.users[{user_id!r}].get()",
                "print(user.name, user.activated_at)",
            ],
        )
        return

    try:
        api = get_api_client()
        user = api.auth_users[user_id].get()

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

    Requires the users:mod scope or higher (login with
    `campus auth login --scope users:mod`).
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

    Requires the users:write scope (login with
    `campus auth login --scope users:write`). Name is the only
    editable field: a user's ID IS its email, so identity fields
    stay fixed.
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

    Permanently deletes the user record. Requires the users:admin
    scope (login with `campus auth login --scope users:admin`).
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
