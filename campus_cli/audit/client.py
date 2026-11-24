"""Shared plumbing for campus.audit commands (#54).

The audit service's versioned API (/audit/v1) authenticates with one
of its own API keys (`audit_v1_...`) sent as a Bearer token — OAuth
user tokens are not accepted (the service's web UI has a separate
browser gate, campus#929/#916) — so it gets its own credential slot
and client here, parallel to the OAuth machinery in campus_cli.auth.
Like the OAuth tokens, the stored key is bound to the service URL it
was stored against and rejected on a target mismatch.
"""

from typing import NoReturn

import typer

from campus_cli.config import config
from campus_cli.credentials import CredentialError, credentials
from campus_cli.utils.output import print_error, print_error_json

# Key material of the campus.audit service is minted with this prefix;
# anything else is almost certainly a token or a paste error.
AUDIT_KEY_PREFIX = "audit_v1_"


def unwrap_payload(result):
    """Return the parsed JSON payload for either SDK response shape.

    SDK v0.11.0 methods are annotated ``-> JsonResponse`` but return the
    ``CampusResponse`` wrapper, which has ``.json()`` and no ``.get()``
    (campus-cli#112); older pins returned parsed payloads directly.
    Duck-type on ``.json()`` so every audit command renders correctly
    against both. The traces commands did this privately first; it moved
    here when the keys commands were found still reading the wrapper as
    a dict, which lost the one-time plaintext of a minted key.
    """
    return result.json() if hasattr(result, "json") else result


def resolve_audit_url(*, as_json: bool = False) -> str:
    """Resolve the audit service base URL the CLI currently targets.

    Exits with a clean, actionable error when ENV/CAMPUS_ENV is invalid,
    instead of letting config.audit_url's ValueError escape as a
    traceback from whichever command touched it first.

    Args:
        as_json: Emit the failure as a flat error envelope on stdout
            instead of a human sentence on stderr (--json callers).

    Returns:
        The targeted audit service base URL (no /audit/v1 prefix; the
        resource root carries it).
    """
    try:
        return config.audit_url
    except ValueError as e:
        fail_command(str(e), as_json=as_json, cause=e)


def _stored_audit_key_url(*, as_json: bool = False) -> str | None:
    """Read the audit URL the stored key was bound to.

    Raises:
        typer.Exit: If the credential store cannot be read (locked
                    keyring, unreadable fallback file) — the store
                    failure is reported, not raised as a traceback.
    """
    try:
        return credentials.get_audit_key_url()
    except CredentialError as e:
        fail_command(
            f"Failed to read the stored audit API key: {e}",
            as_json=as_json,
            cause=e,
        )


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


def mismatch_message(stored: str | None, current: str | None) -> str | None:
    """The standing binding-mismatch sentence, or None when URLs match.

    Shared by the command guard and 'campus audit status' (#62) so the
    two word the problem identically.
    """
    if not stored or not current:
        return None
    if stored.rstrip("/") == current.rstrip("/"):
        return None
    return (
        f"Stored audit API key was stored for {stored} but the CLI is "
        f"targeting {current}. Re-run 'campus audit login' against "
        f"{current}."
    )


def ensure_audit_endpoint_match(*, as_json: bool = False) -> None:
    """
    Fail fast if the stored audit key targets a different service URL.

    Args:
        as_json: Emit the failure as a flat error envelope on stdout
            instead of a human sentence on stderr (--json callers).

    Raises:
        typer.Exit: If the stored key's audit URL differs from the one
                    the CLI currently targets.
    """
    mismatch = audit_endpoint_mismatch()
    if mismatch is None:
        return
    stored, current = mismatch
    fail_command(mismatch_message(stored, current), as_json=as_json)


def get_audit_client(*, as_json: bool = False):
    """
    Get an authenticated campus.audit client (#54).

    Args:
        as_json: Emit guard failures as flat error envelopes on stdout
            instead of human sentences on stderr (--json callers).

    Returns:
        A campus_python AuditRoot authenticating with the stored key.

    Raises:
        typer.Exit: If no key is stored, or it targets another URL.
    """
    try:
        api_key = credentials.get_audit_api_key()
    except CredentialError as e:
        fail_command(
            f"Failed to read the stored audit API key: {e}",
            as_json=as_json,
            cause=e,
        )
    if not api_key:
        fail_command(
            "Not authenticated with campus.audit. Run 'campus audit login'"
            " (--api-key, or set CAMPUS_AUDIT_API_KEY) first.",
            as_json=as_json,
        )

    ensure_audit_endpoint_match(as_json=as_json)

    try:
        from campus_python import AuditRoot, CampusRequest

        client = CampusRequest(
            base_url=resolve_audit_url(as_json=as_json),
            timeout=30,
            mode="device",
        )
        client.set_bearer_authorization(api_key)
        return AuditRoot(json_client=client)
    except ImportError:
        fail_command(
            "campus-api-python library not available.",
            as_json=as_json,
        )


def _render_field_errors(e: Exception) -> str:
    """Render the server's field-level validation errors, when present.

    The server's 422 body carries an errors array (field, code,
    message) that campus_python parses into APIError.errors; without
    this a rejected 'keys new' would report only "One or more fields
    are invalid" with no indication of which field was rejected.
    """
    parts = []
    for field_error in getattr(e, "errors", None) or []:
        piece = str(getattr(field_error, "field", "?"))
        code = getattr(field_error, "code", None)
        message = getattr(field_error, "message", None)
        if code:
            piece += f" ({code}"
            if message:
                piece += f": {message}"
            piece += ")"
        elif message:
            piece += f": {message}"
        parts.append(piece)
    return "; ".join(parts)


def api_error_details(e: Exception) -> tuple[int | None, str]:
    """Best-effort (HTTP status, human message) from a failed audit call.

    campus_python maps non-2xx responses to errors.APIError carrying
    the status code and the server's error_description; raw transport
    failures (requests.HTTPError or connection errors) keep their
    exception text, with any structured Campus error body unpacked.

    A non-2xx failure with no description (a proxy's HTML 502, an
    empty body, a misrouted 404 page) falls back to "HTTP <status>" —
    the status is the one breadcrumb an operator can act on. The 422
    field-level errors array, when present, is appended so a rejected
    payload names the offending field.
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
        message = str(description)
    elif status is not None:
        message = f"HTTP {status}"
    else:
        message = str(e)

    fields = _render_field_errors(e)
    if fields:
        message = f"{message} (fields: {fields})"
    return status, message


def api_error_message(e: Exception) -> str:
    """Extract a human-readable message from a failed audit API call."""
    return api_error_details(e)[1]


def api_error_code(e: Exception) -> str | None:
    """Best-effort machine error code from a failed audit API call.

    campus_python's APIError carries the server envelope's error code
    ("NOT_FOUND", "VALIDATION_FAILED", ...); raw transport failures
    unpack the Campus body's error.code. CLI-side failures (guards,
    argument validation) have no code — callers emit null rather than
    inventing a vocabulary the service doesn't speak.
    """
    code = getattr(e, "error", None)
    if isinstance(code, str) and code:
        return code
    response = getattr(e, "response", None)
    try:
        error_obj = response.json().get("error", "")
    except (ValueError, AttributeError):
        return None
    if isinstance(error_obj, dict) and error_obj.get("code"):
        return str(error_obj["code"])
    return None


def fail_command(
    message: str,
    *,
    as_json: bool = False,
    code: str | None = None,
    status: int | None = None,
    cause: Exception | None = None,
) -> NoReturn:
    """Report a failed audit command and exit 1.

    The one exit point for CLI-side failures (guards, argument
    validation) and the JSON-mode twin of print_error: with as_json the
    message ships as the campus flat error envelope on stdout —
    ``{"error", "error_description", "status"}``, the same shape the
    service speaks — so a --json caller parses one stream regardless of
    outcome, and the non-zero exit still separates success from
    failure.

    Args:
        message: Human-readable failure description.
        as_json: Emit the flat error envelope on stdout instead of the
            sentence on stderr (--json callers).
        code: Machine error code (server's, when known; None for
            CLI-side failures).
        status: HTTP status (None for CLI-side failures).
        cause: The triggering exception, chained for tracebacks.
    """
    if as_json:
        print_error_json({
            "error": code,
            "error_description": message,
            "status": status,
        })
    else:
        print_error(message)
    raise typer.Exit(1) from cause


def fail_api(action: str, e: Exception, *, as_json: bool = False) -> None:
    """Report a failed audit API call and exit 1.

    Appends the standing remedy for the two rejections the operator can
    act on without reading the docs: a rejected key (re-login) and a
    scope shortfall (mint or widen the key). With as_json the failure
    ships as the flat error envelope (see fail_command) carrying the
    server's error code and the HTTP status.
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
    fail_command(
        f"Failed to {action}: {detail}{hint}",
        as_json=as_json,
        code=api_error_code(e),
        status=status,
        cause=e,
    )
