"""Unit tests for client output formatting."""

from datetime import datetime, timezone
from types import SimpleNamespace

from campus_cli.auth.client import _format_client


def _client(created_at, **overrides):
    fields = {
        "id": "uid-client-ab12cd34",
        "name": "Test Client",
        "description": "A test client",
        "created_at": created_at,
        "permissions": {"campus.api": 1},
        "redirect_uris": [],
        "allowed_scopes": [],
        "upstream_scopes": {},
        "token_bridge": False,
        "is_public": False,
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


def test_format_client_with_datetime_created_at():
    """Locally-constructed models carry a datetime created_at."""
    dt = datetime(2026, 9, 29, 10, 0, tzinfo=timezone.utc)
    result = _format_client(_client(dt))
    assert result["created_at"] == "2026-09-29T10:00:00+00:00"


def test_format_client_with_string_created_at():
    """from_resource models carry created_at as an ISO string verbatim."""
    result = _format_client(_client("2026-09-29T10:00:00+00:00"))
    assert result["created_at"] == "2026-09-29T10:00:00+00:00"


def test_format_client_with_none_created_at():
    """created_at may be absent/None."""
    result = _format_client(_client(None))
    assert result["created_at"] is None


def test_format_client_includes_redirect_uris_and_is_public():
    """issue #21: JSON output must carry redirect_uris and is_public."""
    result = _format_client(_client(
        "2026-09-29T10:00:00+00:00",
        redirect_uris=["https://example.edu/callback"],
        is_public=True,
    ))
    assert result["redirect_uris"] == ["https://example.edu/callback"]
    assert result["is_public"] is True


def test_format_client_coerces_none_redirect_uris_to_empty_list():
    """A null redirect_uris projects as [] so the field is always present."""
    result = _format_client(_client(
        "2026-09-29T10:00:00+00:00", redirect_uris=None
    ))
    assert result["redirect_uris"] == []
    assert result["is_public"] is False


def test_format_client_includes_scope_and_bridge_fields():
    """campus-cli#24: JSON output must carry the fail-closed admin fields."""
    result = _format_client(_client(
        "2026-09-29T10:00:00+00:00",
        allowed_scopes=["openid", "campus.api"],
        upstream_scopes={"google": ["https://www.googleapis.com/auth/calendar"]},
        token_bridge=True,
    ))
    assert result["allowed_scopes"] == ["openid", "campus.api"]
    assert result["upstream_scopes"] == {
        "google": ["https://www.googleapis.com/auth/calendar"]
    }
    assert result["token_bridge"] is True


def test_format_client_defaults_scope_fields_when_none():
    """Null scope/bridge fields project as empty values, always present."""
    result = _format_client(_client(
        "2026-09-29T10:00:00+00:00",
        allowed_scopes=None,
        upstream_scopes=None,
        token_bridge=None,
    ))
    assert result["allowed_scopes"] == []
    assert result["upstream_scopes"] == {}
    assert result["token_bridge"] is False


# --- client new option wiring (campus-cli#75) ---

from unittest.mock import MagicMock, patch  # noqa: E402

from typer.testing import CliRunner  # noqa: E402

from campus_cli.cli import app  # noqa: E402

_runner = CliRunner()


def _new_client(**overrides):
    """A created-client model shaped for _format_client()."""
    fields = {
        "id": "uid-client-ef56ab78",
        "name": "Scoped App",
        "description": "Created by test",
        "created_at": "2026-11-06T05:00:00+00:00",
        "permissions": {},
        "redirect_uris": [],
        "allowed_scopes": [],
        "upstream_scopes": {},
        "token_bridge": False,
        "is_public": False,
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


def test_client_new_passes_scope_options_to_sdk():
    with patch("campus_cli.auth.client.get_api_client") as mock_get:
        api = MagicMock()
        api.auth_clients.new.return_value = _new_client()
        mock_get.return_value = api
        result = _runner.invoke(app, [
            "client", "new",
            "--name", "Scoped App", "--description", "Created by test",
            "--allowed-scope", "openid",
            "--allowed-scope", "campus.api",
            "--upstream-scope", "google=https://a/sc1",
            "--upstream-scope", "google=https://a/sc2",
            "--upstream-scope", "gsuite=https://a/sc3",
            "--token-bridge",
        ])
    assert result.exit_code == 0, result.stdout
    kwargs = api.auth_clients.new.call_args.kwargs
    assert kwargs["allowed_scopes"] == ["openid", "campus.api"]
    assert kwargs["upstream_scopes"] == {
        "google": ["https://a/sc1", "https://a/sc2"],
        "gsuite": ["https://a/sc3"],
    }
    assert kwargs["token_bridge"] is True


def test_client_new_omits_unset_scope_options():
    with patch("campus_cli.auth.client.get_api_client") as mock_get:
        api = MagicMock()
        api.auth_clients.new.return_value = _new_client()
        mock_get.return_value = api
        result = _runner.invoke(app, [
            "client", "new", "--name", "Plain", "--description", "d",
        ])
    assert result.exit_code == 0, result.stdout
    kwargs = api.auth_clients.new.call_args.kwargs
    assert kwargs["allowed_scopes"] is None
    assert kwargs["upstream_scopes"] is None
    assert kwargs["token_bridge"] is None


def test_client_new_invalid_upstream_scope_fails_fast():
    with patch("campus_cli.auth.client.get_api_client") as mock_get:
        result = _runner.invoke(app, [
            "client", "new",
            "--name", "X", "--description", "d",
            "--upstream-scope", "bogus",
        ])
    assert result.exit_code == 1
    assert "provider=scope" in result.stderr
    mock_get.assert_not_called()


def test_client_new_dry_run_renders_scope_options():
    with patch("campus_cli.auth.client.get_api_client") as mock_get:
        result = _runner.invoke(app, [
            "client", "new",
            "--name", "X", "--description", "d",
            "--allowed-scope", "openid",
            "--upstream-scope", "google=https://a/sc1",
            "--no-token-bridge",
            "--dry-run",
        ])
        mock_get.assert_not_called()
    assert result.exit_code == 0, result.stdout
    assert "allowed_scopes=['openid']" in result.stdout
    assert "upstream_scopes={'google': ['https://a/sc1']}" in result.stdout
    assert "token_bridge=False" in result.stdout
