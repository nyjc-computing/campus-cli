"""Authentication commands for Campus CLI."""

from campus_cli.auth.client import client_app
from campus_cli.auth.login import login_app
from campus_cli.auth.vault import vault_app

__all__ = ["client_app", "login_app", "vault_app"]
