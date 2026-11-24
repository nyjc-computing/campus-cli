"""User directory commands — the campus.api facade (#1226).

Read-only: list/search the user base and fetch single records through
campus.api's /users facade. Staff read the full base via the
staff:viewer baseline — no grant row needed — and other authenticated
callers get their circle-visible slice plus their own record.

User MUTATION (create/activate/rename/delete) lives in
`campus auth user`: it is campus.auth management work, walled behind
the #883 grant store authority model (a matching grant row AND the
matching users:* scope on the token — either leg alone confers
nothing, campus invariant A8; the env-nominated super-admin root
needs neither). Inspect and administer rows with `campus grant`.
"""

import typer
from rich.console import Console

from campus_cli.auth.common import (
    dry_run_option,
    get_api_client,
)
from campus_cli.utils.output import (
    print_error,
    print_json,
    print_python_api,
)

user_app = typer.Typer(help="User directory commands (campus.api facade)")
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


