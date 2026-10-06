"""Authentication commands - login and logout using Device Authorization Flow."""

import contextlib
import time
import webbrowser

import requests
import typer
from rich.console import Console

from campus_cli import __version__
from campus_cli.auth.common import (
    RefreshError,
    confirm_destructive,
    endpoint_mismatch,
    ensure_endpoint_match,
    get_token_status,
    refresh_access_token,
    resolve_auth_url,
    revoke_token,
)
from campus_cli.config import PUBLIC_OAUTH_CLIENT_ID, config
from campus_cli.credentials import CredentialError, credentials
from campus_cli.utils.output import print_error, print_success

login_app = typer.Typer(help="Authentication commands")
console = Console()

# OAuth client ID for CLI (public client, no secret required)
# PUBLIC_OAUTH_CLIENT_ID is a public client (is_public=True) that is seeded
# in the auth server database. Public clients have no client_secret
# (RFC 6749 §2.1); access is granted via the user's device-flow credentials.
CLI_CLIENT_ID = PUBLIC_OAUTH_CLIENT_ID


class DeviceAuthError(Exception):
    """Exception raised for device authentication errors."""

    pass


def _agent_string() -> str:
    """Build the login-session agent string for this CLI install."""
    import platform
    return (
        f"campus-cli/{__version__} "
        f"({platform.system()} {platform.release()})"
    )


def create_login_session(auth_url: str, user_id: str) -> str | None:
    """Create the login-session record server-side (best-effort, #837).

    The device grant echoes the authorizing user; this call records the
    login against this install's stable device id (config-persisted) so
    audit spans attribute to the device, not just the user. Returns the
    session id, or None when the server predates the route or the call
    fails — attribution is observational and must never block login.
    """
    try:
        response = requests.post(
            f"{auth_url}/logins/",
            json={
                "client_id": CLI_CLIENT_ID,
                "user_id": user_id,
                "device_id": config.get_device_id(),
                "agent_string": _agent_string(),
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json().get("id")
    except (requests.RequestException, ValueError):
        console.print(
            "[dim]Note: device attribution unavailable "
            "(login session was not recorded).[/dim]"
        )
        return None


def delete_login_session(auth_url: str, session_id: str, token: str) -> bool:
    """Revoke the stored login-session record (best-effort, #837).

    The bearer-owned path (campus#838) accepts our access token: the
    session belongs to the same user the token was minted for. Returns
    True when the server confirmed the deletion.
    """
    try:
        response = requests.delete(
            f"{auth_url}/logins/{session_id}/",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        return response.status_code == 200
    except requests.RequestException:
        return False


def get_auth_urls() -> dict:
    """
    Get OAuth endpoint URLs.

    Uses CAMPUS_AUTH_URL env var, config file, ENV/CAMPUS_ENV, or default.

    Returns:
        Dict with device_code_url and token_url.
    """
    base_url = resolve_auth_url()

    return {
        "device_code_url": f"{base_url}/oauth/device_authorize",
        "token_url": f"{base_url}/oauth/token",
    }


def _response_error_detail(e: requests.RequestException) -> str:
    """Extract a human-readable message from a failed HTTP response.

    The auth server returns structured errors as
    {"error": {"code": ..., "message": ..., "details": ...}}; fall back to
    the exception text when there is no JSON body.
    """
    response = getattr(e, "response", None)
    if response is None:
        return str(e)
    try:
        error_obj = response.json().get("error", "")
    except ValueError:
        return str(e)
    if isinstance(error_obj, dict):
        return error_obj.get("message") or error_obj.get("code") or str(e)
    return error_obj or str(e)


def request_device_code() -> dict:
    """
    Request a device code from the authorization server.

    Returns:
        Dict containing device_code, user_code, verification_uri, expires_in, interval.

    Raises:
        DeviceAuthError: If the request fails.
    """
    urls = get_auth_urls()

    try:
        response = requests.post(
            urls["device_code_url"],
            data={"client_id": CLI_CLIENT_ID},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise DeviceAuthError(
            f"Failed to request device code: {_response_error_detail(e)}"
        ) from e


def poll_for_token(device_code: str, interval: int, max_attempts: int = 60) -> dict:
    """
    Poll the token endpoint until the user completes authentication.

    Args:
        device_code: The device code from the initial request.
        interval: Seconds to wait between poll attempts.
        max_attempts: Maximum number of polling attempts.

    Returns:
        Dict containing access_token, refresh_token, expires_in.

    Raises:
        DeviceAuthError: If polling times out or the request fails.
    """
    urls = get_auth_urls()
    # A missing or zero interval from the server would stall polling or
    # zero-divide on the max_attempts computation at the call site.
    poll_interval = max(1, int(interval))

    for attempt in range(max_attempts):
        try:
            response = requests.post(
                urls["token_url"],
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": device_code,
                    "client_id": CLI_CLIENT_ID,
                },
                timeout=30,
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 400:
                error_data = response.json()
                # Campus returns structured errors with oauth_error in details
                # {"error": {"code": "AUTH_...",
                #   "details": {"oauth_error": "authorization_pending"}}}
                error_obj = error_data.get("error", {})
                if isinstance(error_obj, dict):
                    error_message = error_obj.get("message", "")
                    oauth_error = error_obj.get("details", {}).get("oauth_error", "")
                else:
                    # Fallback for simple OAuth 2.0 format:
                    # {"error": "authorization_pending"}
                    oauth_error = error_obj
                    error_message = ""

                if oauth_error == "authorization_pending":
                    console.print(".", end="")
                    time.sleep(poll_interval)
                    continue
                elif oauth_error == "slow_down":
                    # RFC 8628 §3.5: the raised interval persists for the
                    # remainder of the flow, not just the next attempt.
                    poll_interval += 5
                    time.sleep(poll_interval)
                    continue
                elif oauth_error == "expired_token":
                    raise DeviceAuthError(
                        "Device code has expired. Please try logging in again."
                    )
                elif oauth_error == "access_denied":
                    raise DeviceAuthError("Access was denied by the user.")
                else:
                    msg = error_message or error_data.get(
                        "error_description", oauth_error
                    )
                    raise DeviceAuthError(f"Token error: {msg}")
            else:
                response.raise_for_status()

        except requests.RequestException as e:
            if attempt < max_attempts - 1:
                time.sleep(poll_interval)
                continue
            raise DeviceAuthError(f"Network error during token poll: {e}") from e

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

    The auth endpoint is resolved from the CAMPUS_AUTH_URL environment
    variable, the config file, or ENV/CAMPUS_ENV (see campus_cli.config).
    """
    # The endpoint this invocation targets; tokens minted below are bound to it.
    auth_url = resolve_auth_url()

    # Check if already logged in. An endpoint mismatch does not
    # short-circuit: login is the remediation for stale credentials,
    # so re-authentication proceeds against the current target.
    existing_token = credentials.get_token()
    if existing_token and not credentials.is_token_expired():
        mismatch = endpoint_mismatch()
        if mismatch is None:
            console.print("[yellow]Already authenticated.[/yellow]")
            console.print(f"[dim]Authenticated against: {auth_url}[/dim]")
            if output_token:
                console.print(existing_token)
            return
        stored, _ = mismatch
        console.print(
            f"[yellow]Stored credentials were issued by {stored}, but the "
            f"CLI is targeting {auth_url}. Re-authenticating.[/yellow]"
        )

    console.print(f"[dim]Authenticating against: {auth_url}[/dim]")

    try:
        # Step 1: Request device code
        console.print("[bold]Requesting device code...[/bold]")
        device_auth_data = request_device_code()

        user_code = device_auth_data["user_code"]
        verification_uri = device_auth_data["verification_uri"]
        device_code = device_auth_data["device_code"]
        # A zero/absent interval would zero-divide below; 5s is the
        # RFC 8628 default when the server omits it.
        interval = device_auth_data.get("interval") or 5
        expires_in = device_auth_data.get("expires_in", 300)

        # Step 2: Display instructions to user
        console.print(
            "\n[bold cyan]To authenticate, use a web browser to open:[/bold cyan]"
        )
        console.print(f"[link={verification_uri}]{verification_uri}[/link]\n")
        console.print(
            f"[bold]Enter the following code:[/bold] "
            f"[bold yellow]{user_code}[/bold yellow]\n"
        )

        # Open browser automatically
        console.print("Opening browser to verification page...")
        webbrowser.open(verification_uri)

        # Step 3: Poll for token
        console.print("\nWaiting for authentication to complete...")
        console.print("[dim](Polling for token...)[/dim]")

        token_data = poll_for_token(
            device_code=device_code,
            interval=interval,
            max_attempts=max(1, int(expires_in / interval)),
        )

        console.print("\n")  # New line after polling dots

        # Step 4: Store tokens
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in")

        if access_token:
            credentials.set_token(access_token, expires_in=expires_in)
            if refresh_token:
                credentials.set_refresh_token(refresh_token)
            credentials.set_token_auth_url(auth_url)

            # Record the login server-side (#837): the device grant
            # echoes the authorizing user, and the login-session record
            # carries this install's stable device id so audit spans
            # attribute to the device. Best-effort — an older auth
            # deployment without the logins route must not fail login.
            user_id = token_data.get("user_id")
            if user_id:
                login_session_id = create_login_session(auth_url, user_id)
                if login_session_id:
                    credentials.set_login_session_id(login_session_id)

            print_success("Authentication successful!")
            console.print(f"[dim]Authenticated against: {auth_url}[/dim]")
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
        False,
        "--confirm",
        "-y",
        help="Skip confirmation prompt",
    ),
) -> None:
    """
    Log out and clear stored credentials.

    Removes the stored access and refresh tokens from the credential store,
    after attempting server-side revocation (RFC 7009). Revocation is
    best-effort: logout still succeeds when the server is unreachable or
    deployed without a revocation endpoint. Logging out while not
    authenticated is a no-op reported as success.
    """
    try:
        access_token = credentials.get_token()
        had_token = access_token is not None
        if had_token:
            # Only confirm when there is something to log out of; the
            # not-logged-in path below stays a promptless no-op.
            confirm_destructive("log out and revoke the stored tokens", confirm)
            revoked = True
            refresh_token = credentials.get_refresh_token()
            # Revoke where the tokens are valid: the endpoint that minted
            # them. After a target switch the current endpoint would
            # reject them as unknown tokens and they would stay live.
            issuing_auth_url = credentials.get_token_auth_url()
            if refresh_token:
                revoked = (
                    revoke_token(
                        refresh_token,
                        "refresh_token",
                        auth_url=issuing_auth_url,
                    )
                    and revoked
                )
            revoked = (
                revoke_token(
                    access_token, "access_token", auth_url=issuing_auth_url
                )
                and revoked
            )
            if not revoked:
                console.print(
                    "[dim]Note: server-side token revocation was unavailable;"
                    " local credentials were cleared.[/dim]"
                )
            # Revoke the login-session record too (#837): the
            # bearer-owned path accepts our access token (same user).
            # Best-effort like token revocation; the local id is always
            # cleared.
            with contextlib.suppress(CredentialError):
                login_session_id = credentials.get_login_session_id()
                if login_session_id and issuing_auth_url:
                    delete_login_session(
                        issuing_auth_url, login_session_id, access_token
                    )
                credentials.delete_login_session_id()
            credentials.delete_token()
        # A stray refresh token without an access token is still cleared
        # locally (no revocation attempt on the logged-out path).
        with contextlib.suppress(CredentialError):
            credentials.delete_refresh_token()
    except CredentialError as e:
        print_error(f"Failed to log out: {e}")
        raise typer.Exit(1) from e

    if had_token:
        print_success("Logged out successfully.")
    else:
        print_success("Not logged in.")


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

    # A refresh token sent to the wrong endpoint is rejected opaquely by
    # the server; surface the credential/endpoint mismatch instead.
    ensure_endpoint_match()

    try:
        new_token = refresh_access_token()

        if output_json:
            import json

            expires_at = credentials.get_token_expires_at()
            # Machine-readable output: plain stdout write, since Rich's
            # word wrap can split long tokens mid-string and corrupt JSON.
            typer.echo(json.dumps({
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
                    console.print(
                        f"Expires at: {expiry_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}"
                    )
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
        # Plain stdout write: Rich's word wrap can split long values
        # mid-string and corrupt machine-readable JSON.
        import json

        typer.echo(json.dumps(status))
    else:
        if status["authenticated"]:
            print_success("Authenticated")
            console.print("You are logged in to Campus API.")
            console.print(f"Auth endpoint: {status['auth_url']}")

            if not status["endpoint_match"]:
                console.print(
                    "[red bold]Endpoint mismatch:[/red bold] the stored "
                    "token was issued by a different auth endpoint. "
                    "Run [bold]campus auth login[/bold] to re-authenticate."
                )
            if status["token_auth_url"]:
                console.print(f"Token issued by: {status['token_auth_url']}")
            else:
                console.print(
                    "[dim]Token issued by: unknown (stored before endpoint"
                    " binding; binds at next login or refresh)[/dim]"
                )

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
                        console.print(
                            f"Token expires in: [cyan]{minutes}m {seconds}s[/cyan]"
                        )

                    console.print(
                        f"Expires at: {expiry_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}"
                    )
                except ValueError:
                    console.print(f"Expires at: {status['expires_at']}")
            else:
                console.print("[dim](No expiry information available)[/dim]")

            if status["can_refresh"]:
                refresh_status = (
                    "[green]enabled[/green]" if config.auto_refresh
                    else "[yellow]disabled[/yellow]"
                )
                console.print(f"Auto-refresh: {refresh_status}")
        else:
            console.print("[yellow]Not authenticated[/yellow]")
            console.print(f"Auth endpoint: {status['auth_url']}")
            console.print("Run [bold]campus auth login[/bold] to authenticate.")
