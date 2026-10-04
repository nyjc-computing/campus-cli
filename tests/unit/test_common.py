"""Unit tests for shared auth helpers: endpoint binding and refresh."""

from unittest import mock

import pytest
import typer

from campus_cli.auth import common
from campus_cli.auth.common import (
    confirm_destructive,
    endpoint_mismatch,
    ensure_endpoint_match,
    normalize_auth_url,
    refresh_access_token,
)

TARGET = "https://auth-target.example.com/auth/v1"
OTHER = "https://auth-other.example.com/auth/v1"


def _bind(monkeypatch, stored_auth_url: str | None, current_auth_url: str):
    """Point common's credentials/config at mocks with the given endpoints."""
    creds = mock.Mock()
    creds.get_token_auth_url.return_value = stored_auth_url
    monkeypatch.setattr(common, "credentials", creds)
    monkeypatch.setattr(common, "config", mock.Mock(auth_url=current_auth_url))
    return creds


def test_normalize_auth_url_strips_trailing_slashes():
    """Trailing slashes do not affect URL equality."""
    assert normalize_auth_url("https://a.example.com/v1/") == (
        "https://a.example.com/v1"
    )
    assert normalize_auth_url("https://a.example.com/v1") == (
        "https://a.example.com/v1"
    )


def test_endpoint_mismatch_none_when_no_stored_url(monkeypatch):
    """Credentials stored before endpoint binding are treated as matching."""
    _bind(monkeypatch, stored_auth_url=None, current_auth_url=TARGET)
    assert endpoint_mismatch() is None


def test_endpoint_mismatch_none_when_urls_match(monkeypatch):
    """Identical endpoints (ignoring trailing slashes) are a match."""
    _bind(monkeypatch, stored_auth_url=TARGET + "/", current_auth_url=TARGET)
    assert endpoint_mismatch() is None


def test_endpoint_mismatch_returns_both_urls(monkeypatch):
    """A mismatch surfaces both the issuing and targeted endpoints."""
    _bind(monkeypatch, stored_auth_url=OTHER, current_auth_url=TARGET)
    assert endpoint_mismatch() == (OTHER, TARGET)


def test_ensure_endpoint_match_passes_when_no_mismatch(monkeypatch):
    """Matching credentials do not exit."""
    _bind(monkeypatch, stored_auth_url=TARGET, current_auth_url=TARGET)
    ensure_endpoint_match()


def test_ensure_endpoint_match_exits_with_actionable_message(monkeypatch, capsys):
    """A mismatch exits with both endpoints and the login remediation."""
    _bind(monkeypatch, stored_auth_url=OTHER, current_auth_url=TARGET)

    with pytest.raises(typer.Exit) as excinfo:
        ensure_endpoint_match()

    assert excinfo.value.exit_code == 1
    err = capsys.readouterr().err
    assert OTHER in err
    assert TARGET in err
    assert "campus auth login" in err


def test_refresh_access_token_binds_credentials_to_auth_url(monkeypatch):
    """A successful refresh stamps the currently targeted endpoint."""
    creds = _bind(monkeypatch, stored_auth_url=TARGET, current_auth_url=TARGET)
    creds.get_refresh_token.return_value = "refresh_token"

    response = mock.Mock(status_code=200)
    response.json.return_value = {
        "access_token": "new_access_token",
        "refresh_token": "new_refresh_token",
        "expires_in": 3600,
    }
    monkeypatch.setattr(common, "requests", mock.Mock(post=mock.Mock(
        return_value=response
    )))

    token = refresh_access_token()

    assert token == "new_access_token"
    creds.set_token_auth_url.assert_called_once_with(TARGET)


class _InvalidEnvConfig:
    """Config stub whose auth_url raises like an invalid ENV/CAMPUS_ENV."""

    @property
    def auth_url(self):
        raise ValueError(
            "Invalid deployment environment 'bogus' in ENV/CAMPUS_ENV; "
            "expected development, staging, or production"
        )


def test_resolve_auth_url_returns_current_target(monkeypatch):
    """The resolved auth URL is the configured target."""
    monkeypatch.setattr(common, "config", mock.Mock(auth_url=TARGET))
    assert common.resolve_auth_url() == TARGET


def test_resolve_auth_url_exits_cleanly_on_invalid_env(monkeypatch, capsys):
    """An invalid ENV/CAMPUS_ENV exits with an error, not a traceback."""
    monkeypatch.setattr(common, "config", _InvalidEnvConfig())

    with pytest.raises(typer.Exit) as excinfo:
        common.resolve_auth_url()

    assert excinfo.value.exit_code == 1
    assert "bogus" in capsys.readouterr().err


def test_confirm_destructive_skips_when_flag_passed():
    """--confirm/-y waives the confirmation entirely."""
    confirm_destructive("delete the thing", skip=True)


@pytest.mark.parametrize("value", ["1", "true", "yes", "YES", " True "])
def test_confirm_destructive_assume_yes_env_truthy_values(monkeypatch, value):
    """CAMPUS_ASSUME_YES accepts the usual truthy spellings."""
    monkeypatch.setenv("CAMPUS_ASSUME_YES", value)
    confirm_destructive("delete the thing", skip=False)


def test_confirm_destructive_assume_yes_env_falsy_values(monkeypatch, capsys):
    """'0'/'false'/'' do not waive confirmation: non-TTY still refuses."""
    monkeypatch.setattr("sys.stdin", mock.Mock(isatty=mock.Mock(return_value=False)))
    for value in ["0", "false", ""]:
        monkeypatch.setenv("CAMPUS_ASSUME_YES", value)
        with pytest.raises(typer.Exit) as excinfo:
            confirm_destructive("delete the thing", skip=False)
        assert excinfo.value.exit_code == 1
    assert "delete the thing" in capsys.readouterr().err


def test_confirm_destructive_refuses_fast_without_tty(monkeypatch, capsys):
    """Non-interactive callers get an exit naming -y, never a blocking read."""
    monkeypatch.setattr("sys.stdin", mock.Mock(isatty=mock.Mock(return_value=False)))
    monkeypatch.delenv("CAMPUS_ASSUME_YES", raising=False)

    with (
        mock.patch.object(common.typer, "confirm") as mock_confirm,
        pytest.raises(typer.Exit) as excinfo,
    ):
        confirm_destructive("delete client 'uid-x'", skip=False)

    assert excinfo.value.exit_code == 1
    mock_confirm.assert_not_called()
    err = capsys.readouterr().err
    assert "Refusing to proceed" in err
    assert "delete client 'uid-x'" in err
    assert "-y" in err
    assert "CAMPUS_ASSUME_YES=1" in err


def test_confirm_destructive_prompts_when_tty(monkeypatch):
    """With a TTY the interactive prompt still runs and propagates aborts."""
    tty_stdin = mock.Mock()
    tty_stdin.isatty.return_value = True
    monkeypatch.setattr("sys.stdin", tty_stdin)
    monkeypatch.delenv("CAMPUS_ASSUME_YES", raising=False)

    with (
        mock.patch.object(
            common.typer, "confirm", side_effect=typer.Abort
        ) as mock_confirm,
        pytest.raises(typer.Abort),
    ):
        confirm_destructive("delete client 'uid-x'", skip=False)

    mock_confirm.assert_called_once_with("delete client 'uid-x'", abort=True)
