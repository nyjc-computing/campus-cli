"""Access-grant store commands (#50).

The grant matrix (#883) lives server-side in `/auth/v1/grants/`: rows
keyed by (grantee_type, grantee_id, resource_type[, resource_id])
holding either a management level (read < mod < write < admin) or
vault bitflags (1=READ, 2=CREATE, 4=UPDATE, 8=DELETE). A user
principal's management authority is grant row AND token scope; the
env-nominated super-admin root needs neither.

Administration authority: the operator, a same-vocabulary admin, or
the root. Anti-escalation: no principal administers its own grants,
and vocabulary-level `clients:admin` rows are rejected
(operator-equivalent).
"""

import typer
from rich.console import Console

from campus_cli.auth.common import (
    confirm_destructive,
    dry_run_option,
    get_api_client,
)
from campus_cli.utils.output import (
    print_error,
    print_json,
    print_python_api,
    print_success,
)

grants_app = typer.Typer(help="Access-grant store commands (who can do what)")
console = Console()

# Vault bitflag names (campus.model.client.ClientAccess ordering, as
# documented by the client access commands).
_BITFLAG_NAMES = {1: "READ", 2: "CREATE", 4: "UPDATE", 8: "DELETE"}


def _format_access(row: dict) -> str:
    """Render a grant row's permission as `resource:level` or bitflags."""
    resource = row.get("resource_type", "?")
    if row.get("resource_id"):
        resource = f"{resource} {row['resource_id']}"
    if row.get("level"):
        return f"{resource}:{row['level']}"
    bits = row.get("bits") or 0
    names = [name for bit, name in _BITFLAG_NAMES.items() if bits & bit]
    return f"{resource}: {', '.join(names) if names else str(bits)}"


def _format_grant(row: dict) -> dict:
    """Format a grant row for output.

    Args:
        row: The server's AccessGrant resource (plain dict)

    Returns:
        Dict representation with a human-readable access summary
    """
    return {
        "id": row.get("id"),
        "grantee": f"{row.get('grantee_type')}: {row.get('grantee_id')}",
        "access": _format_access(row),
        "created_at": row.get("created_at"),
    }


def _print_grant_rows(rows: list[dict]) -> None:
    """Print grant rows grouped by grantee."""
    if not rows:
        console.print("[dim]No grant rows found.[/dim]")
        return
    console.print(f"[bold]Found {len(rows)} grant row(s):[/bold]\n")
    for row in rows:
        formatted = _format_grant(row)
        console.print(f"[cyan]{formatted['grantee']}[/cyan]")
        console.print(f"  Access: {formatted['access']}")
        console.print(f"  [dim]{formatted['id']}[/dim]")
        console.print()


def _validate_level_bits(level: str | None, bits: int | None) -> None:
    """Require exactly one of --level / --bits.

    Args:
        level: Management level option value
        bits: Vault bitflag option value

    Raises:
        typer.Exit: When neither or both are provided.
    """
    if (level is None) == (bits is None):
        print_error(
            "Provide exactly one of --level (management vocabularies:"
            " read/mod/write/admin) or --bits (vault bitflags:"
            " 1=READ, 2=CREATE, 4=UPDATE, 8=DELETE; combine by summing)."
        )
        raise typer.Exit(1)


GranteeType = typer.Option(
    ..., "--grantee-type", "-t", help="Grantee principal type: user or client"
)
GranteeId = typer.Option(..., "--grantee-id", "-g", help="User email or client ID")
ResourceType = typer.Option(
    ...,
    "--resource-type",
    "-r",
    help="Vocabulary: users, clients, or vault (per-label)",
)
ResourceId = typer.Option(
    "", "--resource-id", help="Instance for per-label resources (vault label)"
)


@grants_app.command("list")
def grants_list(
    grantee_type: str | None = typer.Option(None, "--grantee-type", "-t"),
    grantee_id: str | None = typer.Option(None, "--grantee-id", "-g"),
    resource_type: str | None = typer.Option(None, "--resource-type", "-r"),
    resource_id: str | None = typer.Option(None, "--resource-id"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    List access-grant rows — the "who can administer what" matrix.

    Without filters this is operator/root-only; user principals may
    list the single vocabulary they administer. Filter to keep the
    answer small.
    """
    if dry_run:
        print_python_api(
            "campus grant list",
            [
                "result = campus.auth.grants.list()",
                "for row in result['grants']:",
                "    print(row['grantee_id'], row['resource_type'], row['level'])",
            ],
        )
        return

    try:
        api = get_api_client()
        result = api.auth_grants.list(
            grantee_type=grantee_type,
            grantee_id=grantee_id,
            resource_type=resource_type,
            resource_id=resource_id or None,
        )
        rows = result.get("grants", [])

        if output_json:
            print_json(rows)
        else:
            _print_grant_rows(rows)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to list grants: {e}")
        raise typer.Exit(1) from e


@grants_app.command("check")
def grants_check(
    grantee_type: str = GranteeType,
    grantee_id: str = GranteeId,
    resource_type: str = ResourceType,
    resource_id: str = ResourceId,
    level: str | None = typer.Option(None, "--level", help="Management level to test"),
    bits: int | None = typer.Option(
        None, "--bits", help="Vault bitflag mask to test"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    Check whether a grant row covers a permission.

    Requires operator or same-vocabulary admin authority.
    """
    _validate_level_bits(level, bits)

    if dry_run:
        print_python_api(
            "campus grant check",
            [
                "granted = campus.auth.grants.check(",
                f"    grantee_type={grantee_type!r},",
                f"    grantee_id={grantee_id!r},",
                f"    resource_type={resource_type!r},",
                f"    resource_id={resource_id!r},",
                f"    level={level!r}, bits={bits!r},",
                ")",
                "print(granted)",
            ],
        )
        return

    try:
        api = get_api_client()
        granted = api.auth_grants.check(
            grantee_type=grantee_type,
            grantee_id=grantee_id,
            resource_type=resource_type,
            resource_id=resource_id,
            bits=bits,
            level=level,
        )

        if output_json:
            print_json({"granted": granted})
        else:
            state = "[green]granted[/green]" if granted else "[red]not granted[/red]"
            access = _format_access(
                {
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "level": level,
                    "bits": bits,
                }
            )
            console.print(f"{grantee_type} {grantee_id} → {access}: {state}")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to check grant: {e}")
        raise typer.Exit(1) from e


@grants_app.command("grant")
def grants_grant(
    grantee_type: str = GranteeType,
    grantee_id: str = GranteeId,
    resource_type: str = ResourceType,
    resource_id: str = ResourceId,
    level: str | None = typer.Option(
        None, "--level", help="Management level: read/mod/write/admin"
    ),
    bits: int | None = typer.Option(
        None, "--bits", help="Vault bitflag mask (1=READ, 2=CREATE, 4=UPDATE, 8=DELETE;"
        " sum to combine). Vault bits OR into the existing mask"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    Grant access (create a row, or raise an existing one).

    Management levels never downgrade: revoke first to lower a level.
    Anti-escalation: no principal may administer its own grants, and
    vocabulary-level clients:admin rows are rejected
    (operator-equivalent — authority over client registration stays
    with the operator and the root).
    """
    _validate_level_bits(level, bits)
    if resource_type == "vault" and not resource_id:
        print_error("Vault grant rows must name their label (--resource-id).")
        raise typer.Exit(1)

    if dry_run:
        print_python_api(
            "campus grant grant",
            [
                "row = campus.auth.grants.grant(",
                f"    grantee_type={grantee_type!r},",
                f"    grantee_id={grantee_id!r},",
                f"    resource_type={resource_type!r},",
                f"    resource_id={resource_id!r},",
                f"    level={level!r}, bits={bits!r},",
                ")",
                "print(row)",
            ],
        )
        return

    try:
        api = get_api_client()
        row = api.auth_grants.grant(
            grantee_type=grantee_type,
            grantee_id=grantee_id,
            resource_type=resource_type,
            resource_id=resource_id,
            bits=bits,
            level=level,
        )

        if output_json:
            print_json(row)
        else:
            print_success("Grant created successfully!")
            print_json(row)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to create grant: {e}")
        raise typer.Exit(1) from e


@grants_app.command("revoke")
def grants_revoke(
    grantee_type: str = GranteeType,
    grantee_id: str = GranteeId,
    resource_type: str = ResourceType,
    resource_id: str = ResourceId,
    level: str | None = typer.Option(
        None, "--level", help="Management level to revoke"
    ),
    bits: int | None = typer.Option(
        None, "--bits", help="Vault bitflags to clear"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation"),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    Revoke access (clear vault bits, delete covered levels).

    Vault rows delete at zero bits; a revoked level's row is deleted
    when the held level covers it. The remaining row (or null) is
    printed.
    """
    _validate_level_bits(level, bits)

    if dry_run:
        print_python_api(
            "campus grant revoke",
            [
                "row = campus.auth.grants.revoke(",
                f"    grantee_type={grantee_type!r},",
                f"    grantee_id={grantee_id!r},",
                f"    resource_type={resource_type!r},",
                f"    resource_id={resource_id!r},",
                f"    level={level!r}, bits={bits!r},",
                ")",
                "print(row)",
            ],
        )
        return

    target = _format_access(
        {
            "resource_type": resource_type,
            "resource_id": resource_id,
            "level": level,
            "bits": bits,
        }
    )
    confirm_destructive(f"revoke {target} from {grantee_type} {grantee_id}", confirm)

    try:
        api = get_api_client()
        row = api.auth_grants.revoke(
            grantee_type=grantee_type,
            grantee_id=grantee_id,
            resource_type=resource_type,
            resource_id=resource_id,
            bits=bits,
            level=level,
        )

        if output_json:
            print_json(row)
        elif row:
            print_success("Revoked; remaining row:")
            print_json(row)
        else:
            print_success("Revoked; the grant row was deleted.")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to revoke grant: {e}")
        raise typer.Exit(1) from e


@grants_app.command("delete")
def grants_delete(
    grant_id: str = typer.Option(..., "--grant-id", help="Grant row ID (from list)"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation"),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    Delete a grant row outright.

    Prefer 'campus grant revoke' for partial revocation: this removes
    the whole row.
    """
    if dry_run:
        print_python_api(
            "campus grant delete",
            [f"campus.auth.grants.delete({grant_id!r})"],
        )
        return

    confirm_destructive(f"delete grant row '{grant_id}'", confirm)

    try:
        api = get_api_client()
        api.auth_grants.delete(grant_id)
        print_success(f"Grant row '{grant_id}' deleted.")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to delete grant: {e}")
        raise typer.Exit(1) from e
