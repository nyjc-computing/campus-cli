"""Campus CLI - Command-line interface for Campus API."""

import typer
from rich.console import Console

app = typer.Typer(
    name="campus",
    help="Campus CLI - Command-line interface for Campus API",
    no_args_is_help=True,
)

console = Console()


@app.callback()
def callback(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
) -> None:
    """Campus CLI - Command-line interface for Campus API."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


@app.command()
def version() -> None:
    """Show the version information."""
    from campus_cli import __version__

    console.print(f"campus-cli version [bold green]{__version__}[/bold green]")


# Import auth commands
# noqa: E402 - Imported here to avoid circular dependencies
from campus_cli.audit import audit_app  # noqa: E402
from campus_cli.auth import (  # noqa: E402
    client_app,
    grants_app,
    login_app,
    user_app,
    vault_app,
)
from campus_cli.resources import (  # noqa: E402
    app_app,
    assignment_app,
    circle_app,
    file_app,
    submission_app,
    timetable_app,
)

# Register sub-apps
app.add_typer(login_app, name="auth", help="Authentication commands")
app.add_typer(client_app, name="client", help="OAuth client management commands")
app.add_typer(user_app, name="user", help="User management commands")
app.add_typer(grants_app, name="grant", help="Access-grant store commands")
app.add_typer(vault_app, name="vault", help="Vault management commands")
app.add_typer(audit_app, name="audit", help="Campus Audit service commands")
app.add_typer(
    assignment_app, name="assignment", help="Assignment commands (campus.api)"
)
app.add_typer(
    submission_app, name="submission", help="Submission commands (campus.api)"
)
app.add_typer(
    timetable_app, name="timetable", help="Timetable commands (campus.api)"
)
app.add_typer(circle_app, name="circle", help="Circle commands (campus.api)")
app.add_typer(
    file_app, name="file", help="File storage commands (campus.api)"
)
app.add_typer(
    app_app, name="app", help="Hosted-app publishing commands (campus.api)"
)


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
