"""Subjcombi commands (campus#592): user→lessongroup mappings.

Changes append effective-dated records server-side — the records are
the mutation trail — and scheduled changes take effect at their
effective_from (date-only values apply at 07:00 school time) without
any scheduler. Mutations require the subjcombi.admin role circle.
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
    print_table,
)

subjcombi_app = typer.Typer(
    help="Subjcombi commands: user→lessongroup mappings (campus.api)"
)
console = Console()


@subjcombi_app.command("set")
def subjcombi_set(
    user_id: str = typer.Option(
        ..., "--user-id", help="The user's campus account email"
    ),
    lessongroup_id: str = typer.Option(
        ..., "--lessongroup-id", help="The lessongroup to map to"
    ),
    effective_from: str = typer.Option(
        None, "--effective-from",
        help="When it applies (ISO datetime, or YYYY-MM-DD for"
        " 07:00 school time); absent = immediate",
    ),
    reason: str = typer.Option(
        None, "--reason", help="Optional change note for the trail"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Set the user's mapping (appends a trail record)."""
    if dry_run:
        body = f"lessongroup_id={lessongroup_id!r}"
        if effective_from is not None:
            body += f", effective_from={effective_from!r}"
        if reason is not None:
            body += f", reason={reason!r}"
        print_python_api(
            "campus subjcombi set",
            [
                "record = campus.api.subjcombi.set(",
                f"    {user_id!r},",
                f"    {body},",
                ")",
                "print(record)",
            ],
        )
        return

    when = effective_from or "immediately"
    confirm_destructive(
        f"map user '{user_id}' to lessongroup '{lessongroup_id}'"
        f" (effective {when})", confirm
    )

    try:
        api = get_api_client()
        record = api.api_subjcombi.set(
            user_id,
            lessongroup_id,
            effective_from=effective_from,
            reason=reason,
        )

        if output_json:
            print_json(record)
        else:
            print_success(
                f"Mapping recorded: '{user_id}' -> '{lessongroup_id}'"
                f" (effective {record.get('effective_from')})."
            )
            print_json(record)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to set the mapping: {e}")
        raise typer.Exit(1) from e


@subjcombi_app.command("get")
def subjcombi_get(
    user_id: str = typer.Option(
        ..., "--user-id", help="The user's campus account email"
    ),
    at: str = typer.Option(
        None, "--at", help="Resolve the mapping as of this datetime"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Show the user's effective mapping (mapping, roster, or unmapped)."""
    if dry_run:
        call = (
            f"campus.api.subjcombi[{user_id!r}].get(at={at!r})"
            if at else f"campus.api.subjcombi[{user_id!r}].get()"
        )
        print_python_api("campus subjcombi get", [f"print({call})"])
        return

    try:
        api = get_api_client()
        view = (
            api.api_subjcombi[user_id].get(at=at)
            if at
            else api.api_subjcombi[user_id].get()
        )

        if output_json:
            print_json(view)
        else:
            console.print(
                f"[bold]{user_id}[/bold] -> "
                f"{view.get('lessongroup_id') or 'unmapped'}"
                f" (via {view.get('source')})"
            )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to get the mapping for '{user_id}': {e}")
        raise typer.Exit(1) from e


@subjcombi_app.command("history")
def subjcombi_history(
    user_id: str = typer.Option(
        ..., "--user-id", help="The user's campus account email"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Show the user's full mutation trail (newest first)."""
    if dry_run:
        print_python_api(
            "campus subjcombi history",
            [
                "records = campus.api.subjcombi["
                f"{user_id!r}].history()",
                "for r in records:",
                "    print(r['effective_from'], r['lessongroup_id'],"
                " r['actor_id'])",
            ],
        )
        return

    try:
        api = get_api_client()
        records = api.api_subjcombi[user_id].history()

        if output_json:
            print_json(records)
        elif not records:
            console.print("[dim]No mapping records.[/dim]")
        else:
            console.print(f"[bold]{len(records)} record(s):[/bold]\n")
            print_table(
                headers=["Effective", "Group", "Previous", "Actor", "Status"],
                rows=[
                    [
                        str(r.get("effective_from")),
                        str(r.get("lessongroup_id")),
                        str(r.get("previous_lessongroup_id") or "-"),
                        str(r.get("actor_id")),
                        (
                            "cancelled"
                            if r.get("cancelled_at")
                            else ("superseded" if r.get("superseded_by") else "active")
                        ),
                    ]
                    for r in records
                ],
            )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to get the history for '{user_id}': {e}")
        raise typer.Exit(1) from e


@subjcombi_app.command("pending")
def subjcombi_pending(
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """List scheduled mappings not yet effective (soonest first)."""
    if dry_run:
        print_python_api(
            "campus subjcombi pending",
            [
                "records = campus.api.subjcombi.pending()",
                "for r in records:",
                "    print(r['effective_from'], r['user_id'],"
                " r['lessongroup_id'])",
            ],
        )
        return

    try:
        api = get_api_client()
        records = api.api_subjcombi.pending()

        if output_json:
            print_json(records)
        elif not records:
            console.print("[dim]Nothing is pending.[/dim]")
        else:
            console.print(f"[bold]{len(records)} pending record(s):[/bold]\n")
            print_table(
                headers=["Effective", "User", "Group"],
                rows=[
                    [
                        str(r.get("effective_from")),
                        str(r.get("user_id")),
                        str(r.get("lessongroup_id")),
                    ]
                    for r in records
                ],
            )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to list pending mappings: {e}")
        raise typer.Exit(1) from e


@subjcombi_app.command("cancel")
def subjcombi_cancel(
    record_id: str = typer.Option(
        ..., "--record-id", help="The subjcombi record to cancel"
    ),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Cancel a pending scheduled mapping (409 once it is effective)."""
    if dry_run:
        print_python_api(
            "campus subjcombi cancel",
            [f"campus.api.subjcombi.cancel({record_id!r})"],
        )
        return

    confirm_destructive(f"cancel scheduled mapping '{record_id}'", confirm)

    try:
        api = get_api_client()
        record = api.api_subjcombi.cancel(record_id)
        print_success(f"Cancelled '{record_id}'.")
        print_json(record)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to cancel '{record_id}': {e}")
        raise typer.Exit(1) from e
