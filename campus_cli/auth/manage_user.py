"""User management commands through campus.auth (#42).

`campus auth user` is the management surface: create, activate,
rename, delete — and list/get for designated admins. Every command
runs against campus.auth's walled /users management routes under the
campus#883 grant store authority model: a matching grant row AND the
matching users:* scope on the token — either leg alone confers
nothing (campus invariant A8). The env-nominated super-admin root
needs neither. Inspect and administer rows with `campus grant`.

- list/get: users:read
- activate: users:mod (implies read)
- new/edit: users:write (implies mod and read)
- delete:   users:admin (implies write)

Directory READS for ordinary staff live in `campus user` (the
campus.api facade, #1226); this group is the admin path to the same
records through their grant authority.
"""

import typer
from rich.console import Console

from campus_cli.auth.common import (
    confirm_destructive,
    dry_run_option,
    get_api_client,
)
from campus_cli.auth.user import _format_user, _print_user_details
from campus_cli.utils.output import (
    print_error,
    print_json,
    print_python_api,
    print_success,
)

manage_user_app = typer.Typer(help="Manage users through campus.auth")
console = Console()


@manage_user_app.command("list")
def user_list(
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    List all Campus users (campus.auth management surface).

    Requires users:read authority: a users:read grant row AND the
    users:read scope on your token (see `campus grant list`; the
    super-admin root needs neither). Directory reads for ordinary
    staff are `campus user list` (the campus.api facade).
    """
    if dry_run:
        print_python_api(
            "campus auth user list",
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


@manage_user_app.command("get")
def user_get(
    user_id: str = typer.Option(..., "--user-id", "-u", help="User ID (email)"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    Get details of a Campus user (campus.auth management surface).

    Requires users:read authority: a users:read grant row AND the
    users:read scope on your token (see `campus grant list`; the
    super-admin root needs neither). Directory reads for ordinary
    staff are `campus user get` (the campus.api facade).
    """
    if dry_run:
        print_python_api(
            "campus auth user get",
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


@manage_user_app.command("new")
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
    activate them with 'campus auth user activate'.
    """
    if dry_run:
        print_python_api(
            "campus auth user new",
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
                " 'campus auth user activate'.[/dim]"
            )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to create user: {e}")
        raise typer.Exit(1) from e


@manage_user_app.command("activate")
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
            "campus auth user activate",
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


@manage_user_app.command("edit")
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
            "campus auth user edit",
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


@manage_user_app.command("delete")
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
            "campus auth user delete",
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
