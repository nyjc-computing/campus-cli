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
    refresh_access_token,
    resolve_auth_url,
    revoke_token,
)
from campus_cli.config import PUBLIC_OAUTH_CLIENT_ID, config
from campus_cli.credentials import CredentialError, credentials
from campus_cli.utils.clipboard import copy_to_clipboard
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


def _response_oauth_error(e: requests.RequestException) -> str | None:
    """Extract the RFC 6749 error code from a failed HTTP response.

    Campus OAuth errors surface as structured bodies carrying
    details.oauth_error ("invalid_scope", "invalid_client", ...);
    plain OAuth 2.0 bodies carry the code as the top-level "error"
    string. Returns None when neither shape is present.
    """
    response = getattr(e, "response", None)
    if response is None:
        return None
    try:
        error_obj = response.json().get("error", None)
    except ValueError:
        return None
    if isinstance(error_obj, dict):
        return error_obj.get("details", {}).get("oauth_error")
    return error_obj if isinstance(error_obj, str) else None


def request_device_code(scopes: list[str] | None = None) -> dict:
    """
    Request a device code from the authorization server.

    Args:
        scopes: Optional scope request (#865). Passed through to the
            device_authorize endpoint as the RFC 6749 space-delimited
            `scope` parameter; the server validates it against the
            client's registered allowlist and rejects unknown scopes.
            Absent means the server's default CLI scope set.

    Returns:
        Dict containing device_code, user_code, verification_uri, expires_in, interval.

    Raises:
        DeviceAuthError: If the request fails.
    """
    urls = get_auth_urls()
    data = {"client_id": CLI_CLIENT_ID}
    if scopes:
        data["scope"] = " ".join(scopes)

    try:
        response = requests.post(
            urls["device_code_url"],
            data=data,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        message = f"Failed to request device code: {_response_error_detail(e)}"
        # The server message names the offending scopes but not the
        # remedy: the allowlist is operator-controlled, so point there.
        if _response_oauth_error(e) == "invalid_scope":
            message += (
                " The requested scopes are outside this CLI client's"
                " registered allowlist — ask the operator to widen it"
                " (campus client update --client-id <id>"
                " --allowed-scope <scope>)."
            )
        raise DeviceAuthError(message) from e


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
    scope: list[str] = typer.Option(  # noqa: B008
        [],
        "--scope",
        "-s",
        help=(
            "Request a management scope for the token (#865); repeat for"
            " multiple (e.g. --scope clients:write). The server rejects"
            " scopes outside this client's registered allowlist — an"
            " operator must widen it first."
        ),
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
    # An explicit --scope request bypasses the short-circuit too (#38):
    # it asks for a token minted with those scopes, so a valid stored
    # token must not swallow it as a no-op (the documented upgrade path
    # is re-login with the wider scope).
    existing_token = credentials.get_token()
    if existing_token and not credentials.is_token_expired():
        mismatch = endpoint_mismatch()
        if mismatch is None and not scope:
            console.print("[yellow]Already authenticated.[/yellow]")
            console.print(f"[dim]Authenticated against: {auth_url}[/dim]")
            if output_token:
                console.print(existing_token)
            return
        if mismatch is not None:
            stored, _ = mismatch
            console.print(
                f"[yellow]Stored credentials were issued by {stored}, but the "
                f"CLI is targeting {auth_url}. Re-authenticating.[/yellow]"
            )
        else:
            console.print(
                "[dim]Re-authenticating to request scopes: "
                f"{' '.join(scope)}[/dim]"
            )

    console.print(f"[dim]Authenticating against: {auth_url}[/dim]")

    try:
        # Step 1: Request device code
        console.print("[bold]Requesting device code...[/bold]")
        device_auth_data = request_device_code(scopes=list(scope))

        user_code = device_auth_data["user_code"]
        verification_uri = device_auth_data["verification_uri"]
        # Prefer verification_uri_complete (RFC 8628 §3.3.1), which embeds
        # the user code: the consent page (#869) discloses the requested
        # scopes only on that pre-filled page. Older servers may omit it.
        verification_uri_complete = device_auth_data.get(
            "verification_uri_complete"
        )
        device_code = device_auth_data["device_code"]
        # A zero/absent interval would zero-divide below; 5s is the
        # RFC 8628 default when the server omits it.
        interval = device_auth_data.get("interval") or 5
        expires_in = device_auth_data.get("expires_in", 300)

        # Step 2: Display instructions to user
        console.print(
            "\n[bold cyan]To authenticate, use a web browser to open:[/bold cyan]"
        )
        if verification_uri_complete:
            console.print(
                f"[link={verification_uri_complete}]"
                f"{verification_uri_complete}[/link]\n"
            )
        # Keep the bare URI + code visible regardless (RFC 8628 wants the
        # code displayed; some users open the bare URL on another device).
        console.print(f"[link={verification_uri}]{verification_uri}[/link]\n")
        console.print(
            f"[bold]Enter the following code:[/bold] "
            f"[bold yellow]{user_code}[/bold yellow]\n"
        )

        # Best-effort convenience (#43): a transcription typo costs a
        # full browser round-trip, so try the clipboard; failure prints
        # nothing extra and never blocks login.
        copy_status = copy_to_clipboard(user_code)
        if copy_status == "native":
            console.print("[dim]Code copied to clipboard.[/dim]")
        elif copy_status == "osc52":
            console.print(
                "[dim]Sent the code to your terminal's clipboard (OSC 52);"
                " if it doesn't paste, copy it manually.[/dim]"
            )

        # Open browser automatically
        console.print("Opening browser to verification page...")
        webbrowser.open(verification_uri_complete or verification_uri)

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

            # Record the granted scopes and authorizing principal
            # locally (#45), so `campus auth status` can report them
            # without a network round-trip. Purely additive: the device
            # grant response carries the space-joined `scope` and the
            # `user_id`; credentials stored before this simply lack the
            # keys and status reports them as unknown.
            scopes = token_data.get("scope")
            if isinstance(scopes, str) and scopes.strip():
                credentials.set_token_scopes(scopes.split())
            user_id = token_data.get("user_id")
            if user_id:
                credentials.set_token_user_id(user_id)

            # Record the login server-side (#837): the device grant
            # echoes the authorizing user (already extracted above for
            # the local principal record, #45), and the login-session
            # record carries this install's stable device id so audit
            # spans attribute to the device. Best-effort — an older
            # auth deployment without the logins route must not fail
            # login.
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
    offline: bool = typer.Option(
        False,
        "--offline",
        help=(
            "Skip the authenticated validity check (no network calls;"
            " the check verifies the stored token against GET users/,"
            " where FORBIDDEN means valid and UNAUTHORIZED invalid)."
            " Exit codes: 0 when a stored token is present and valid —"
            " or its check was skipped, unreachable, or inconclusive;"
            " 1 when not logged in or the token was rejected by the"
            " server."
        ),
    ),
) -> None:
    """
    Show the stored credential's identity and scopes (#45).

    Prints the auth client id, the endpoint in use (and the endpoint
    that minted the token), the authenticated principal, the scopes
    the stored token carries, and token expiry — everything scripts
    need to answer "what can this token do?" before acting. Unless
    --offline is given, a lightweight authenticated check also reports
    whether the token still authenticates (network errors are
    non-fatal: they are reported without failing the command).

    Exit code: 1 when not logged in, or when the stored token is
    rejected by the server; 0 otherwise.
    """
    from campus_cli.auth.status import run_status

    run_status(output_json=output_json, offline=offline)
