"""Unit tests for the campus.audit command group (#54)."""

from unittest import mock

import pytest
import requests
import typer
from campus_python import errors
from typer.testing import CliRunner

from campus_cli.audit.client import (
    api_error_details,
    audit_endpoint_mismatch,
    resolve_audit_url,
)
from campus_cli.audit.login import _resolve_key_input, verify_api_key
from campus_cli.audit.traces import _format_trace_summary, _status_markup
from campus_cli.cli import app
from campus_cli.config import Config
from campus_cli.credentials import CredentialError

AUDIT_URL = "https://audit.example.test"


def _http_error(status, error_body=None):
    """Build an HTTPError whose response carries the given status/body."""
    response = mock.Mock(spec=requests.Response, status_code=status)
    if error_body is None:
        response.json.side_effect = ValueError("no json body")
    else:
        response.json.return_value = error_body
    return requests.HTTPError("error", response=response)


class TestApiErrorMessage:
    """api_error_details extracts status and message from both error shapes."""

    def test_client_library_api_error(self):
        # campus_python raises errors.APIError for non-2xx responses.
        error = errors.APIError(
            status_code=401, error_description="Invalid API key"
        )
        assert api_error_details(error) == (401, "Invalid API key")

    def test_raw_http_error_structured_body(self):
        error = _http_error(400, {
            "error": {"code": "AUDIT_INVALID", "message": "bad scopes"}
        })
        assert api_error_details(error) == (400, "bad scopes")

    def test_raw_http_error_code_without_message(self):
        error = _http_error(400, {"error": {"code": "AUDIT_INVALID"}})
        assert api_error_details(error) == (400, "AUDIT_INVALID")

    def test_raw_http_error_plain_body(self):
        error = _http_error(400, {"error": "invalid_key"})
        assert api_error_details(error) == (400, "invalid_key")

    def test_raw_http_error_without_json_body(self):
        status, message = api_error_details(_http_error(404))
        assert status == 404
        assert message  # degrades to the exception text

    def test_network_error_keeps_exception_text(self):
        error = requests.ConnectionError("connection refused")
        assert api_error_details(error) == (None, "connection refused")


class TestResolveAuditUrl:
    """audit URL resolution mirrors campus_python's precedence."""

    @pytest.fixture
    def config(self, tmp_path, monkeypatch):
        """A Config isolated from the developer's real config file."""
        monkeypatch.delenv("CAMPUS_AUDIT_URL", raising=False)
        monkeypatch.delenv("ENV", raising=False)
        monkeypatch.delenv("CAMPUS_ENV", raising=False)
        return Config(config_path=tmp_path / "config.json")

    def test_development_default(self, config):
        assert config.audit_url == Config.DEFAULT_AUDIT_URL

    def test_staging_env_mapping(self, config, monkeypatch):
        monkeypatch.setenv("ENV", "staging")
        assert config.audit_url == Config.STAGING_AUDIT_URL

    def test_production_env_mapping(self, config, monkeypatch):
        monkeypatch.setenv("ENV", "production")
        assert config.audit_url == Config.PRODUCTION_AUDIT_URL

    def test_testing_maps_to_development(self, config, monkeypatch):
        monkeypatch.setenv("CAMPUS_ENV", "testing")
        assert config.audit_url == Config.DEFAULT_AUDIT_URL

    def test_explicit_env_var_wins(self, config, monkeypatch):
        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("CAMPUS_AUDIT_URL", AUDIT_URL)
        assert config.audit_url == AUDIT_URL

    def test_config_file_key_beats_env_mapping(self, config, monkeypatch):
        monkeypatch.setenv("ENV", "production")
        config.audit_url = AUDIT_URL
        assert config.audit_url == AUDIT_URL

    def test_invalid_env_exits_cleanly(self, config, monkeypatch):
        monkeypatch.setenv("ENV", "qa")
        with (
            mock.patch("campus_cli.audit.client.config", config),
            pytest.raises(typer.Exit),
        ):
            resolve_audit_url()


class TestAuditEndpointMismatch:
    """Stored keys are bound to the audit URL they were stored for."""

    def test_no_url_binding_matches(self, monkeypatch):
        creds = mock.Mock()
        creds.get_audit_key_url.return_value = None
        monkeypatch.setattr("campus_cli.audit.client.credentials", creds)
        assert audit_endpoint_mismatch() is None

    def test_trailing_slash_normalized(self, monkeypatch):
        creds = mock.Mock()
        creds.get_audit_key_url.return_value = AUDIT_URL + "/"
        monkeypatch.setattr("campus_cli.audit.client.credentials", creds)
        monkeypatch.setenv("CAMPUS_AUDIT_URL", AUDIT_URL)
        assert audit_endpoint_mismatch() is None

    def test_mismatch_reports_both(self, monkeypatch):
        creds = mock.Mock()
        creds.get_audit_key_url.return_value = "https://audit-old.test"
        monkeypatch.setattr("campus_cli.audit.client.credentials", creds)
        monkeypatch.setenv("CAMPUS_AUDIT_URL", AUDIT_URL)
        assert audit_endpoint_mismatch() == ("https://audit-old.test", AUDIT_URL)


class TestResolveKeyInput:
    """The key comes from --api-key, the environment, or a prompt."""

    def test_option_wins_over_env(self, monkeypatch):
        monkeypatch.setenv("CAMPUS_AUDIT_API_KEY", "audit_v1_env")
        assert _resolve_key_input("audit_v1_opt") == "audit_v1_opt"

    def test_env_fallback_is_stripped(self, monkeypatch):
        monkeypatch.setenv("CAMPUS_AUDIT_API_KEY", "  audit_v1_env \n")
        assert _resolve_key_input(None) == "audit_v1_env"

    def test_prompted_when_interactive(self, monkeypatch):
        monkeypatch.delenv("CAMPUS_AUDIT_API_KEY", raising=False)
        monkeypatch.setattr("sys.stdin", mock.Mock(isatty=lambda: True))
        monkeypatch.setattr(
            "campus_cli.audit.login.typer.prompt",
            lambda *_args, **_kwargs: "audit_v1_prompted",
        )
        assert _resolve_key_input(None) == "audit_v1_prompted"

    def test_nothing_given_exits_non_interactive(self, monkeypatch):
        monkeypatch.delenv("CAMPUS_AUDIT_API_KEY", raising=False)
        monkeypatch.setattr("sys.stdin", mock.Mock(isatty=lambda: False))
        with pytest.raises(typer.Exit):
            _resolve_key_input(None)

    def test_blank_option_exits(self, monkeypatch):
        monkeypatch.delenv("CAMPUS_AUDIT_API_KEY", raising=False)
        monkeypatch.setattr("sys.stdin", mock.Mock(isatty=lambda: False))
        with pytest.raises(typer.Exit):
            _resolve_key_input("   ")


class TestVerifyApiKey:
    """Any authenticated response proves the key; 401 rejects it."""

    def _verify(self, side_effect):
        with mock.patch.multiple(
            "campus_python", AuditRoot=mock.DEFAULT, CampusRequest=mock.DEFAULT
        ) as mocked:
            root = mocked["AuditRoot"].return_value
            if side_effect is not None:
                root.apikeys.list.side_effect = side_effect
            return verify_api_key(AUDIT_URL, "audit_v1_k")

    def test_accepted_key_verifies(self):
        assert self._verify(None) == "verified"

    def test_forbidden_key_is_authenticated(self):
        # 403: valid key, but no apikeys:read (trace-only student key).
        assert self._verify(_http_error(403)) == "verified"

    def test_rejected_key_raises_without_storing(self):
        with pytest.raises(typer.Exit):
            self._verify(_http_error(401))

    def test_unreachable_service_stores_unverified(self):
        assert self._verify(
            requests.ConnectionError("connection refused")
        ) == "unverified"

    def test_server_error_does_not_prove_the_key(self):
        assert self._verify(_http_error(500)) == "unverified"


class TestAuditLoginCmd:
    """campus audit login stores (or rejects) the key end to end."""

    def test_login_stores_key_bound_to_url(self):
        creds = mock.Mock()
        with (
            mock.patch("campus_cli.audit.login.credentials", creds),
            mock.patch(
                "campus_cli.audit.login.verify_api_key", return_value="verified"
            ),
            mock.patch.dict(
                "os.environ",
                {
                    "CAMPUS_AUDIT_URL": AUDIT_URL,
                    "CAMPUS_AUDIT_API_KEY": "audit_v1_new",
                },
            ),
        ):
            result = CliRunner().invoke(app, ["audit", "login"])
        assert result.exit_code == 0, result.output
        creds.set_audit_api_key.assert_called_once_with(
            "audit_v1_new", AUDIT_URL
        )

    def test_login_rejected_key_stores_nothing(self):
        creds = mock.Mock()
        with (
            mock.patch("campus_cli.audit.login.credentials", creds),
            mock.patch(
                "campus_cli.audit.login.verify_api_key",
                side_effect=typer.Exit(1),
            ),
            mock.patch.dict(
                "os.environ",
                {
                    "CAMPUS_AUDIT_URL": AUDIT_URL,
                    "CAMPUS_AUDIT_API_KEY": "audit_v1_bad",
                },
            ),
        ):
            result = CliRunner().invoke(app, ["audit", "login"])
        assert result.exit_code == 1
        creds.set_audit_api_key.assert_not_called()

    def test_login_skip_verify_stores_without_network(self):
        creds = mock.Mock()
        with (
            mock.patch("campus_cli.audit.login.credentials", creds),
            mock.patch("campus_cli.audit.login.verify_api_key") as mock_verify,
            mock.patch.dict(
                "os.environ",
                {
                    "CAMPUS_AUDIT_URL": AUDIT_URL,
                    "CAMPUS_AUDIT_API_KEY": "audit_v1_offline",
                },
            ),
        ):
            result = CliRunner().invoke(app, ["audit", "login", "--skip-verify"])
        assert result.exit_code == 0, result.output
        mock_verify.assert_not_called()
        creds.set_audit_api_key.assert_called_once_with(
            "audit_v1_offline", AUDIT_URL
        )

    def test_logout_clears_stored_key_with_confirm(self):
        creds = mock.Mock()
        creds.get_audit_api_key.return_value = "audit_v1_k"
        with mock.patch("campus_cli.audit.login.credentials", creds):
            result = CliRunner().invoke(app, ["audit", "logout", "--confirm"])
        assert result.exit_code == 0, result.output
        creds.delete_audit_api_key.assert_called_once()

    def test_logout_refuses_without_confirm_when_not_a_tty(self):
        creds = mock.Mock()
        creds.get_audit_api_key.return_value = "audit_v1_k"
        with mock.patch("campus_cli.audit.login.credentials", creds):
            result = CliRunner().invoke(app, ["audit", "logout"])
        assert result.exit_code == 1
        creds.delete_audit_api_key.assert_not_called()

    def test_logout_when_not_logged_in_is_a_noop(self):
        creds = mock.Mock()
        creds.get_audit_api_key.return_value = None
        with mock.patch("campus_cli.audit.login.credentials", creds):
            result = CliRunner().invoke(app, ["audit", "logout"])
        assert result.exit_code == 0, result.output
        creds.delete_audit_api_key.assert_not_called()


class TestTraceFormatting:
    """Trace summaries render status, timing, and principal."""

    def test_status_classes(self):
        assert "green" in _status_markup(200)
        assert "yellow" in _status_markup(404)
        assert "red" in _status_markup(500)
        assert "dim" in _status_markup(None)

    def test_summary_shows_request_and_timing(self):
        line = _format_trace_summary({
            "trace_id": "a" * 32,
            "span_count": 3,
            "started_at": "2026-10-20T10:00:00+00:00",
            "duration_ms": 42.5,
            "root_span": {
                "method": "GET",
                "path": "/auth/v1/users/",
                "status_code": 200,
                "user_id": "alice@school.edu",
            },
        })
        assert "GET /auth/v1/users/" in line
        assert "42.5 ms" in line
        assert "3 span(s)" in line
        assert "alice@school.edu" in line

    def test_summary_falls_back_to_anonymous(self):
        line = _format_trace_summary({
            "trace_id": "a" * 32,
            "span_count": 1,
            "duration_ms": 5,
            "root_span": {"method": "POST", "path": "/x", "status_code": 401},
        })
        assert "anonymous" in line


class TestAuditCredentialStorage:
    """The audit key rides the shared credential store, URL-bound."""

    def test_round_trip(self, credential_storage):
        credential_storage.set_audit_api_key("audit_v1_k", AUDIT_URL)
        assert credential_storage.get_audit_api_key() == "audit_v1_k"
        assert credential_storage.get_audit_key_url() == AUDIT_URL

        credential_storage.delete_audit_api_key()
        assert credential_storage.get_audit_api_key() is None
        assert credential_storage.get_audit_key_url() is None

    def test_delete_without_key_raises(self, credential_storage):
        with pytest.raises(CredentialError):
            credential_storage.delete_audit_api_key()
