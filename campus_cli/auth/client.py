"""OAuth client management commands."""

import typer
from rich.console import Console

from campus_cli.auth.common import get_api_client
from campus_cli.utils.output import print_error, print_json, print_success

client_app = typer.Typer(help="OAuth client management commands")
console = Console()


def _format_client(client, include_secret: bool = False) -> dict:
    """Format a client model for output.

    Args:
        client: The campus.model.Client instance
        include_secret: Whether to include the secret (only shown on creation)

    Returns:
        Dict representation of the client
    """
    result = {
        "id": client.id,
        "name": client.name,
        "description": client.description,
        "created_at": client.created_at.isoformat() if client.created_at else None,
        "permissions": client.permissions,
    }
    if include_secret and hasattr(client, "secret") and client.secret:
        result["client_secret"] = client.secret
    return result


def _print_client_details(client_data: dict) -> None:
    """Print client details in a formatted way.

    Args:
        client_data: Dict with client information
    """
    console.print(f"[bold]Client ID:[/bold] {client_data.get('id', 'N/A')}")
    console.print(f"[bold]Name:[/bold] {client_data.get('name', 'N/A')}")
    console.print(f"[bold]Description:[/bold] {client_data.get('description', 'N/A')}")

    if client_data.get("created_at"):
        console.print(f"[bold]Created:[/bold] {client_data['created_at']}")

    if "client_secret" in client_data:
        console.print(f"[bold]Client Secret:[/bold] [bold yellow]{client_data['client_secret']}[/bold yellow]")
        console.print("\n[yellow]Note: Store the client secret securely. It won't be shown again.[/yellow]")

    if client_data.get("permissions"):
        console.print(f"[bold]Permissions:[/bold]")
        for vault, access in client_data["permissions"].items():
            console.print(f"  - {vault}: {access}")


@client_app.command("list")
def client_list(
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """
    List all OAuth clients.

    Displays all OAuth clients with their IDs, names, and descriptions.
    """
    try:
        api = get_api_client()
        clients = api.auth_clients.list()

        if output_json:
            print_json([_format_client(c) for c in clients])
        else:
            if not clients:
                console.print("[dim]No clients found.[/dim]")
                return

            console.print(f"[bold]Found {len(clients)} client(s):[/bold]\n")
            for client in clients:
                console.print(f"[cyan]{client.id}[/cyan]")
                console.print(f"  Name: {client.name}")
                console.print(f"  Description: {client.description}")
                if client.permissions:
                    vaults = ", ".join(client.permissions.keys())
                    console.print(f"  Vaults: {vaults}")
                console.print()

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to list clients: {e}")
        raise typer.Exit(1) from e


@client_app.command("new")
def client_new(
    name: str = typer.Option(..., "--name", "-n", help="Client name"),
    description: str = typer.Option(..., "--description", "-d", help="Client description"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """
    Create a new OAuth client.

    Creates a new OAuth client with the specified name and description.
    The client secret will only be shown once after creation.
    """
    try:
        api = get_api_client()
        client = api.auth_clients.new(name=name, description=description)

        result = _format_client(client, include_secret=True)

        if output_json:
            print_json(result)
        else:
            print_success(f"Client '{name}' created successfully!")
            _print_client_details(result)

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
        api = get_api_client()
        client = api.auth_clients[client_id].get()

        result = _format_client(client)

        if output_json:
            print_json(result)
        else:
            _print_client_details(result)

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
        api = get_api_client()
        client = api.auth_clients[client_id].update(name=name, description=description)

        result = _format_client(client)

        if output_json:
            print_json(result)
        else:
            print_success(f"Client '{client_id}' updated successfully!")
            _print_client_details(result)

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
        api = get_api_client()
        api.auth_clients[client_id].delete()
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
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """
    Revoke an OAuth client's secret.

    Revokes the client secret and generates a new one. The new secret
    will only be shown once.
    """
    if not confirm:
        typer.confirm(
            f"Are you sure you want to revoke the secret for client '{client_id}'?", abort=True
        )

    try:
        api = get_api_client()
        # The revoke() method returns the new secret
        new_secret = api.auth_clients[client_id].revoke()

        if output_json:
            print_json({"client_id": client_id, "new_secret": new_secret})
        else:
            print_success(f"Client secret revoked for '{client_id}'.")
            console.print(f"[bold]New Client Secret:[/bold] [bold yellow]{new_secret}[/bold yellow]")
            console.print("\n[yellow]Note: Store the new client secret securely. It won't be shown again.[/yellow]")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to revoke client: {e}")
        raise typer.Exit(1) from e


# Client access sub-commands
access_app = typer.Typer(help="OAuth client access management commands")
client_app.add_typer(access_app, name="access")


@access_app.command("get")
def client_access_get(
    client_id: str = typer.Option(..., "--client-id", "-i", help="Client ID"),
    vault: str | None = typer.Option(None, "--vault", "-v", help="Vault label (if not specified, shows all)"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """
    Get client vault access permissions.

    Displays the access permissions for a client.
    If --vault is specified, shows only that vault's permissions.
    Otherwise, shows all vault permissions.
    """
    try:
        api = get_api_client()
        access = api.auth_clients[client_id].access.get(vault=vault)

        if output_json:
            print_json(access)
        else:
            if vault:
                console.print(f"[bold]Client:[/bold] {client_id}")
                console.print(f"[bold]Vault:[/bold] {vault}")
                console.print(f"[bold]Access:[/bold] {access.get('access', 'N/A')}")
            else:
                console.print(f"[bold]Client:[/bold] {client_id}")
                console.print(f"[bold]Vault Access:[/bold]")
                if not access.get("access"):
                    console.print("[dim]No vault access configured.[/dim]")
                else:
                    for vault_label, access_level in access["access"].items():
                        console.print(f"  {vault_label}: {access_level}")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to get client access: {e}")
        raise typer.Exit(1) from e


@access_app.command("grant")
def client_access_grant(
    client_id: str = typer.Option(..., "--client-id", "-i", help="Client ID"),
    vault: str = typer.Option(..., "--vault", "-v", help="Vault label"),
    permission: int = typer.Option(..., "--permission", "-p", help="Permission bitflag (1=READ, 2=CREATE, 4=UPDATE, 8=DELETE)"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """
    Grant vault access to a client.

    Grants the specified permission level for a vault to the client.
    Permissions are bitflags: 1=READ, 2=CREATE, 4=UPDATE, 8=DELETE.
    Combine with bitwise OR: e.g., 3 for READ+CREATE.
    """
    try:
        api = get_api_client()
        result = api.auth_clients[client_id].access.grant(vault=vault, permission=permission)

        if output_json:
            print_json(result)
        else:
            print_success(f"Granted access to vault '{vault}' for client '{client_id}'.")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to grant client access: {e}")
        raise typer.Exit(1) from e


@access_app.command("revoke")
def client_access_revoke(
    client_id: str = typer.Option(..., "--client-id", "-i", help="Client ID"),
    vault: str = typer.Option(..., "--vault", "-v", help="Vault label"),
    permission: int = typer.Option(..., "--permission", "-p", help="Permission bitflag to revoke"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """
    Revoke vault access from a client.

    Revokes the specified permission level for a vault from the client.
    Permissions are bitflags: 1=READ, 2=CREATE, 4=UPDATE, 8=DELETE.
    """
    try:
        api = get_api_client()
        result = api.auth_clients[client_id].access.revoke(vault=vault, permission=permission)

        if output_json:
            print_json(result)
        else:
            print_success(f"Revoked access to vault '{vault}' for client '{client_id}'.")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to revoke client access: {e}")
        raise typer.Exit(1) from e


@access_app.command("update")
def client_access_update(
    client_id: str = typer.Option(..., "--client-id", "-i", help="Client ID"),
    vault: str = typer.Option(..., "--vault", "-v", help="Vault label"),
    permission: int = typer.Option(..., "--permission", "-p", help="Permission bitflag to set"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """
    Update (replace) vault access for a client.

    Sets the permission level for a vault to the exact value specified.
    Use 0 to remove all access to the vault.
    Permissions are bitflags: 1=READ, 2=CREATE, 4=UPDATE, 8=DELETE.
    """
    try:
        api = get_api_client()
        result = api.auth_clients[client_id].access.update(vault=vault, permission=permission)

        if output_json:
            print_json(result)
        else:
            if permission == 0:
                print_success(f"Removed all access to vault '{vault}' for client '{client_id}'.")
            else:
                print_success(f"Updated access to vault '{vault}' for client '{client_id}'.")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to update client access: {e}")
        raise typer.Exit(1) from e
