"""Shared utilities for auth commands."""

import typer

from campus_cli.credentials import credentials
from campus_cli.utils.output import print_error


def get_api_client():
    """
    Get an authenticated API client.

    Returns:
        An authenticated campus API client.

    Raises:
        typer.Exit: If authentication fails.
    """
    token = credentials.get_token()
    if not token:
        print_error("Not authenticated. Run 'campus auth login' first.")
        raise typer.Exit(1)

    try:
        from campus_api import CampusClient

        return CampusClient(token=token)
    except ImportError:
        print_error("campus-api-python library not available.")
        raise typer.Exit(1) from None
