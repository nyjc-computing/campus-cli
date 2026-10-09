"""Integration tests for CLI commands.

These tests test CLI commands with mocked dependencies for isolation.
"""

from json import loads as json_loads
from unittest.mock import ANY, Mock, patch

from typer.testing import CliRunner

from campus_cli.auth.login import DeviceAuthError
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
        allowed_scopes=[],
        upstream_scopes={},
        token_bridge=False,
    )
    # `name` as a Mock kwarg names the mock itself; the attribute needs
    # setting explicitly or .name is a child Mock (breaks JSON output).
    client.name = "Test Client"
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
        mock_creds.get_token_auth_url.return_value = None

        result = runner.invoke(app, ["auth", "status"])

        assert result.exit_code == 0
        assert "Not authenticated" in result.stdout


def test_auth_logout_with_token():
    """Test logout revokes tokens server-side and clears stored credentials."""
    with (
        patch("campus_cli.auth.login.credentials") as mock_creds,
        patch(
            "campus_cli.auth.login.revoke_token", return_value=True
        ) as mock_revoke,
    ):
        mock_creds.get_token.return_value = "test_access_token"
        mock_creds.get_refresh_token.return_value = "test_refresh_token"
        mock_creds.get_token_auth_url.return_value = (
            "https://auth-minted.example.com/auth/v1"
        )

        result = runner.invoke(app, ["auth", "logout", "-y"])

        assert result.exit_code == 0
        assert "Logged out successfully" in result.stdout
        assert mock_revoke.call_args_list == [
            (
                ("test_refresh_token", "refresh_token"),
                {"auth_url": "https://auth-minted.example.com/auth/v1"},
            ),
            (
                ("test_access_token", "access_token"),
                {"auth_url": "https://auth-minted.example.com/auth/v1"},
            ),
        ]
        mock_creds.delete_token.assert_called_once()
        mock_creds.delete_refresh_token.assert_called_once()


def test_auth_logout_revocation_unavailable():
    """Logout still clears local credentials when revocation fails."""
    with (
        patch("campus_cli.auth.login.credentials") as mock_creds,
        patch(
            "campus_cli.auth.login.revoke_token", return_value=False
        ) as mock_revoke,
    ):
        mock_creds.get_token.return_value = "test_access_token"
        mock_creds.get_refresh_token.return_value = None

        result = runner.invoke(app, ["auth", "logout", "-y"])

        assert result.exit_code == 0
        assert "Logged out successfully" in result.stdout
        assert "revocation was unavailable" in result.stdout
        assert mock_revoke.call_args_list == [
            (("test_access_token", "access_token"), {"auth_url": ANY}),
        ]
        mock_creds.delete_token.assert_called_once()
        mock_creds.delete_refresh_token.assert_called_once()


def test_auth_logout_not_authenticated():
    """Test logout is a friendly no-op when no token is stored."""
    with (
        patch("campus_cli.auth.login.credentials") as mock_creds,
        patch("campus_cli.auth.login.revoke_token") as mock_revoke,
    ):
        mock_creds.get_token.return_value = None

        result = runner.invoke(app, ["auth", "logout"])

        assert result.exit_code == 0
        assert "Not logged in" in result.stdout
        mock_revoke.assert_not_called()
        mock_creds.delete_token.assert_not_called()
        # A stray refresh token without an access token is still cleared
        mock_creds.delete_refresh_token.assert_called_once()


def test_auth_logout_refuses_without_confirmation_when_non_interactive():
    """No TTY and no waiver exits with the remedy instead of blocking."""
    with (
        patch("campus_cli.auth.login.credentials") as mock_creds,
        patch("campus_cli.auth.login.revoke_token", return_value=True),
    ):
        mock_creds.get_token.return_value = "test_access_token"

        result = runner.invoke(app, ["auth", "logout"])

    assert result.exit_code == 1
    assert "Refusing to proceed" in result.output
    assert "-y" in result.output
    assert "CAMPUS_ASSUME_YES" in result.output
    mock_creds.delete_token.assert_not_called()
    mock_creds.delete_refresh_token.assert_not_called()


def test_auth_logout_assume_yes_env_proceeds_without_flag(monkeypatch):
    """CAMPUS_ASSUME_YES=1 waives confirmation for the session."""
    monkeypatch.setenv("CAMPUS_ASSUME_YES", "1")
    with (
        patch("campus_cli.auth.login.credentials") as mock_creds,
        patch(
            "campus_cli.auth.login.revoke_token", return_value=True
        ) as mock_revoke,
    ):
        mock_creds.get_token.return_value = "test_access_token"
        mock_creds.get_refresh_token.return_value = None

        result = runner.invoke(app, ["auth", "logout"])

    assert result.exit_code == 0
    assert "Logged out successfully" in result.stdout
    mock_revoke.assert_called_once()
    mock_creds.delete_token.assert_called_once()


def test_client_delete_refuses_non_interactive_without_waiver():
    """client delete without -y refuses fast when there is no TTY."""
    with patch("campus_cli.auth.client.get_api_client") as mock_get:
        result = runner.invoke(app, ["client", "delete", "--client-id", "uid-x"])

    assert result.exit_code == 1
    assert "Refusing to proceed" in result.output
    assert "delete client 'uid-x'" in result.output
    mock_get.assert_not_called()


def test_client_delete_y_flag_proceeds():
    """-y waives the confirmation for one invocation."""
    with patch("campus_cli.auth.client.get_api_client") as mock_get:
        result = runner.invoke(
            app, ["client", "delete", "--client-id", "uid-x", "-y"]
        )

    assert result.exit_code == 0
    mock_get.return_value.auth_clients["uid-x"].delete.assert_called_once()


def test_client_delete_assume_yes_env_proceeds(monkeypatch):
    """CAMPUS_ASSUME_YES=1 waives the confirmation without -y."""
    monkeypatch.setenv("CAMPUS_ASSUME_YES", "1")
    with patch("campus_cli.auth.client.get_api_client") as mock_get:
        result = runner.invoke(app, ["client", "delete", "--client-id", "uid-x"])

    assert result.exit_code == 0
    mock_get.return_value.auth_clients["uid-x"].delete.assert_called_once()


def test_auth_status_json_format():
    """Test auth status outputs valid JSON when requested."""
    # Mock credentials to ensure no token is stored (isolated test)
    with patch("campus_cli.auth.common.credentials") as mock_creds:
        mock_creds.get_token.return_value = None
        mock_creds.get_refresh_token.return_value = None
        mock_creds.get_token_expires_at.return_value = None
        mock_creds.get_token_auth_url.return_value = None

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


def test_client_get_json_includes_redirect_uris_and_is_public():
    """issue #21: client get --json no longer drops redirect_uris/is_public."""
    with patch("campus_cli.auth.client.get_api_client") as mock_get:
        mock_get.return_value.auth_clients["uid-client-test1234"].get.return_value = (
            _mock_client(redirect_uris=["https://a/cb"], is_public=True)
        )

        result = runner.invoke(
            app, ["client", "get", "--client-id", "uid-client-test1234", "--json"]
        )

    assert result.exit_code == 0
    payload = json_loads(result.stdout)
    assert payload["redirect_uris"] == ["https://a/cb"]
    assert payload["is_public"] is True


def test_client_get_json_includes_scope_and_bridge_fields():
    """campus-cli#24: client get --json carries the fail-closed fields."""
    with patch("campus_cli.auth.client.get_api_client") as mock_get:
        mock_get.return_value.auth_clients["uid-client-test1234"].get.return_value = (
            _mock_client(
                allowed_scopes=["openid"],
                upstream_scopes={"google": ["https://a.example/calendar"]},
                token_bridge=True,
            )
        )

        result = runner.invoke(
            app, ["client", "get", "--client-id", "uid-client-test1234", "--json"]
        )

    assert result.exit_code == 0
    payload = json_loads(result.stdout)
    assert payload["allowed_scopes"] == ["openid"]
    assert payload["upstream_scopes"] == {"google": ["https://a.example/calendar"]}
    assert payload["token_bridge"] is True


def test_client_get_table_shows_scope_and_bridge_fields():
    """campus-cli#24: table mode prints allowlists and the bridge flag."""
    with patch("campus_cli.auth.client.get_api_client") as mock_get:
        mock_get.return_value.auth_clients["uid-client-test1234"].get.return_value = (
            _mock_client(
                allowed_scopes=["openid"],
                upstream_scopes={"google": ["https://a.example/calendar"]},
                token_bridge=True,
            )
        )

        result = runner.invoke(
            app, ["client", "get", "--client-id", "uid-client-test1234"]
        )

    assert result.exit_code == 0
    assert "Allowed scopes:" in result.stdout
    assert "- openid" in result.stdout
    assert "Upstream scopes:" in result.stdout
    assert "google:" in result.stdout
    assert "Token bridge: yes" in result.stdout


def test_client_list_json_includes_redirect_uris_and_is_public():
    """issue #21: client list --json no longer drops redirect_uris/is_public."""
    with patch("campus_cli.auth.client.get_api_client") as mock_get:
        mock_get.return_value.auth_clients.list.return_value = [
            _mock_client(redirect_uris=["https://a/cb"], is_public=True),
        ]

        result = runner.invoke(app, ["client", "list", "--json"])

    assert result.exit_code == 0
    payload = json_loads(result.stdout)
    assert payload[0]["redirect_uris"] == ["https://a/cb"]
    assert payload[0]["is_public"] is True


def test_client_list_table_shows_redirect_uris_and_public_flag():
    """issue #21: table mode prints each redirect URI and the public flag."""
    with patch("campus_cli.auth.client.get_api_client") as mock_get:
        mock_get.return_value.auth_clients.list.return_value = [
            _mock_client(redirect_uris=["https://a/cb"], is_public=True),
            _mock_client(),
        ]

        result = runner.invoke(app, ["client", "list"])

    assert result.exit_code == 0
    assert result.stdout.count("Redirect URIs:") == 2
    assert "    - https://a/cb" in result.stdout
    assert "    (none)" in result.stdout
    assert result.stdout.count("Public client: yes") == 1
    assert result.stdout.count("Public client: no") == 1


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
        mock_creds.get_token_auth_url.return_value = None

        result = runner.invoke(app, ["auth", "status"])

        assert result.exit_code == 0
        assert "Authenticated" in result.stdout
        assert "Auth endpoint" in result.stdout


def _bound_mocks(stored_auth_url, target_auth_url):
    """Build credential/config mocks sharing one endpoint binding state.

    login_cmd reads login's globals while endpoint_mismatch() reads
    common's; both names must point at the same mocks for the two
    modules to agree on the targeted endpoint.
    """
    creds = Mock()
    creds.get_token.return_value = "test_access_token"
    creds.is_token_expired.return_value = False
    creds.get_token_auth_url.return_value = stored_auth_url
    target_config = Mock(auth_url=target_auth_url)
    patches = [
        patch("campus_cli.auth.login.credentials", creds),
        patch("campus_cli.auth.common.credentials", creds),
        patch("campus_cli.auth.login.config", target_config),
        patch("campus_cli.auth.common.config", target_config),
    ]
    return creds, patches


def test_auth_login_mismatch_bypasses_already_authenticated():
    """An endpoint mismatch re-authenticates instead of no-op short-circuit."""
    creds, patches = _bound_mocks(
        stored_auth_url="https://auth-old.example.com/auth/v1",
        target_auth_url="https://auth-target.example.com/auth/v1",
    )

    with (
        patches[0],
        patches[1],
        patches[2],
        patches[3],
        patch(
            "campus_cli.auth.login.request_device_code",
            side_effect=DeviceAuthError("stop here"),
        ),
    ):
        result = runner.invoke(app, ["auth", "login"])

    assert result.exit_code == 1
    assert "Already authenticated" not in result.stdout
    assert "Re-authenticating" in result.stdout
    assert "https://auth-old.example.com/auth/v1" in result.stdout
    assert "Requesting device code" in result.stdout


def test_auth_login_already_authenticated_matching_endpoint():
    """Matching binding keeps the already-authenticated short-circuit."""
    creds, patches = _bound_mocks(
        stored_auth_url="https://auth-target.example.com/auth/v1",
        target_auth_url="https://auth-target.example.com/auth/v1",
    )

    with patches[0], patches[1], patches[2], patches[3]:
        result = runner.invoke(app, ["auth", "login"])

    assert result.exit_code == 0
    assert "Already authenticated" in result.stdout
    assert "Authenticated against" in result.stdout


def test_auth_login_scope_bypasses_already_authenticated():
    """issue #38: --scope mints a new token instead of no-op short-circuit.

    A valid stored token for the same endpoint must not swallow an
    explicit --scope request: re-login with wider scopes is the
    documented upgrade path, so the device flow must run with them.
    """
    creds, patches = _bound_mocks(
        stored_auth_url="https://auth-target.example.com/auth/v1",
        target_auth_url="https://auth-target.example.com/auth/v1",
    )

    with (
        patches[0],
        patches[1],
        patches[2],
        patches[3],
        patch(
            "campus_cli.auth.login.request_device_code",
            side_effect=DeviceAuthError("stop here"),
        ) as mock_device,
    ):
        result = runner.invoke(
            app,
            ["auth", "login", "--scope", "clients:write"],
        )

    assert result.exit_code == 1
    assert "Already authenticated" not in result.stdout
    assert "Re-authenticating to request scopes: clients:write" in result.stdout
    assert "Requesting device code" in result.stdout
    mock_device.assert_called_once_with(scopes=["clients:write"])


def test_auth_login_scopeless_keeps_short_circuit():
    """issue #38: scope-less login with a valid token stays a no-op."""
    creds, patches = _bound_mocks(
        stored_auth_url="https://auth-target.example.com/auth/v1",
        target_auth_url="https://auth-target.example.com/auth/v1",
    )

    with (
        patches[0],
        patches[1],
        patches[2],
        patches[3],
        patch(
            "campus_cli.auth.login.request_device_code",
            side_effect=DeviceAuthError("must not run"),
        ) as mock_device,
    ):
        result = runner.invoke(app, ["auth", "login"])

    assert result.exit_code == 0
    assert "Already authenticated" in result.stdout
    mock_device.assert_not_called()


def test_auth_login_binds_tokens_to_target_auth_url():
    """A successful login stamps the issuing endpoint onto the credentials."""
    target = "https://auth-target.example.com/auth/v1"
    creds, patches = _bound_mocks(stored_auth_url=None, target_auth_url=target)
    creds.get_token.return_value = None

    device_data = {
        "user_code": "ABC-123",
        "verification_uri": "https://verify.example.com",
        "device_code": "device_code",
        "interval": 5,
        "expires_in": 300,
    }
    token_data = {
        "access_token": "new_access_token",
        "refresh_token": "new_refresh_token",
        "expires_in": 3600,
    }

    with (
        patches[0],
        patches[1],
        patches[2],
        patches[3],
        patch(
            "campus_cli.auth.login.request_device_code",
            return_value=device_data,
        ),
        patch(
            "campus_cli.auth.login.poll_for_token",
            return_value=token_data,
        ),
        patch("campus_cli.auth.login.webbrowser"),
        # Never touch a real clipboard from CI (#43).
        patch(
            "campus_cli.auth.login.copy_to_clipboard",
            return_value="native",
        ) as mock_copy,
    ):
        result = runner.invoke(app, ["auth", "login"])

    assert result.exit_code == 0
    assert "Authentication successful" in result.stdout
    assert "Code copied to clipboard" in result.stdout
    mock_copy.assert_called_once_with("ABC-123")
    assert target in result.stdout
    creds.set_token_auth_url.assert_called_once_with(target)


def test_auth_refresh_endpoint_mismatch_fails_fast():
    """refresh refuses to send a foreign refresh token to this endpoint."""
    _, patches = _bound_mocks(
        stored_auth_url="https://auth-old.example.com/auth/v1",
        target_auth_url="https://auth-target.example.com/auth/v1",
    )

    with (
        patches[0],
        patches[1],
        patches[2],
        patches[3],
        patch("campus_cli.auth.login.refresh_access_token") as mock_refresh,
    ):
        result = runner.invoke(app, ["auth", "refresh"])

    assert result.exit_code == 1
    mock_refresh.assert_not_called()
    assert "issued by" in result.output


def test_auth_refresh_json_output_survives_long_tokens():
    """--json is machine-readable: Rich wrapping must not split the token."""
    long_token = "a" * 200
    creds = Mock()
    creds.get_token.return_value = "stale_access_token"
    creds.get_token_expires_at.return_value = "2026-10-04T12:00:00+00:00"
    with (
        patch("campus_cli.auth.login.credentials", creds),
        patch(
            "campus_cli.auth.common.credentials",
            Mock(get_token_auth_url=Mock(return_value=None)),
        ),
        patch(
            "campus_cli.auth.login.refresh_access_token",
            return_value=long_token,
        ),
    ):
        result = runner.invoke(app, ["auth", "refresh", "--json"])

    assert result.exit_code == 0
    payload = json_loads(result.stdout)
    assert payload["access_token"] == long_token


def test_auth_status_shows_endpoint_mismatch():
    """A stored token from a different endpoint is flagged in status."""
    with patch("campus_cli.auth.common.credentials") as mock_creds:
        mock_creds.get_token.return_value = "test_access_token"
        mock_creds.get_refresh_token.return_value = None
        mock_creds.get_token_expires_at.return_value = None
        mock_creds.is_token_expired.return_value = False
        mock_creds.get_token_auth_url.return_value = (
            "https://auth-other.example.com/auth/v1"
        )

        result = runner.invoke(app, ["auth", "status"])

        assert result.exit_code == 0
        assert "Endpoint mismatch" in result.stdout
        assert "https://auth-other.example.com/auth/v1" in result.stdout


def test_auth_status_json_includes_endpoint_binding():
    """auth status --json exposes both endpoints and the match verdict."""
    with patch("campus_cli.auth.common.credentials") as mock_creds:
        mock_creds.get_token.return_value = "test_access_token"
        mock_creds.get_refresh_token.return_value = None
        mock_creds.get_token_expires_at.return_value = None
        mock_creds.is_token_expired.return_value = False
        mock_creds.get_token_auth_url.return_value = (
            "https://auth-other.example.com/auth/v1"
        )

        result = runner.invoke(app, ["auth", "status", "--json"])

        assert result.exit_code == 0
        status = json_loads(result.stdout)
        assert status["token_auth_url"] == (
            "https://auth-other.example.com/auth/v1"
        )
        assert status["endpoint_match"] is False
        assert "auth_url" in status
