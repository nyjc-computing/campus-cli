"""Vault management commands."""

from typing import Optional

import typer
from rich.console import Console

from campus_cli.credentials import credentials
from campus_cli.utils.output import print_error, print_json, print_success, print_table

vault_app = typer.Typer(help="Vault management commands")
console = Console()


def get_api_client():
    """
    Get an authenticated API client.

    Returns:
        An authenticated campus API client.

    Raises:
        typer.Exit: If authentication fails.
    """
    token = credentials.get_token()
    if not token:
        print_error("Not authenticated. Run 'campus auth login' first.")
        raise typer.Exit(1)

    try:
        from campus_api import CampusClient

        return CampusClient(token=token)
    except ImportError:
        print_error("campus-api-python library not available.")
        raise typer.Exit(1) from None


@vault_app.command("list")
def vault_list(
    vault: str = typer.Option(..., "--vault", "-v", help="Vault label"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """
    List all entries in a vault.

    Displays all keys stored in the specified vault.
    """
    try:
        api_client = get_api_client()

        # TODO: Implement actual API call
        result = {
            "vault": vault,
            "keys": ["key1", "key2", "key3"],
            "count": 3,
        }

        if output_json:
            print_json(result)
        else:
            console.print(f"[bold]Vault:[/bold] {vault}")
            print_table(
                headers=["Key"],
                rows=[[key] for key in result["keys"]],
            )

    except Exception as e:
        print_error(f"Failed to list vault: {e}")
        raise typer.Exit(1) from e


@vault_app.command("get")
def vault_get(
    vault: str = typer.Option(..., "--vault", "-v", help="Vault label"),
    key: Optional[str] = typer.Option(None, "--key", "-k", help="Specific key to retrieve"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """
    Get vault contents.

    Retrieves the entire vault or a specific key-value pair.
    If --key is not specified, returns all entries in the vault.
    """
    try:
        api_client = get_api_client()

        # TODO: Implement actual API call
        if key:
            result = {
                "vault": vault,
                "key": key,
                "value": f"value-for-{key}",
            }
        else:
            result = {
                "vault": vault,
                "entries": {
                    "key1": "value1",
                    "key2": "value2",
                    "key3": "value3",
                },
            }

        if output_json:
            print_json(result)
        else:
            if key:
                console.print(f"[bold]Vault:[/bold] {vault}")
                console.print(f"[bold]Key:[/bold] {key}")
                console.print(f"[bold]Value:[/bold] {result['value']}")
            else:
                console.print(f"[bold]Vault:[/bold] {vault}")
                console.print("[bold]Entries:[/bold]")
                for k, v in result["entries"].items():
                    console.print(f"  {k}: {v}")

    except Exception as e:
        print_error(f"Failed to get vault: {e}")
        raise typer.Exit(1) from e


@vault_app.command("set")
def vault_set(
    vault: str = typer.Option(..., "--vault", "-v", help="Vault label"),
    key: str = typer.Option(..., "--key", "-k", help="Key to set"),
    value: str = typer.Option(..., "--value", help="Value to set"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """
    Set a key-value pair in a vault.

    Stores or updates the specified key with the given value in the vault.
    """
    try:
        api_client = get_api_client()

        # TODO: Implement actual API call
        result = {
            "vault": vault,
            "key": key,
            "value": value,
        }

        if output_json:
            print_json(result)
        else:
            print_success(f"Set '{key}' in vault '{vault}'.")

    except Exception as e:
        print_error(f"Failed to set vault entry: {e}")
        raise typer.Exit(1) from e


@vault_app.command("delete")
def vault_delete(
    vault: str = typer.Option(..., "--vault", "-v", help="Vault label"),
    key: str = typer.Option(..., "--key", "-k", help="Key to delete"),
    confirm: bool = typer.Option(True, "--confirm", "-y", help="Skip confirmation"),
) -> None:
    """
    Delete a key from a vault.

    Removes the specified key from the vault.
    """
    if not confirm:
        typer.confirm(f"Are you sure you want to delete key '{key}' from vault '{vault}'?", abort=True)

    try:
        api_client = get_api_client()

        # TODO: Implement actual API call
        print_success(f"Deleted '{key}' from vault '{vault}'.")

    except Exception as e:
        print_error(f"Failed to delete vault entry: {e}")
        raise typer.Exit(1) from e
