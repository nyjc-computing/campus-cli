"""Shared utilities for auth commands."""

import os
import sys

import requests
import typer

from campus_cli.config import PUBLIC_OAUTH_CLIENT_ID, config
from campus_cli.credentials import credentials
from campus_cli.utils.output import print_error


class RefreshError(Exception):
    """Exception raised for token refresh errors."""

    pass


# Session-level opt-out from confirmation prompts, for agents and other
# non-interactive callers (per-command --confirm/-y still takes precedence).
ASSUME_YES_ENV = "CAMPUS_ASSUME_YES"


def assume_yes_from_env() -> bool:
    """Whether the CAMPUS_ASSUME_YES environment variable is set truthy."""
    return os.environ.get(ASSUME_YES_ENV, "").strip().lower() in (
        "1", "true", "yes",
    )


def confirm_destructive(message: str, skip: bool) -> None:
    """Confirm a destructive action, refusing fast when there is no TTY.

    Non-interactive callers (agents, CI) never block waiting for input:
    without -y (or CAMPUS_ASSUME_YES) the command exits 1 with an error
    naming the remedy, rather than hanging on or opaquely aborting the
    confirmation read.

    Args:
        message: What the command is about to do (lowercase clause).
        skip: True when the caller passed --confirm/-y.

    Raises:
        typer.Exit: In non-interactive mode without a confirmation waiver.
        typer.Abort: When the user declines the interactive prompt.
    """
    if skip or assume_yes_from_env():
        return
    if not sys.stdin.isatty():
        print_error(
            f"Refusing to proceed without confirmation (no TTY): {message}."
            f" Re-run with -y, or set {ASSUME_YES_ENV}=1 for"
            " non-interactive use."
        )
        raise typer.Exit(1)
    typer.confirm(message, abort=True)


def dry_run_option():
    """Build the shared --dry-run option for API-backed commands."""
    return typer.Option(
        False,
        "--dry-run",
        help="Show the equivalent Python API code without calling the API",
    )


def resolve_auth_url() -> str:
    """Resolve the auth endpoint the CLI currently targets.

    Exits with a clean, actionable error when ENV/CAMPUS_ENV is invalid,
    instead of letting config.auth_url's ValueError escape as a traceback
    from whichever command touched it first.

    Returns:
        The targeted auth endpoint URL.
    """
    try:
        return config.auth_url
    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(1) from e


def get_auth_urls(auth_url: str | None = None) -> dict:
    """
    Get OAuth endpoint URLs.

    Uses the given auth endpoint, or resolves the current target from
    CAMPUS_AUTH_URL env var, config file, ENV/CAMPUS_ENV, or default.

    Args:
        auth_url: Base endpoint to build URLs from; defaults to the
                  CLI's current target.

    Returns:
        Dict with device_code_url and token_url.
    """
    base_url = auth_url if auth_url is not None else resolve_auth_url()

    return {
        "device_code_url": f"{base_url}/oauth/device_authorize",
        "token_url": f"{base_url}/oauth/token",
        "revoke_url": f"{base_url}/oauth/revoke",
    }


def revoke_token(
    token: str, token_type_hint: str, auth_url: str | None = None
) -> bool:
    """
    Revoke a token via the auth server's revocation endpoint (RFC 7009).

    Best-effort by design: logout must still succeed when the server is
    unreachable or deployed without /oauth/revoke, so any failure is
    reported as False instead of raising.

    Args:
        token: The access or refresh token to revoke.
        token_type_hint: "access_token" or "refresh_token".
        auth_url: Revoke against this endpoint instead of the CLI's
                  current target. Callers should pass the endpoint that
                  minted the token — a token is unknown to (and leaked
                  to) any other endpoint of the deployment.

    Returns:
        True if the server confirmed revocation, False otherwise.
    """
    urls = get_auth_urls(auth_url)

    try:
        response = requests.post(
            urls["revoke_url"],
            data={
                "token": token,
                "token_type_hint": token_type_hint,
                "client_id": PUBLIC_OAUTH_CLIENT_ID,
            },
            timeout=10,
        )
        return response.status_code == 200
    except requests.RequestException:
        return False


def normalize_auth_url(url: str) -> str:
    """Normalize an auth URL for comparison (trailing slashes stripped)."""
    return url.rstrip("/")


def endpoint_mismatch() -> tuple[str, str] | None:
    """
    Check whether the stored credentials were issued by the targeted endpoint.

    Returns:
        (stored_auth_url, current_auth_url) on mismatch, None otherwise.
        Credentials stored before endpoint binding (no stored URL) are
        treated as matching; they bind at the next login or refresh.
    """
    stored = credentials.get_token_auth_url()
    if not stored:
        return None
    current = resolve_auth_url()
    if normalize_auth_url(stored) != normalize_auth_url(current):
        return (stored, current)
    return None


def ensure_endpoint_match() -> None:
    """
    Fail fast if stored credentials were issued by a different auth endpoint.

    Raises:
        typer.Exit: If the stored token's issuing endpoint differs from
                    the endpoint the CLI currently targets.
    """
    mismatch = endpoint_mismatch()
    if mismatch is None:
        return
    stored, current = mismatch
    print_error(
        f"Stored token was issued by {stored} but the CLI is targeting "
        f"{current}. Run 'campus auth login' to re-authenticate against "
        f"{current}."
    )
    raise typer.Exit(1)


def refresh_access_token() -> str:
    """
    Refresh the access token using the stored refresh token.

    Returns:
        The new access token.

    Raises:
        RefreshError: If refresh fails.
    """
    refresh_token = credentials.get_refresh_token()
    if not refresh_token:
        raise RefreshError("No refresh token available. Please login again.")

    urls = get_auth_urls()

    try:
        response = requests.post(
            urls["token_url"],
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": PUBLIC_OAUTH_CLIENT_ID,
            },
            timeout=30,
        )

        if response.status_code != 200:
            is_json = response.headers.get("content-type", "").startswith(
                "application/json"
            )
            error_data = response.json() if is_json else {}
            error_msg = error_data.get(
                "error_description",
                error_data.get("error", "Refresh failed")
            )
            raise RefreshError(f"Token refresh failed: {error_msg}")

        token_data = response.json()

        # Extract tokens
        access_token = token_data.get("access_token")
        new_refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in")

        if not access_token:
            raise RefreshError("Refresh response did not contain access token")

        # Store the new tokens, bound to the endpoint that minted them
        credentials.set_token(access_token, expires_in=expires_in)
        if new_refresh_token:
            credentials.set_refresh_token(new_refresh_token)
        credentials.set_token_auth_url(config.auth_url)

        return access_token

    except requests.RequestException as e:
        raise RefreshError(f"Network error during token refresh: {e}") from e
    except (ValueError, KeyError) as e:
        raise RefreshError(f"Invalid response from token endpoint: {e}") from e


def get_api_client(auto_refresh: bool | None = None):
    """
    Get an authenticated API client, with optional auto-refresh.

    Args:
        auto_refresh: Override the default auto-refresh setting.
                     If None, uses the config setting.

    Returns:
        An authenticated campus API client.

    Raises:
        typer.Exit: If authentication fails.
    """
    # Determine if auto-refresh is enabled
    if auto_refresh is None:
        auto_refresh = config.auto_refresh

    token = credentials.get_token()
    if not token:
        print_error("Not authenticated. Run 'campus auth login' first.")
        raise typer.Exit(1)

    # Fail fast on a credential/endpoint mismatch before any refresh
    # attempt: a refresh token sent to the wrong endpoint would only
    # surface as an opaque server-side rejection.
    ensure_endpoint_match()

    # Check if token needs refresh
    threshold = config.refresh_threshold if auto_refresh else 0
    if credentials.is_token_expired(threshold_seconds=threshold):
        if auto_refresh:
            refresh_token = credentials.get_refresh_token()
            if refresh_token:
                try:
                    token = refresh_access_token()
                except RefreshError as e:
                    print_error(f"Failed to refresh token: {e}")
                    print_error("Please run 'campus auth login' to authenticate again.")
                    raise typer.Exit(1) from None
            else:
                print_error("Access token expired and no refresh token available.")
                print_error(
                    "Please run 'campus auth login' to authenticate again."
                )
                raise typer.Exit(1)
        else:
            print_error("Access token expired.")
            print_error(
                "Run 'campus auth refresh' to refresh, or "
                "'campus auth login' to authenticate again."
            )
            raise typer.Exit(1)

    try:
        from campus_cli.api import CampusClient

        return CampusClient(token=token)
    except ImportError:
        print_error("campus-api-python library not available.")
        raise typer.Exit(1) from None


def get_token_status() -> dict:
    """
    Get the current token status information.

    Returns:
        Dict with keys: authenticated, expires_at, is_expired, can_refresh,
        auth_url, token_auth_url, endpoint_match
    """
    token = credentials.get_token()
    refresh_token = credentials.get_refresh_token()
    expires_at = credentials.get_token_expires_at()
    token_auth_url = credentials.get_token_auth_url()

    return {
        "authenticated": token is not None,
        "expires_at": expires_at,
        "is_expired": credentials.is_token_expired() if token else False,
        "can_refresh": refresh_token is not None,
        "auth_url": resolve_auth_url(),
        "token_auth_url": token_auth_url,
        # Credentials stored before endpoint binding (no stored URL) count
        # as matching; they bind at the next login or refresh.
        "endpoint_match": (
            endpoint_mismatch() is None if token else True
        ),
    }
