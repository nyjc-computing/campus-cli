"""`campus auth status` — stored-token identity and scopes (#45).

Tokens carry exactly the scopes requested at login (no accumulation),
so the scopes recorded at login describe the stored token until it is
replaced. This module assembles that locally-held identity — client,
endpoints, principal, scopes, expiry — and, unless --offline is given,
adds a lightweight authenticated validity check.

The validity check (#45) hits GET <auth>/users/ with the bearer token
and reads only the status code, which the error envelope design keeps
meaningful:

- 403 FORBIDDEN — the token authenticated but may not list users
  (users:read is operator/admin-only): the token is valid.
- 401 UNAUTHORIZED — the token is unknown/revoked/expired: invalid.
- 200 — a users:read token that listed users: valid.

Raw requests rather than the campus_python client: the SDK's
CampusRequest wraps requests.RequestException as errors.ServerError,
which would conflate "could not reach server" with a real HTTP 500 —
the three-state machine below needs the two apart. This also matches
the device-flow HTTP style in login.py.

States and exit codes (documented in the command's help):

- not logged in — friendly message, exit 1 (both modes).
- token rejected (401) — reported as invalid, exit 1.
- could not reach server (network error) — third state, NON-FATAL:
  warning printed, exit 0, validity reported as "unreachable".
- any other inconclusive probe result (e.g. 5xx) — exit 0, validity
  "unknown".
"""

import json
from datetime import datetime, timezone

import requests
import typer

from campus_cli.auth import common
from campus_cli.auth.common import get_token_status
from campus_cli.config import PUBLIC_OAUTH_CLIENT_ID
from campus_cli.utils.output import console, print_success, print_warning

# Validity states for the token check. "not_checked" is the --offline
# value; None (JSON null) is used when there is no token to check.
VALIDITY_NOT_CHECKED = "not_checked"
VALIDITY_VALID = "valid"
VALIDITY_INVALID = "invalid"
VALIDITY_UNREACHABLE = "unreachable"
VALIDITY_UNKNOWN = "unknown"

# The probe is a single lightweight GET; a short timeout keeps
# `campus auth status` snappy even when the server is down.
_PROBE_TIMEOUT = 10


def probe_token_validity(auth_url: str, token: str) -> tuple[str, str | None]:
    """Check whether an access token still authenticates (#45).

    Sends the cheapest authenticated request the auth server offers —
    GET /users/ — and classifies the response by status code alone:
    FORBIDDEN means the token is valid but not allowed to list users,
    UNAUTHORIZED means the token was rejected (see the module docstring
    for why raw requests are used instead of the client library).

    Args:
        auth_url: The auth endpoint the token is bound to.
        token: The access token to check.

    Returns:
        (validity, note): validity is one of VALIDITY_VALID,
        VALIDITY_INVALID, VALIDITY_UNREACHABLE or VALIDITY_UNKNOWN;
        note carries detail for the unreachable/unknown states and is
        None otherwise.
    """
    try:
        response = requests.get(
            f"{auth_url}/users/",
            headers={"Authorization": f"Bearer {token}"},
            timeout=_PROBE_TIMEOUT,
        )
    except requests.RequestException as e:
        # Note carries only the underlying error; the "could not reach
        # server" phrasing is supplied by whichever output renders it.
        return VALIDITY_UNREACHABLE, str(e)

    if response.status_code in (200, 403):
        # 403: authenticated, just lacking users:read — valid. A
        # users:read token gets 200 (the user list is discarded).
        return VALIDITY_VALID, None
    if response.status_code == 401:
        return VALIDITY_INVALID, None
    return VALIDITY_UNKNOWN, f"server returned HTTP {response.status_code}"


def _expires_in_seconds(expires_at: str | None) -> int | None:
    """Seconds until the stored expiry, negative once past.

    None when no expiry is recorded or the timestamp is unparseable
    (the raw string is still shown in the human output, matching the
    other auth commands' leniency).
    """
    if not expires_at:
        return None
    try:
        expiry_dt = datetime.fromisoformat(expires_at)
        if expiry_dt.tzinfo is None:
            expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
        remaining = expiry_dt - datetime.now(timezone.utc)
        return int(remaining.total_seconds())
    except (ValueError, TypeError):
        return None


def build_status(offline: bool) -> dict:
    """Assemble the full status payload from the credential store.

    Extends common.get_token_status (authenticated/expiry/endpoint
    fields, kept verbatim for --json backward compatibility) with the
    identity fields recorded at login (#45): client id, principal and
    scopes — plus the token check result unless offline.

    Args:
        offline: True skips the network validity check entirely.

    Returns:
        The status dict (see the command docstring for the schema).
    """
    token = get_token_status()
    creds = common.credentials
    authenticated: bool = token["authenticated"]
    user_id = creds.get_token_user_id() if authenticated else None
    scopes = creds.get_token_scopes() if authenticated else None

    status = {
        **token,
        "client_id": PUBLIC_OAUTH_CLIENT_ID,
        "user_id": user_id,
        # None means "not recorded" (credential predates #45 or no
        # token), never "no scopes": an empty list is a real answer.
        "scopes": scopes,
        "expires_in_seconds": (
            _expires_in_seconds(token["expires_at"]) if authenticated else None
        ),
    }

    if not authenticated:
        status.update(token_validity=None, probe_url=None, probe_note=None)
        return status

    if offline:
        status.update(
            token_validity=VALIDITY_NOT_CHECKED,
            probe_url=None,
            probe_note=None,
        )
        return status

    # Probe the endpoint the token is bound to — where it is actually
    # valid — mirroring logout's revoke-at-issuing-endpoint rule.
    # Unbound (pre-endpoint-binding) credentials fall back to the
    # current target.
    probe_url = token["token_auth_url"] or token["auth_url"]
    validity, note = probe_token_validity(probe_url, creds.get_token())
    status.update(token_validity=validity, probe_url=probe_url, probe_note=note)
    return status


def _print_validity_line(status: dict) -> None:
    """Print the human-readable token check result."""
    validity = status["token_validity"]
    if validity == VALIDITY_NOT_CHECKED:
        console.print("[dim]Token check: skipped (--offline)[/dim]")
        return
    if validity is None:
        return

    probe_url = status["probe_url"]
    where = f" against {probe_url}" if probe_url else ""
    if validity == VALIDITY_VALID:
        console.print(f"Token check{where}: [green]valid[/green]")
    elif validity == VALIDITY_INVALID:
        console.print(
            f"Token check{where}: [red bold]invalid[/red bold] — the server "
            "rejected the token. Run [bold]campus auth login[/bold] to "
            "re-authenticate."
        )
    elif validity == VALIDITY_UNREACHABLE:
        print_warning(
            f"Token check{where}: could not reach server "
            f"({status['probe_note']}) — validity unknown."
        )
    else:
        print_warning(
            f"Token check{where}: inconclusive "
            f"({status['probe_note']}) — validity unknown."
        )


def _print_expiry(status: dict) -> None:
    """Print the expiry block, matching the other auth commands' style."""
    expires_at = status["expires_at"]
    if not expires_at:
        console.print("[dim](No expiry information available)[/dim]")
        return
    try:
        expiry_dt = datetime.fromisoformat(expires_at)
        if expiry_dt.tzinfo is None:
            expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
        if status["is_expired"]:
            console.print("[red bold]Token has expired.[/red bold]")
        else:
            total = max(
                0, int((expiry_dt - datetime.now(timezone.utc)).total_seconds())
            )
            console.print(
                f"Token expires in: [cyan]"
                f"{total // 3600}h {total % 3600 // 60}m {total % 60}s"
                f"[/cyan]"
            )
        console.print(
            f"Expires at: {expiry_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
    except ValueError:
        console.print(f"Expires at: {expires_at}")


def _print_human(status: dict) -> None:
    """Render the status payload for a terminal."""
    if not status["authenticated"]:
        console.print("[yellow]Not authenticated[/yellow]")
        console.print(f"Auth endpoint: {status['auth_url']}")
        console.print("Run [bold]campus auth login[/bold] to authenticate.")
        return

    print_success("Authenticated")
    console.print(f"Client: {status['client_id']}")
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

    if status["user_id"]:
        console.print(f"Principal: {status['user_id']}")
    else:
        console.print(
            "[dim]Principal: unknown (not recorded; shown after next"
            " login)[/dim]"
        )

    scopes = status["scopes"]
    if scopes is None:
        console.print(
            "[dim]Scopes: unknown (not recorded; re-login to record"
            " this token's scopes)[/dim]"
        )
    elif scopes:
        console.print(f"Scopes: {', '.join(scopes)}")
    else:
        console.print("Scopes: (none)")

    _print_expiry(status)

    if status["can_refresh"]:
        console.print(
            "[dim]Refresh token: stored (campus auth refresh"
            " reissues the same scopes)[/dim]"
        )

    _print_validity_line(status)


def run_status(output_json: bool, offline: bool) -> None:
    """Entry point for the `campus auth status` command.

    Exits 1 when not logged in (both modes) or when the token check
    finds the stored token rejected; every other outcome — including
    an unreachable server or an inconclusive check — is non-fatal.
    """
    status = build_status(offline)

    if output_json:
        # Plain stdout write: Rich's word wrap can split long values
        # mid-string and corrupt machine-readable JSON.
        typer.echo(json.dumps(status))
    else:
        _print_human(status)

    if not status["authenticated"]:
        raise typer.Exit(1)
    if status["token_validity"] == VALIDITY_INVALID:
        raise typer.Exit(1)
