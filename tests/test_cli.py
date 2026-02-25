"""Test CLI command registration."""

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


def test_auth_status_not_authenticated():
    """Test auth status when not logged in."""
    result = runner.invoke(app, ["auth", "status"])

    assert result.exit_code == 0
    assert "Not authenticated" in result.stdout


def test_auth_status_json_format():
    """Test auth status outputs valid JSON when requested."""
    result = runner.invoke(app, ["auth", "status", "--json"])

    assert result.exit_code == 0
    assert '"authenticated":' in result.stdout
