"""Shared utilities for auth commands."""

import requests
import typer

from campus_cli.config import PUBLIC_OAUTH_CLIENT_ID, config
from campus_cli.credentials import credentials
from campus_cli.utils.output import print_error


class RefreshError(Exception):
    """Exception raised for token refresh errors."""

    pass


def dry_run_option():
    """Build the shared --dry-run option for API-backed commands."""
    return typer.Option(
        False,
        "--dry-run",
        help="Show the equivalent Python API code without calling the API",
    )


def get_auth_urls() -> dict:
    """
    Get OAuth endpoint URLs.

    Uses CAMPUS_AUTH_URL env var, config file, or default.

    Returns:
        Dict with device_code_url and token_url.
    """
    base_url = config.auth_url

    return {
        "device_code_url": f"{base_url}/oauth/device_authorize",
        "token_url": f"{base_url}/oauth/token",
        "revoke_url": f"{base_url}/oauth/revoke",
    }


def revoke_token(token: str, token_type_hint: str) -> bool:
    """
    Revoke a token via the auth server's revocation endpoint (RFC 7009).

    Best-effort by design: logout must still succeed when the server is
    unreachable or deployed without /oauth/revoke, so any failure is
    reported as False instead of raising.

    Args:
        token: The access or refresh token to revoke.
        token_type_hint: "access_token" or "refresh_token".

    Returns:
        True if the server confirmed revocation, False otherwise.
    """
    urls = get_auth_urls()

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

        # Store the new tokens
        credentials.set_token(access_token, expires_in=expires_in)
        if new_refresh_token:
            credentials.set_refresh_token(new_refresh_token)

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
        Dict with keys: authenticated, expires_at, is_expired, can_refresh
    """
    token = credentials.get_token()
    refresh_token = credentials.get_refresh_token()
    expires_at = credentials.get_token_expires_at()

    return {
        "authenticated": token is not None,
        "expires_at": expires_at,
        "is_expired": credentials.is_token_expired() if token else False,
        "can_refresh": refresh_token is not None,
    }
