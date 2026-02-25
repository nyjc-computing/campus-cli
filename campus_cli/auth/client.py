"""OAuth client management commands."""

import typer
from rich.console import Console

from campus_cli.auth.common import get_api_client
from campus_cli.utils.output import print_error, print_json, print_success, print_table

client_app = typer.Typer(help="OAuth client management commands")
console = Console()


@client_app.command("new")
def client_new(
    name: str = typer.Option(..., "--name", "-n", help="Client name"),
    description: str = typer.Option(..., "--description", "-d", help="Client description"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """
    Create a new OAuth client.

    Creates a new OAuth client with the specified name and description.
    """
    try:
        client = get_api_client()

        # TODO: Implement actual API call when campus-api-python supports it
        # For now, return a placeholder response
        result = {
            "client_id": "placeholder-client-id",
            "client_secret": "placeholder-client-secret",
            "name": name,
            "description": description,
            "redirect_uris": [],
            "scopes": [],
        }

        if output_json:
            print_json(result)
        else:
            print_success(f"Client '{name}' created successfully!")
            console.print(f"Client ID: [bold]{result['client_id']}[/bold]")
            console.print(f"Client Secret: [bold]{result['client_secret']}[/bold]")
            console.print("\n[yellow]Note: Store the client secret securely.[/yellow]")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to create client: {e}")
        raise typer.Exit(1) from e


@client_app.command("get")
def client_get(
    client_id: str = typer.Option(..., "--client-id", "-i", help="Client ID"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """
    Get details of an OAuth client.

    Retrieves and displays information about the specified client.
    """
    try:
        client = get_api_client()

        # TODO: Implement actual API call
        result = {
            "client_id": client_id,
            "name": "Example Client",
            "description": "Example description",
            "redirect_uris": ["http://localhost:8080/callback"],
            "scopes": ["read", "write"],
            "created_at": "2024-01-01T00:00:00Z",
        }

        if output_json:
            print_json(result)
        else:
            console.print(f"[bold]Client ID:[/bold] {result['client_id']}")
            console.print(f"[bold]Name:[/bold] {result['name']}")
            console.print(f"[bold]Description:[/bold] {result['description']}")
            console.print(f"[bold]Redirect URIs:[/bold] {', '.join(result['redirect_uris'])}")
            console.print(f"[bold]Scopes:[/bold] {', '.join(result['scopes'])}")
            console.print(f"[bold]Created:[/bold] {result['created_at']}")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to get client: {e}")
        raise typer.Exit(1) from e


@client_app.command("update")
def client_update(
    client_id: str = typer.Option(..., "--client-id", "-i", help="Client ID"),
    name: str | None = typer.Option(None, "--name", "-n", help="New client name"),
    description: str | None = typer.Option(
        None, "--description", "-d", help="New client description"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """
    Update an OAuth client.

    Updates the name and/or description of an existing client.
    """
    if not name and not description:
        print_error("At least one of --name or --description must be provided.")
        raise typer.Exit(1)

    try:
        client = get_api_client()

        # TODO: Implement actual API call
        result = {
            "client_id": client_id,
            "name": name or "Updated Name",
            "description": description or "Updated description",
        }

        if output_json:
            print_json(result)
        else:
            print_success(f"Client '{client_id}' updated successfully!")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to update client: {e}")
        raise typer.Exit(1) from e


@client_app.command("delete")
def client_delete(
    client_id: str = typer.Option(..., "--client-id", "-i", help="Client ID"),
    confirm: bool = typer.Option(True, "--confirm", "-y", help="Skip confirmation"),
) -> None:
    """
    Delete an OAuth client.

    Permanently deletes the specified OAuth client.
    """
    if not confirm:
        typer.confirm(f"Are you sure you want to delete client '{client_id}'?", abort=True)

    try:
        client = get_api_client()

        # TODO: Implement actual API call
        print_success(f"Client '{client_id}' deleted successfully.")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to delete client: {e}")
        raise typer.Exit(1) from e


@client_app.command("revoke")
def client_revoke(
    client_id: str = typer.Option(..., "--client-id", "-i", help="Client ID"),
    confirm: bool = typer.Option(True, "--confirm", "-y", help="Skip confirmation"),
) -> None:
    """
    Revoke access for an OAuth client.

    Revokes all access tokens for the specified client.
    """
    if not confirm:
        typer.confirm(
            f"Are you sure you want to revoke access for client '{client_id}'?", abort=True
        )

    try:
        client = get_api_client()

        # TODO: Implement actual API call
        print_success(f"Access revoked for client '{client_id}'.")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to revoke client: {e}")
        raise typer.Exit(1) from e
