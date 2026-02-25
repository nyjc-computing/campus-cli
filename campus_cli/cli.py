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
    api_endpoint: str | None = typer.Option(
        None,
        "--api-endpoint",
        "-e",
        help="Override the default API endpoint",
    ),
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

    if api_endpoint:
        ctx.obj["api_endpoint"] = api_endpoint


@app.command()
def version() -> None:
    """Show the version information."""
    from campus_cli import __version__

    console.print(f"campus-cli version [bold green]{__version__}[/bold green]")


# Import auth commands
from campus_cli.auth import (
    client_app,
    login_app,
    vault_app,
)

# Register sub-apps
app.add_typer(login_app, name="auth", help="Authentication commands")
app.add_typer(client_app, name="client", help="OAuth client management commands")
app.add_typer(vault_app, name="vault", help="Vault management commands")


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
