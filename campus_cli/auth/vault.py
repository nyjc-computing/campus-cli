"""Vault management commands."""

import typer
from rich.console import Console

from campus_cli.auth.common import get_api_client
from campus_cli.utils.output import print_error, print_json, print_success, print_table

vault_app = typer.Typer(help="Vault management commands")
console = Console()


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
        api = get_api_client()
        keys = api.auth_vaults[vault].keys()

        if output_json:
            print_json({"vault": vault, "keys": keys, "count": len(keys)})
        else:
            console.print(f"[bold]Vault:[/bold] {vault}")
            console.print(f"[bold]Keys:[/bold] {len(keys)} key(s)\n")
            if keys:
                print_table(headers=["Key"], rows=[[key] for key in keys])
            else:
                console.print("[dim]No keys found in this vault.[/dim]")

    except typer.Exit:
        raise
    except KeyError:
        print_error(f"Vault '{vault}' not found.")
        raise typer.Exit(1) from None
    except Exception as e:
        print_error(f"Failed to list vault: {e}")
        raise typer.Exit(1) from e


@vault_app.command("get")
def vault_get(
    vault: str = typer.Option(..., "--vault", "-v", help="Vault label"),
    key: str | None = typer.Option(None, "--key", "-k", help="Specific key to retrieve"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """
    Get vault contents.

    Retrieves the entire vault or a specific key-value pair.
    If --key is not specified, returns all entries in the vault.
    """
    try:
        api = get_api_client()

        if key:
            try:
                value = api.auth_vaults[vault][key]
                if output_json:
                    print_json({"vault": vault, "key": key, "value": value})
                else:
                    console.print(f"[bold]Vault:[/bold] {vault}")
                    console.print(f"[bold]Key:[/bold] {key}")
                    console.print(f"[bold]Value:[/bold] {value}")
            except KeyError:
                print_error(f"Key '{key}' not found in vault '{vault}'.")
                raise typer.Exit(1) from None
        else:
            keys = api.auth_vaults[vault].keys()
            entries = {}
            for k in keys:
                try:
                    entries[k] = api.auth_vaults[vault][k]
                except KeyError:
                    pass

            if output_json:
                print_json({"vault": vault, "entries": entries, "count": len(entries)})
            else:
                console.print(f"[bold]Vault:[/bold] {vault}")
                console.print(f"[bold]Entries:[/bold] {len(entries)} key(s)\n")
                if entries:
                    for k, v in entries.items():
                        console.print(f"  [cyan]{k}:[/cyan] {v}")
                else:
                    console.print("[dim]No entries found in this vault.[/dim]")

    except typer.Exit:
        raise
    except KeyError:
        print_error(f"Vault '{vault}' not found.")
        raise typer.Exit(1) from None
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
        api = get_api_client()
        api.auth_vaults[vault][key] = value

        if output_json:
            print_json({"vault": vault, "key": key, "value": value})
        else:
            print_success(f"Set '{key}' in vault '{vault}'.")

    except typer.Exit:
        raise
    except KeyError:
        print_error(f"Vault '{vault}' not found.")
        raise typer.Exit(1) from None
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
        api = get_api_client()
        del api.auth_vaults[vault][key]
        print_success(f"Deleted '{key}' from vault '{vault}'.")

    except typer.Exit:
        raise
    except KeyError:
        print_error(f"Key '{key}' not found in vault '{vault}'.")
        raise typer.Exit(1) from None
    except Exception as e:
        print_error(f"Failed to delete vault entry: {e}")
        raise typer.Exit(1) from e
