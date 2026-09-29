"""Integration tests for CLI commands.

These tests test CLI commands with mocked dependencies for isolation.
"""

from unittest.mock import Mock, patch

from typer.testing import CliRunner

from campus_cli.cli import app

runner = CliRunner()


def _mock_client(**overrides):
    """Build a mock Client model for API responses."""
    client = Mock(
        id="uid-client-test1234",
        name="Test Client",
        description="A test client",
        created_at=None,
        permissions={},
        is_public=False,
        redirect_uris=[],
    )
    for key, value in overrides.items():
        setattr(client, key, value)
    return client


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


def test_auth_logout_with_token():
    """Test logout clears stored credentials and reports success."""
    with patch("campus_cli.auth.login.credentials") as mock_creds:
        mock_creds.get_token.return_value = "test_access_token"

        result = runner.invoke(app, ["auth", "logout"])

        assert result.exit_code == 0
        assert "Logged out successfully" in result.stdout
        mock_creds.delete_token.assert_called_once()
        mock_creds.delete_refresh_token.assert_called_once()


def test_auth_logout_not_authenticated():
    """Test logout is a friendly no-op when no token is stored."""
    with patch("campus_cli.auth.login.credentials") as mock_creds:
        mock_creds.get_token.return_value = None

        result = runner.invoke(app, ["auth", "logout"])

        assert result.exit_code == 0
        assert "Not logged in" in result.stdout
        mock_creds.delete_token.assert_not_called()
        # A stray refresh token without an access token is still cleared
        mock_creds.delete_refresh_token.assert_called_once()


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


def test_client_new_confidential():
    """client new without --public creates a confidential client unchanged."""
    with patch("campus_cli.auth.client.get_api_client") as mock_get:
        mock_get.return_value.auth_clients.new.return_value = _mock_client()

        result = runner.invoke(
            app, ["client", "new", "--name", "Test", "--description", "D"]
        )

        assert result.exit_code == 0
        mock_get.return_value.auth_clients.new.assert_called_once_with(
            name="Test", description="D", is_public=False, redirect_uris=None
        )
        assert "created successfully" in result.stdout
        assert "client revoke" in result.stdout


def test_client_new_public():
    """--public creates a public client and drops the secret note."""
    with patch("campus_cli.auth.client.get_api_client") as mock_get:
        client = _mock_client(is_public=True, redirect_uris=["https://a/cb"])
        mock_get.return_value.auth_clients.new.return_value = client

        result = runner.invoke(
            app,
            [
                "client", "new", "--name", "Test", "--description", "D",
                "--public", "--redirect-uri", "https://a/cb",
            ],
        )

        assert result.exit_code == 0
        mock_get.return_value.auth_clients.new.assert_called_once_with(
            name="Test",
            description="D",
            is_public=True,
            redirect_uris=["https://a/cb"],
        )
        assert "created successfully" in result.stdout
        assert "Public client" in result.stdout
        assert "client revoke" not in result.stdout


def test_client_new_redirect_uri_repeatable():
    """--redirect-uri can be passed multiple times, forwarded verbatim."""
    with patch("campus_cli.auth.client.get_api_client") as mock_get:
        mock_get.return_value.auth_clients.new.return_value = _mock_client(
            redirect_uris=["https://a/cb", "https://b/cb"]
        )

        result = runner.invoke(
            app,
            [
                "client", "new", "--name", "Test", "--description", "D",
                "--redirect-uri", "https://a/cb",
                "--redirect-uri", "https://b/cb",
            ],
        )

        assert result.exit_code == 0
        _, kwargs = mock_get.return_value.auth_clients.new.call_args
        assert kwargs["redirect_uris"] == ["https://a/cb", "https://b/cb"]
        assert kwargs["is_public"] is False


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
