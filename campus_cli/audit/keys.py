"""campus.audit API key management (#54).

The operator workflow for minting and managing audit API keys, e.g.
one per student for dev-environment access: `owner_id` is an
email-format label (organizational only — campus.audit is user-blind
and self-contained by design), `scopes` gate what the key may call
(e.g. ["traces:read"]), and key management itself requires apikeys:*
scopes, held only by the operator key. Plaintext key material is
shown exactly once, at creation and at regeneration (mirroring the
server).
"""

from typing import Optional

import typer
from rich.console import Console

from campus_cli.audit.client import fail_api, get_audit_client
from campus_cli.auth.common import (
    confirm_destructive,
    dry_run_option,
)
from campus_cli.utils.output import (
    AUDIT_PYTHON_API_PREAMBLE,
    print_error,
    print_json,
    print_python_api,
    print_success,
)

keys_app = typer.Typer(help="Audit API key lifecycle (operator, apikeys:*)")
console = Console()

ApiKeyOption = typer.Option(..., "--key-id", help="API key ID (from keys list)")
OwnerOption = typer.Option(
    ...,
    "--owner",
    help=(
        "Owner label, conventionally the student email (organizational"
        " only — campus.audit is user-blind)"
    ),
)
ScopeOption = typer.Option(
    ...,
    "--scope",
    help=(
        "Scope the key grants, e.g. traces:read; repeat for multiple"
        " (the server requires at least one)"
    ),
)


def _print_reveal_key(key_value: str) -> None:
    """Print plaintext key material exactly once, unwrapped.

    Plain stdout write: Rich's word wrap can split long tokens
    mid-string, which would corrupt a copy-pasted key.
    """
    console.print("[dim]-------8<------- (copy now)[/dim]")
    typer.echo(key_value)
    console.print("[dim]-------8<-------[/dim]")


def _print_key_record(record: dict) -> None:
    """Print one API key record in human-readable form."""
    status = "[green]active[/green]"
    if record.get("revoked_at"):
        status = "[red]revoked[/red]"
    elif record.get("expires_at"):
        status = "[yellow]expires[/yellow]"
    console.print(f"[cyan]{record.get('name')}[/cyan] [dim]{record.get('id')}[/dim]")
    console.print(
        f"  Owner: {record.get('owner_id')}  Status: {status}"
        f"  Scopes: {' '.join(record.get('scopes') or []) or '(none)'}"
    )
    extras = []
    if record.get("rate_limit") is not None:
        extras.append(f"rate limit {record['rate_limit']}/min")
    if record.get("expires_at"):
        extras.append(f"expires {record['expires_at']}")
    if record.get("revoked_at"):
        extras.append(f"revoked {record['revoked_at']}")
    if extras:
        console.print(f"  [dim]{'; '.join(extras)}[/dim]")
    console.print()


@keys_app.command("list")
def keys_list(
    owner: Optional[str] = typer.Option(None, "--owner", help="Filter by owner"),
    include_inactive: bool = typer.Option(
        False,
        "--all",
        help="Include revoked and expired keys (default: active only)",
    ),
    limit: Optional[int] = typer.Option(None, "--limit", help="Page size"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    List audit API keys, optionally filtered by owner.

    Requires apikeys:read on the stored key (the operator key).
    """
    if dry_run:
        print_python_api(
            "campus audit keys list",
            [
                "result = campus_audit.apikeys.list(",
                f"    owner_id={owner!r},",
                f"    active_only={not include_inactive!r},",
                f"    limit={limit!r},",
                ")",
                "for key in result['api_keys']:",
                "    print(key['id'], key['name'], key['scopes'])",
            ],
            preamble=AUDIT_PYTHON_API_PREAMBLE,
        )
        return

    try:
        api = get_audit_client()
        result = api.apikeys.list(
            owner_id=owner, active_only=not include_inactive, limit=limit
        )
        keys = result.get("api_keys", [])

        if output_json:
            print_json(keys)
        else:
            if not keys:
                console.print("[dim]No API keys found.[/dim]")
                return
            console.print(f"[bold]Found {len(keys)} API key(s):[/bold]\n")
            for record in keys:
                _print_key_record(record)

    except typer.Exit:
        raise
    except Exception as e:
        fail_api("list API keys", e)


@keys_app.command("new")
def keys_new(
    name: str = typer.Option(..., "--name", help="Key name, e.g. the student's name"),
    owner: str = OwnerOption,
    scope: list[str] = ScopeOption,  # noqa: B008
    rate_limit: Optional[int] = typer.Option(
        None, "--rate-limit", help="Requests per minute (optional)"
    ),
    expires_at: Optional[str] = typer.Option(
        None, "--expires-at", help="ISO 8601 expiry (optional)"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    Create an audit API key (mint a student key).

    The plaintext key is shown exactly once, at creation — the server
    keeps only its hash. Pass it to the student; they store it with
    'campus audit login --api-key'.
    """
    if dry_run:
        new_kwargs = [
            f"    name={name!r},",
            f"    owner_id={owner!r},",
            f"    scopes={list(scope)!r},",
        ]
        if rate_limit is not None:
            new_kwargs.append(f"    rate_limit={rate_limit!r},")
        if expires_at is not None:
            new_kwargs.append(f"    expires_at={expires_at!r},")
        print_python_api(
            "campus audit keys new",
            [
                "record = campus_audit.apikeys.new(",
                *new_kwargs,
                ")",
                "print(record['api_key'])  # shown only here",
            ],
            preamble=AUDIT_PYTHON_API_PREAMBLE,
        )
        return

    try:
        api = get_audit_client()
        record = api.apikeys.new(
            name=name,
            owner_id=owner,
            scopes=list(scope),
            rate_limit=rate_limit,
            expires_at=expires_at,
        )

        if output_json:
            print_json(record)
        else:
            print_success(
                "API key created. The plaintext value is shown only here —"
                " copy it now:"
            )
            _print_reveal_key(record.get("api_key", ""))
            console.print("[dim]Key record:[/dim]")
            _print_key_record(record)

    except typer.Exit:
        raise
    except Exception as e:
        fail_api("create API key", e)


@keys_app.command("get")
def keys_get(
    key_id: str = ApiKeyOption,
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Show one audit API key's record (never its plaintext)."""
    if dry_run:
        print_python_api(
            "campus audit keys get",
            [f"record = campus_audit.apikeys[{key_id!r}].get()", "print(record)"],
            preamble=AUDIT_PYTHON_API_PREAMBLE,
        )
        return

    try:
        api = get_audit_client()
        record = api.apikeys[key_id].get()

        if output_json:
            print_json(record)
        else:
            _print_key_record(record)

    except typer.Exit:
        raise
    except Exception as e:
        fail_api(f"get API key '{key_id}'", e)


@keys_app.command("update")
def keys_update(
    key_id: str = ApiKeyOption,
    name: Optional[str] = typer.Option(None, "--name", help="New key name"),
    scope: Optional[list[str]] = typer.Option(  # noqa: B008
        None,
        "--scope",
        help=(
            "Replacement scope set; repeat for multiple. Omit to keep"
            " the current scopes"
        ),
    ),
    rate_limit: Optional[int] = typer.Option(
        None, "--rate-limit", help="Requests per minute"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    Update an audit API key's name, scopes, or rate limit.

    Only the fields passed are changed. Expiry and revocation are
    immutable — mint a fresh key instead.
    """
    if name is None and scope is None and rate_limit is None:
        print_error(
            "Nothing to update: pass --name, --scope, or --rate-limit."
        )
        raise typer.Exit(1)

    if dry_run:
        update_kwargs = []
        if name is not None:
            update_kwargs.append(f"    name={name!r},")
        if scope is not None:
            update_kwargs.append(f"    scopes={list(scope)!r},")
        if rate_limit is not None:
            update_kwargs.append(f"    rate_limit={rate_limit!r},")
        print_python_api(
            "campus audit keys update",
            [
                f"record = campus_audit.apikeys[{key_id!r}].update(",
                *update_kwargs,
                ")",
                "print(record)",
            ],
            preamble=AUDIT_PYTHON_API_PREAMBLE,
        )
        return

    try:
        api = get_audit_client()
        record = api.apikeys[key_id].update(
            name=name,
            scopes=list(scope) if scope is not None else None,
            rate_limit=rate_limit,
        )

        if output_json:
            print_json(record)
        else:
            print_success("API key updated.")
            _print_key_record(record)

    except typer.Exit:
        raise
    except Exception as e:
        fail_api(f"update API key '{key_id}'", e)


@keys_app.command("revoke")
def keys_revoke(
    key_id: str = ApiKeyOption,
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation"),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    Revoke an audit API key (the record is kept for audit).

    The key stops authenticating immediately; its record stays listed
    under --all for the audit trail.
    """
    if dry_run:
        print_python_api(
            "campus audit keys revoke",
            [f"campus_audit.apikeys[{key_id!r}].revoke()"],
            preamble=AUDIT_PYTHON_API_PREAMBLE,
        )
        return

    confirm_destructive(f"revoke audit API key '{key_id}'", confirm)

    try:
        api = get_audit_client()
        api.apikeys[key_id].revoke()
        print_success(f"API key '{key_id}' revoked (record kept for audit).")

    except typer.Exit:
        raise
    except Exception as e:
        fail_api(f"revoke API key '{key_id}'", e)


@keys_app.command("regenerate")
def keys_regenerate(
    key_id: str = ApiKeyOption,
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    Replace an audit API key's plaintext value (rotation).

    The old value stops working immediately; the new one is shown
    exactly once here. Scopes, rate limit, and expiry carry over.
    """
    if dry_run:
        print_python_api(
            "campus audit keys regenerate",
            [
                f"key = campus_audit.apikeys[{key_id!r}].regenerate()",
                "print(key)  # shown only here",
            ],
            preamble=AUDIT_PYTHON_API_PREAMBLE,
        )
        return

    confirm_destructive(
        f"regenerate audit API key '{key_id}' (the old value stops"
        " working immediately)",
        confirm,
    )

    try:
        api = get_audit_client()
        key_value = api.apikeys[key_id].regenerate()

        if output_json:
            print_json({"id": key_id, "api_key": key_value})
        else:
            print_success(
                "API key regenerated. The new plaintext value is shown only"
                " here — copy it now:"
            )
            _print_reveal_key(key_value)

    except typer.Exit:
        raise
    except Exception as e:
        fail_api(f"regenerate API key '{key_id}'", e)
