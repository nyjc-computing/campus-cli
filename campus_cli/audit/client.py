"""Shared plumbing for campus.audit commands (#54).

The audit service (/audit/v1) authenticates with one of its own API
keys (`audit_v1_...`) sent as a Bearer token — OAuth user tokens are
not accepted — so it gets its own credential slot and client here,
parallel to the OAuth machinery in campus_cli.auth. Like the OAuth
tokens, the stored key is bound to the service URL it was stored
against and rejected on a target mismatch.
"""

import typer

from campus_cli.config import config
from campus_cli.credentials import CredentialError, credentials
from campus_cli.utils.output import print_error

# Key material of the campus.audit service is minted with this prefix;
# anything else is almost certainly a token or a paste error.
AUDIT_KEY_PREFIX = "audit_v1_"


def resolve_audit_url() -> str:
    """Resolve the audit service base URL the CLI currently targets.

    Exits with a clean, actionable error when ENV/CAMPUS_ENV is invalid,
    instead of letting config.audit_url's ValueError escape as a
    traceback from whichever command touched it first.

    Returns:
        The targeted audit service base URL (no /audit/v1 prefix; the
        resource root carries it).
    """
    try:
        return config.audit_url
    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(1) from e


def _stored_audit_key_url() -> str | None:
    """Read the audit URL the stored key was bound to.

    Raises:
        typer.Exit: If the credential store cannot be read (locked
                    keyring, unreadable fallback file) — the store
                    failure is reported, not raised as a traceback.
    """
    try:
        return credentials.get_audit_key_url()
    except CredentialError as e:
        print_error(f"Failed to read the stored audit API key: {e}")
        raise typer.Exit(1) from e


def audit_endpoint_mismatch() -> tuple[str, str] | None:
    """
    Check whether the stored audit key was stored for the targeted service URL.

    Returns:
        (stored_url, current_url) on mismatch, None otherwise. Keys
        stored before URL binding (no stored URL) are treated as
        matching; they bind at the next 'campus audit login'.
    """
    stored = _stored_audit_key_url()
    if not stored:
        return None
    current = resolve_audit_url()
    if stored.rstrip("/") != current.rstrip("/"):
        return (stored, current)
    return None


def ensure_audit_endpoint_match() -> None:
    """
    Fail fast if the stored audit key targets a different service URL.

    Raises:
        typer.Exit: If the stored key's audit URL differs from the one
                    the CLI currently targets.
    """
    mismatch = audit_endpoint_mismatch()
    if mismatch is None:
        return
    stored, current = mismatch
    print_error(
        f"Stored audit API key was stored for {stored} but the CLI is "
        f"targeting {current}. Re-run 'campus audit login' against "
        f"{current}."
    )
    raise typer.Exit(1)


def get_audit_client():
    """
    Get an authenticated campus.audit client (#54).

    Returns:
        A campus_python AuditRoot authenticating with the stored key.

    Raises:
        typer.Exit: If no key is stored, or it targets another URL.
    """
    try:
        api_key = credentials.get_audit_api_key()
    except CredentialError as e:
        print_error(f"Failed to read the stored audit API key: {e}")
        raise typer.Exit(1) from e
    if not api_key:
        print_error(
            "Not authenticated with campus.audit. Run 'campus audit login'"
            " (--api-key, or set CAMPUS_AUDIT_API_KEY) first."
        )
        raise typer.Exit(1)

    ensure_audit_endpoint_match()

    try:
        from campus_python import AuditRoot, CampusRequest

        client = CampusRequest(
            base_url=resolve_audit_url(), timeout=30, mode="device"
        )
        client.set_bearer_authorization(api_key)
        return AuditRoot(json_client=client)
    except ImportError:
        print_error("campus-api-python library not available.")
        raise typer.Exit(1) from None


def api_error_details(e: Exception) -> tuple[int | None, str]:
    """Best-effort (HTTP status, human message) from a failed audit call.

    campus_python maps non-2xx responses to errors.APIError carrying
    the status code and the server's error_description; raw transport
    failures (requests.HTTPError or connection errors) keep their
    exception text, with any structured Campus error body unpacked.
    """
    status = getattr(e, "status_code", None)
    description = getattr(e, "error_description", None)
    if status is None:
        response = getattr(e, "response", None)
        status = getattr(response, "status_code", None)
        try:
            error_obj = response.json().get("error", "")
        except (ValueError, AttributeError):
            error_obj = ""
        if isinstance(error_obj, dict):
            description = error_obj.get("message") or error_obj.get("code")
        elif error_obj:
            description = error_obj
    if description:
        return status, str(description)
    return status, str(e)


def api_error_message(e: Exception) -> str:
    """Extract a human-readable message from a failed audit API call."""
    return api_error_details(e)[1]


def fail_api(action: str, e: Exception) -> None:
    """Report a failed audit API call and exit 1.

    Appends the standing remedy for the two rejections the operator can
    act on without reading the docs: a rejected key (re-login) and a
    scope shortfall (mint or widen the key).
    """
    status, message = api_error_details(e)
    hint = ""
    if status == 401:
        hint = " Re-run 'campus audit login' with a valid key."
    elif status == 403:
        hint = (
            " The stored key lacks the required scope;"
            " mint or update it with 'campus audit keys'."
        )
    # The server's message may already be a sentence: don't double the
    # full stop when appending the remedy hint.
    detail = message.strip()
    if detail and not detail.endswith((".", "!", "?")):
        detail += "."
    print_error(f"Failed to {action}: {detail}{hint}")
    raise typer.Exit(1) from e
