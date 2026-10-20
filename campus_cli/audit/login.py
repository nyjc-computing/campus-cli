"""campus.audit login/logout/status (#54, #62).

The audit service only accepts its own API keys, so 'campus audit
login' stores a key from --api-key, CAMPUS_AUDIT_API_KEY, or an
interactive prompt instead of running the OAuth device flow. The key
is verified against the service (best-effort, never blocking on
network errors) and bound to the audit URL it was stored for, like
OAuth tokens are bound to their auth endpoint. 'status' reports the
stored key's local state; the audit service has no "who am I"
endpoint, so it is a purely offline view.
"""

import json
import os
import sys
from datetime import datetime, timezone

import requests
import typer
from rich.console import Console

from campus_cli.audit.client import (
    AUDIT_KEY_PREFIX,
    api_error_details,
    api_error_message,
    mismatch_message,
    resolve_audit_url,
)
from campus_cli.audit.keys import _parse_timestamp
from campus_cli.auth.common import confirm_destructive
from campus_cli.config import config
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


def _relative_age(parsed: datetime) -> str:
    """Coarse age of a stored key ('3 hours ago')."""
    seconds = int((datetime.now(timezone.utc) - parsed).total_seconds())
    if seconds < 0:
        # Clock skew between storage and now; don't render a negative.
        return "just now"
    if seconds < 90:
        return f"{seconds} seconds ago"
    minutes = seconds // 60
    if minutes < 90:
        return f"{minutes} minutes ago"
    hours = minutes // 60
    if hours < 36:
        return f"{hours} hours ago"
    return f"{hours // 24} days ago"


def status_cmd(
    output_json: bool = typer.Option(
        False, "--json", help="Output status as JSON"
    ),
) -> None:
    """
    Show the stored audit key's local state (#62).

    The audit service has no "who am I" endpoint, so this is a purely
    local view: whether a key is stored, which URL it is bound to, the
    URL the CLI currently targets (flagging a mismatch the way the
    commands' guard does), and when the key was stored. No network
    call is made — unlike 'campus auth status', there is no online
    check. Exit code: 1 when no key is stored, 0 otherwise (a
    bound/target mismatch is reported but does not fail the check;
    every API-backed command refuses on its own until re-login).
    """
    try:
        api_key = credentials.get_audit_api_key()
        key_url = credentials.get_audit_key_url()
        stored_at = credentials.get_audit_key_stored_at()
    except CredentialError as e:
        print_error(f"Failed to read the stored audit API key: {e}")
        raise typer.Exit(1) from e

    # A local view must not die on an unresolvable target: an invalid
    # ENV/CAMPUS_ENV is exactly the state worth diagnosing here.
    try:
        current_url: str | None = config.audit_url
    except ValueError:
        current_url = None

    mismatch = mismatch_message(key_url, current_url)

    if output_json:
        # Plain stdout write: Rich's word wrap can corrupt JSON for a
        # parsing consumer (same reasoning as 'campus auth refresh').
        typer.echo(json.dumps({
            "authenticated": api_key is not None,
            "audit_url": current_url,
            "key_url": key_url,
            "endpoint_match": mismatch is None,
            "stored_at": stored_at,
        }))
    elif not api_key:
        print_error(
            "Not logged in to campus.audit."
            " Run 'campus audit login' first."
        )
        if current_url:
            console.print(f"Audit service (target): {current_url}")
    else:
        print_success("Audit API key stored.")
        if current_url:
            console.print(f"Audit service (target): {current_url}")
        else:
            console.print(
                "Audit service (target): [red]unknown[/red]"
                " (invalid ENV/CAMPUS_ENV; set CAMPUS_AUDIT_URL)"
            )
        console.print(f"Key bound to: {key_url or '[dim]none[/dim]'}")
        parsed_stored_at = _parse_timestamp(stored_at)
        if parsed_stored_at is None:
            console.print("[dim]Stored: unknown[/dim]")
        else:
            console.print(
                f"Stored: {parsed_stored_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
                f" ({_relative_age(parsed_stored_at)})"
            )
        if mismatch:
            print_error(mismatch)

    if not api_key:
        raise typer.Exit(1)
