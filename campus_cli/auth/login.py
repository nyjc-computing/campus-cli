"""Authentication commands - login and logout using Device Authorization Flow."""

import time
import webbrowser
from typing import Optional

import requests
import typer
from rich.console import Console

from campus_cli.config import config
from campus_cli.credentials import CredentialError, credentials
from campus_cli.utils.output import print_error, print_success

login_app = typer.Typer(help="Authentication commands")
console = Console()

# OAuth client ID for CLI (public client, no secret required)
CLI_CLIENT_ID = "campus-cli"
DEVICE_CODE_ENDPOINT = "/oauth/device_authorize"
TOKEN_ENDPOINT = "/oauth/token"


class DeviceAuthError(Exception):
    """Exception raised for device authentication errors."""

    pass


def request_device_code() -> dict:
    """
    Request a device code from the authorization server.

    Returns:
        Dict containing device_code, user_code, verification_uri, expires_in, interval.

    Raises:
        DeviceAuthError: If the request fails.
    """
    url = f"{config.api_endpoint}{DEVICE_CODE_ENDPOINT}"

    try:
        response = requests.post(
            url,
            data={
                "client_id": CLI_CLIENT_ID,
            },
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise DeviceAuthError(f"Failed to request device code: {e}") from e


def poll_for_token(device_code: str, interval: int, max_attempts: int = 60) -> dict:
    """
    Poll the token endpoint until the user completes authentication.

    Args:
        device_code: The device code from the initial request.
        interval: Seconds to wait between poll attempts.
        max_attempts: Maximum number of polling attempts.

    Returns:
        Dict containing access_token, refresh_token, expires_in, token_type.

    Raises:
        DeviceAuthError: If polling times out or the request fails.
    """
    url = f"{config.api_endpoint}{TOKEN_ENDPOINT}"

    for attempt in range(max_attempts):
        try:
            response = requests.post(
                url,
                data={
                    "client_id": CLI_CLIENT_ID,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": device_code,
                },
                headers={"Accept": "application/json"},
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 400:
                # Check for authorization pending or slow down
                error = response.json().get("error", "")
                if error == "authorization_pending":
                    # User hasn't completed auth yet, continue polling
                    console.print(".", end="", flush=True)
                    time.sleep(interval)
                    continue
                elif error == "slow_down":
                    # Server is asking us to poll less frequently
                    time.sleep(interval + 5)
                    continue
                elif error == "expired_token":
                    raise DeviceAuthError("Device code has expired. Please try logging in again.")
                elif error == "access_denied":
                    raise DeviceAuthError("Access was denied by the user.")
            else:
                response.raise_for_status()

        except requests.RequestException as e:
            # Don't fail on network errors during polling, just retry
            if attempt < max_attempts - 1:
                time.sleep(interval)
                continue
            raise DeviceAuthError(f"Failed to poll for token: {e}") from e

    raise DeviceAuthError("Authentication timed out. Please try again.")


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
    Authenticate with Campus API using Device Authorization Flow.

    This will:
    1. Request a device code from the server
    2. Display a code for you to enter at the verification URL
    3. Poll for the token while you complete authentication in a browser
    4. Store the received token in your credential manager
    """
    # Check if already logged in
    existing_token = credentials.get_token()
    if existing_token:
        console.print("[yellow]Already authenticated.[/yellow]")
        if output_token:
            console.print(existing_token)
        return

    try:
        # Step 1: Request device code
        console.print("[bold]Requesting device code...[/bold]")
        device_auth_data = request_device_code()

        user_code = device_auth_data["user_code"]
        verification_uri = device_auth_data["verification_uri"]
        device_code = device_auth_data["device_code"]
        interval = device_auth_data.get("interval", 5)
        expires_in = device_auth_data.get("expires_in", 300)

        # Step 2: Display instructions to user
        console.print("\n[bold cyan]To authenticate, use a web browser to open:[/bold cyan]")
        console.print(f"[link]{verification_uri}[/link]\n")
        console.print(f"[bold]Enter the following code:[/bold] [bold yellow]{user_code}[/bold yellow]\n")

        # Open browser automatically
        console.print("Opening browser to verification page...")
        webbrowser.open(verification_uri)

        # Step 3: Poll for token
        console.print("\nWaiting for authentication to complete...")
        console.print("[dim](Polling for token...)[/dim]")

        token_data = poll_for_token(
            device_code=device_code,
            interval=interval,
            max_attempts=int(expires_in / interval),
        )

        console.print("\n")  # New line after polling dots

        # Step 4: Store tokens
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")

        if access_token:
            credentials.set_token(access_token)
            if refresh_token:
                credentials.set_refresh_token(refresh_token)

            print_success("Authentication successful!")
            if output_token:
                console.print(access_token)
        else:
            print_error("Authentication completed but no token received.")
            raise typer.Exit(1)

    except DeviceAuthError as e:
        console.print("\n")  # New line after polling dots
        print_error(str(e))
        raise typer.Exit(1) from e
    except Exception as e:
        console.print("\n")  # New line after polling dots
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
