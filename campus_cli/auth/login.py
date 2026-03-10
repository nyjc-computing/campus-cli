"""Authentication commands - login and logout using Device Authorization Flow."""

import time
import webbrowser

import typer
from rich.console import Console

from campus_cli.auth.common import RefreshError, get_token_status, refresh_access_token
from campus_cli.config import config
from campus_cli.credentials import CredentialError, credentials
from campus_cli.utils.output import print_error, print_success

login_app = typer.Typer(help="Authentication commands")
console = Console()

# OAuth client ID for CLI (public client, no secret required)
CLI_CLIENT_ID = "campus-cli"


class DeviceAuthError(Exception):
    """Exception raised for device authentication errors."""

    pass


def request_device_code(campus_auth) -> dict:
    """
    Request a device code from the authorization server.

    Args:
        campus_auth: Campus auth client from campus-api-python

    Returns:
        Dict containing device_code, user_code, verification_uri, expires_in, interval.

    Raises:
        DeviceAuthError: If the request fails.
    """
    try:
        return campus_auth.oauth.request_device_code(client_id=CLI_CLIENT_ID)
    except Exception as e:
        raise DeviceAuthError(f"Failed to request device code: {e}") from e


def poll_for_token(campus_auth, device_code: str, interval: int, max_attempts: int = 60):
    """
    Poll the token endpoint until the user completes authentication.

    Args:
        campus_auth: Campus auth client from campus-api-python
        device_code: The device code from the initial request.
        interval: Seconds to wait between poll attempts.
        max_attempts: Maximum number of polling attempts.

    Returns:
        OAuthToken instance containing access_token, refresh_token, expiry information.

    Raises:
        DeviceAuthError: If polling times out or the request fails.
    """
    for attempt in range(max_attempts):
        try:
            response = campus_auth.oauth.poll_for_token(
                client_id=CLI_CLIENT_ID,
                device_code=device_code
            )
            return response
        except Exception as e:
            error_str = str(e)
            # Check for authorization pending or slow down
            if "authorization_pending" in error_str.lower():
                # User hasn't completed auth yet, continue polling
                console.print(".", end="", flush=True)
                time.sleep(interval)
                continue
            elif "slow_down" in error_str.lower():
                # Server is asking us to poll less frequently
                time.sleep(interval + 5)
                continue
            elif "expired_token" in error_str.lower() or "expired" in error_str.lower():
                raise DeviceAuthError("Device code has expired. Please try logging in again.")
            elif "access_denied" in error_str.lower():
                raise DeviceAuthError("Access was denied by the user.")
            # Don't fail on network errors during polling, just retry
            elif attempt < max_attempts - 1:
                time.sleep(interval)
                continue
            else:
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

    The auth endpoint is determined by the CAMPUS_ENV environment variable.
    """
    # Import campus-python client
    try:
        import campus_python
    except ImportError:
        print_error("campus-python library not found. Please install it first.")
        raise typer.Exit(1)

    # Check if already logged in
    existing_token = credentials.get_token()
    if existing_token and not credentials.is_token_expired():
        console.print("[yellow]Already authenticated.[/yellow]")
        if output_token:
            console.print(existing_token)
        return

    try:
        # Initialize campus client in device mode (no credentials required)
        campus = campus_python.Campus(timeout=60, mode="device")
        campus_auth = campus.auth

        # Step 1: Request device code
        console.print("[bold]Requesting device code...[/bold]")
        device_auth_data = request_device_code(campus_auth)

        user_code = device_auth_data["user_code"]
        verification_uri = device_auth_data["verification_uri"]
        device_code = device_auth_data["device_code"]
        interval = device_auth_data.get("interval", 5)
        expires_in = device_auth_data.get("expires_in", 300)

        # Step 2: Display instructions to user
        console.print("\n[bold cyan]To authenticate, use a web browser to open:[/bold cyan]")
        console.print(f"[link={verification_uri}]{verification_uri}[/link]\n")
        console.print(f"[bold]Enter the following code:[/bold] [bold yellow]{user_code}[/bold yellow]\n")

        # Open browser automatically
        console.print("Opening browser to verification page...")
        webbrowser.open(verification_uri)

        # Step 3: Poll for token
        console.print("\nWaiting for authentication to complete...")
        console.print("[dim](Polling for token...)[/dim]")

        token_response = poll_for_token(
            campus_auth,
            device_code=device_code,
            interval=interval,
            max_attempts=max(1, int(expires_in / interval)),
        )

        console.print("\n")  # New line after polling dots

        # Step 4: Store tokens
        # token_response is an OAuthToken instance with id, expiry_seconds, refresh_token
        access_token = token_response.id
        expires_in = token_response.expiry_seconds
        refresh_token = getattr(token_response, "refresh_token", None)

        if access_token:
            credentials.set_token(access_token, expires_in=expires_in)
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
    except (CredentialError, KeyError, ValueError, TypeError) as e:
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


@login_app.command("refresh")
def refresh_cmd(
    output_token: bool = typer.Option(
        False,
        "--output-token",
        "-t",
        help="Output the new access token to stdout",
    ),
    output_json: bool = typer.Option(
        False,
        "--json",
        help="Output status as JSON",
    ),
) -> None:
    """
    Refresh the access token using the stored refresh token.

    Manually refresh your access token. This is also done automatically
    when running commands (if auto_refresh is enabled).
    """
    if not credentials.get_token():
        print_error("Not authenticated. Run 'campus auth login' first.")
        raise typer.Exit(1)

    try:
        new_token = refresh_access_token()

        if output_json:
            import json
            from datetime import datetime, timezone

            expires_at = credentials.get_token_expires_at()
            console.print(json.dumps({
                "success": True,
                "access_token": new_token,
                "expires_at": expires_at,
            }))
        else:
            print_success("Token refreshed successfully!")
            if output_token:
                console.print(new_token)

            expires_at = credentials.get_token_expires_at()
            if expires_at:
                from datetime import datetime, timezone

                try:
                    expiry_dt = datetime.fromisoformat(expires_at)
                    if expiry_dt.tzinfo is None:
                        expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
                    console.print(f"Expires at: {expiry_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                except ValueError:
                    console.print(f"Expires at: {expires_at}")

    except RefreshError as e:
        print_error(str(e))
        print_error("Please run 'campus auth login' to authenticate again.")
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

    Shows whether you are currently authenticated and token expiry information.
    """
    status = get_token_status()

    if output_json:
        import json
        console.print(json.dumps(status))
    else:
        if status["authenticated"]:
            print_success("Authenticated")
            console.print("You are logged in to Campus API.")

            if status["expires_at"]:
                from datetime import datetime, timezone

                try:
                    expiry_dt = datetime.fromisoformat(status["expires_at"])
                    if expiry_dt.tzinfo is None:
                        expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
                    now = datetime.now(timezone.utc)

                    if status["is_expired"]:
                        console.print("[red bold]Token has expired.[/red bold]")
                    else:
                        remaining = expiry_dt - now
                        minutes = int(remaining.total_seconds() // 60)
                        seconds = int(remaining.total_seconds() % 60)
                        console.print(f"Token expires in: [cyan]{minutes}m {seconds}s[/cyan]")

                    console.print(f"Expires at: {expiry_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                except ValueError:
                    console.print(f"Expires at: {status['expires_at']}")
            else:
                console.print("[dim](No expiry information available)[/dim]")

            if status["can_refresh"]:
                console.print("Auto-refresh: [green]enabled[/green]" if config.auto_refresh else "Auto-refresh: [yellow]disabled[/yellow]")
        else:
            console.print("[yellow]Not authenticated[/yellow]")
            console.print("Run [bold]campus auth login[/bold] to authenticate.")
