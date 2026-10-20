"""campus.audit login/logout (#54).

The audit service only accepts its own API keys, so 'campus audit
login' stores a key from --api-key, CAMPUS_AUDIT_API_KEY, or an
interactive prompt instead of running the OAuth device flow. The key
is verified against the service (best-effort, never blocking on
network errors) and bound to the audit URL it was stored for, like
OAuth tokens are bound to their auth endpoint.
"""

import os
import sys

import requests
import typer
from rich.console import Console

from campus_cli.audit.client import (
    AUDIT_KEY_PREFIX,
    api_error_details,
    api_error_message,
    resolve_audit_url,
)
from campus_cli.auth.common import confirm_destructive
from campus_cli.credentials import CredentialError, credentials
from campus_cli.utils.output import print_error, print_success, print_warning

console = Console()

# Environment fallback for the key material, for scripts and CI.
AUDIT_API_KEY_ENV = "CAMPUS_AUDIT_API_KEY"


def _resolve_key_input(api_key_option: str | None) -> str:
    """Get the API key from the option, the environment, or a prompt.

    Raises:
        typer.Exit: When no source yields a key (non-interactive).
    """
    api_key = api_key_option or os.environ.get(AUDIT_API_KEY_ENV) or ""
    if not api_key and sys.stdin.isatty():
        api_key = typer.prompt("Audit API key", hide_input=True)
    api_key = api_key.strip()
    if not api_key:
        print_error(
            f"No API key given. Pass --api-key or set {AUDIT_API_KEY_ENV}."
        )
        raise typer.Exit(1)
    if not api_key.startswith(AUDIT_KEY_PREFIX):
        print_warning(
            f"The key does not look like an audit API key (expected the"
            f" {AUDIT_KEY_PREFIX}… prefix); storing it anyway."
        )
    return api_key


def verify_api_key(audit_url: str, api_key: str) -> str:
    """Check the key against the audit service before storing it.

    Any authenticated response proves the key: 200 needs apikeys:read,
    while 403 means the key is valid but scoped elsewhere (fine for
    trace-only student keys).

    Args:
        audit_url: The audit service base URL to verify against.
        api_key: The candidate plaintext key.

    Returns:
        "verified" when the server accepted the key, "unverified" when
        the service could not be reached (the key is stored anyway).

    Raises:
        typer.Exit: When the server rejected the key (nothing stored).
    """
    try:
        from campus_python import AuditRoot, CampusRequest, errors
    except ImportError:
        print_error("campus-api-python library not available.")
        raise typer.Exit(1) from None

    try:
        client = CampusRequest(base_url=audit_url, timeout=10, mode="device")
        client.set_bearer_authorization(api_key)
        AuditRoot(json_client=client).apikeys.list(limit=1)
    except (errors.APIError, requests.RequestException) as e:
        status, _ = api_error_details(e)
        if status == 401:
            print_error(
                "The audit service rejected this key (401);"
                " nothing was stored."
            )
            raise typer.Exit(1) from e
        if status == 403:
            # An authenticated rejection: the key works but lacks
            # apikeys:read (fine for trace-only student keys).
            console.print(
                "[dim]Key verified (lacks apikeys:read, so it cannot"
                " list keys — fine for trace-only keys).[/dim]"
            )
            return "verified"
        # Anything else (network error, 404 on older deployments, 5xx)
        # does not prove the key; store it unverified and say so.
        print_warning(
            f"Could not verify the key against the audit service"
            f" ({api_error_message(e)}); storing it unverified."
        )
        return "unverified"
    return "verified"


def login_cmd(
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        help=(
            "The audit API key (audit_v1_...). Falls back to the"
            f" {AUDIT_API_KEY_ENV} environment variable, then an"
            " interactive prompt."
        ),
    ),
    skip_verify: bool = typer.Option(
        False,
        "--skip-verify",
        help="Store the key without checking it against the service",
    ),
) -> None:
    """
    Store an API key for the campus.audit service (#54).

    Unlike OAuth tokens, audit keys never expire server-side into a
    refresh flow: a revoked or deleted key is cleared by re-running
    this command with a new one. The key is stored in the shared
    credential store, bound to the audit URL the CLI currently targets.
    """
    audit_url = resolve_audit_url()
    api_key = _resolve_key_input(api_key)

    if not skip_verify:
        verify_api_key(audit_url, api_key)

    try:
        credentials.set_audit_api_key(api_key, audit_url)
    except CredentialError as e:
        print_error(f"Failed to store the audit API key: {e}")
        raise typer.Exit(1) from e
    print_success("Audit API key stored.")
    console.print(f"[dim]Audit service: {audit_url}[/dim]")


def logout_cmd(
    confirm: bool = typer.Option(
        False, "--confirm", "-y", help="Skip confirmation prompt"
    ),
) -> None:
    """
    Clear the stored audit API key (local only).

    This does not disable the key server-side — audit keys cannot
    revoke themselves. To invalidate a key, revoke it first:
    'campus audit keys revoke --key-id <id>'.
    """
    try:
        if not credentials.get_audit_api_key():
            print_success("Not logged in to campus.audit.")
            return
        confirm_destructive(
            "clear the stored campus.audit API key", confirm
        )
        credentials.delete_audit_api_key()
    except CredentialError as e:
        print_error(f"Failed to log out: {e}")
        raise typer.Exit(1) from e

    print_success("Logged out of campus.audit (local key cleared).")
