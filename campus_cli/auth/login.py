"""Authentication commands - login and logout."""

import webbrowser
from typing import Optional

import typer
from rich.console import Console

from campus_cli.config import config
from campus_cli.credentials import CredentialError, credentials
from campus_cli.utils.output import print_error, print_success

login_app = typer.Typer(help="Authentication commands")
console = Console()


@login_app.command("login")
def login_cmd(
    output_token: bool = typer.Option(
        False,
        "--output-token",
        "-t",
        help="Output the access token to stdout",
    ),
) -> None:
    """
    Authenticate with Campus API using OAuth flow.

    Opens a browser window for authentication and stores the received token.
    """
    # Check if already logged in
    existing_token = credentials.get_token()
    if existing_token:
        console.print("[yellow]Already authenticated.[/yellow]")
        if output_token:
            console.print(existing_token)
        return

    # Import campus API client to generate auth URL
    try:
        # TODO: Integrate with campus-api-python for OAuth flow
        # For now, we'll create a placeholder implementation
        auth_url = f"{config.api_endpoint}/oauth/authorize"

        console.print("[bold]Opening browser for authentication...[/bold]")
        console.print(f"If browser doesn't open, visit:\n[link]{auth_url}[/link]")

        # Open browser
        webbrowser.open(auth_url)

        console.print("\n[yellow]OAuth flow not yet fully implemented.[/yellow]")
        console.print("Please paste your access token below:")

        # For now, prompt for token manually
        # In production, this would be a proper OAuth callback handler
        token = typer.prompt("Access token", hide_input=True)

        if token:
            credentials.set_token(token)
            print_success("Authentication successful!")
            if output_token:
                console.print(token)
        else:
            print_error("No token provided. Authentication failed.")

    except Exception as e:
        print_error(f"Authentication failed: {e}")
        raise typer.Exit(1) from e


@login_app.command("logout")
def logout_cmd(
    confirm: bool = typer.Option(
        True,
        "--confirm",
        "-y",
        help="Skip confirmation prompt",
    ),
) -> None:
    """
    Log out and clear stored credentials.

    Removes the stored access and refresh tokens from the credential store.
    """
    if not confirm:
        typer.confirm("Are you sure you want to log out?", abort=True)

    try:
        credentials.delete_token()
        try:
            credentials.delete_refresh_token()
        except CredentialError:
            pass  # Refresh token may not exist
        print_success("Logged out successfully.")
    except CredentialError as e:
        print_error(f"Failed to log out: {e}")
        raise typer.Exit(1) from e


@login_app.command("status")
def status_cmd(
    output_json: bool = typer.Option(
        False,
        "--json",
        help="Output status as JSON",
    ),
) -> None:
    """
    Check authentication status.

    Shows whether you are currently authenticated.
    """
    token = credentials.get_token()

    if token:
        if output_json:
            import json

            console.print(json.dumps({"authenticated": True}))
        else:
            print_success("Authenticated")
            console.print("You are logged in to Campus API.")
    else:
        if output_json:
            import json

            console.print(json.dumps({"authenticated": False}))
        else:
            console.print("[yellow]Not authenticated[/yellow]")
            console.print("Run [bold]campus auth login[/bold] to authenticate.")
