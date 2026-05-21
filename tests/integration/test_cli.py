"""Integration tests for CLI commands.

These tests test CLI commands with mocked dependencies for isolation.
"""

from unittest.mock import patch

from typer.testing import CliRunner

from campus_cli.cli import app

runner = CliRunner()


def test_cli_version():
    """Test version command returns correct output."""
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert "campus-cli" in result.stdout
    assert "0.1.0" in result.stdout


def test_cli_help():
    """Test help command displays all top-level commands."""
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "auth" in result.stdout
    assert "client" in result.stdout
    assert "vault" in result.stdout
    assert "version" in result.stdout


def test_auth_help():
    """Test auth subcommand displays all auth commands."""
    result = runner.invoke(app, ["auth", "--help"])

    assert result.exit_code == 0
    assert "login" in result.stdout
    assert "logout" in result.stdout
    assert "status" in result.stdout


def test_auth_status_not_authenticated():
    """Test auth status when not logged in."""
    # Mock credentials to ensure no token is stored (isolated test)
    with patch("campus_cli.auth.common.credentials") as mock_creds:
        mock_creds.get_token.return_value = None
        mock_creds.get_refresh_token.return_value = None
        mock_creds.get_token_expires_at.return_value = None

        result = runner.invoke(app, ["auth", "status"])

        assert result.exit_code == 0
        assert "Not authenticated" in result.stdout


def test_auth_status_json_format():
    """Test auth status outputs valid JSON when requested."""
    # Mock credentials to ensure no token is stored (isolated test)
    with patch("campus_cli.auth.common.credentials") as mock_creds:
        mock_creds.get_token.return_value = None
        mock_creds.get_refresh_token.return_value = None
        mock_creds.get_token_expires_at.return_value = None

        result = runner.invoke(app, ["auth", "status", "--json"])

        assert result.exit_code == 0
        assert '"authenticated":' in result.stdout


def test_client_help():
    """Test client subcommand displays all client commands."""
    result = runner.invoke(app, ["client", "--help"])

    assert result.exit_code == 0
    assert "new" in result.stdout
    assert "get" in result.stdout
    assert "update" in result.stdout
    assert "delete" in result.stdout
    assert "revoke" in result.stdout


def test_vault_help():
    """Test vault subcommand displays all vault commands."""
    result = runner.invoke(app, ["vault", "--help"])

    assert result.exit_code == 0
    assert "list" in result.stdout
    assert "get" in result.stdout
    assert "set" in result.stdout
    assert "delete" in result.stdout


def test_auth_status_authenticated():
    """Test auth status when authenticated."""
    # Mock credentials to simulate authenticated state
    with patch("campus_cli.auth.common.credentials") as mock_creds:
        mock_creds.get_token.return_value = "test_access_token"
        mock_creds.get_refresh_token.return_value = "test_refresh_token"
        mock_creds.get_token_expires_at.return_value = "2024-12-31T23:59:59+00:00"
        mock_creds.is_token_expired.return_value = False

        result = runner.invoke(app, ["auth", "status"])

        assert result.exit_code == 0
        assert "Authenticated" in result.stdout
