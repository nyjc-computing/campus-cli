"""Unit tests for the campus.audit command group (#54)."""

import json
from unittest import mock

import pytest
import requests
import typer
from campus_python import errors
from typer.testing import CliRunner

from campus_cli.audit.client import (
    api_error_details,
    audit_endpoint_mismatch,
    fail_api,
    get_audit_client,
    resolve_audit_url,
)
from campus_cli.audit.keys import _key_status, _parse_timestamp
from campus_cli.audit.login import _resolve_key_input, verify_api_key
from campus_cli.audit.traces import (
    _content_length,
    _format_trace_summary,
    _status_markup,
    _ua_family,
)
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
    """audit URL resolution: BASE_URL stands in for a missing service URL."""

    PROD_GATEWAY = "https://nyjc-campus.up.railway.app"
    DEV_GATEWAY = "https://campus-development.up.railway.app"

    @pytest.fixture
    def config(self, tmp_path, monkeypatch):
        """A Config isolated from the developer's real config file."""
        for var in ("CAMPUS_AUDIT_URL", "AUDIT_URL", "ENV", "CAMPUS_ENV",
                    "CAMPUS_BASE_URL", "BASE_URL"):
            monkeypatch.delenv(var, raising=False)
        return Config(config_path=tmp_path / "config.json")

    def test_production_default(self, config):
        assert config.audit_url == self.PROD_GATEWAY

    def test_development_env_falls_back(self, config, monkeypatch):
        monkeypatch.setenv("ENV", "development")
        assert config.audit_url == self.DEV_GATEWAY

    def test_campus_env_development_falls_back(self, config, monkeypatch):
        monkeypatch.setenv("CAMPUS_ENV", "development")
        assert config.audit_url == self.DEV_GATEWAY

    def test_testing_maps_to_development(self, config, monkeypatch):
        monkeypatch.setenv("CAMPUS_ENV", "testing")
        assert config.audit_url == self.DEV_GATEWAY

    def test_staging_is_retired(self, config, monkeypatch):
        monkeypatch.setenv("ENV", "staging")
        with pytest.raises(ValueError, match="retired"):
            _ = config.audit_url

    def test_base_url_stand_in(self, config, monkeypatch):
        monkeypatch.setenv("BASE_URL", "https://gateway.example.com")
        assert config.audit_url == "https://gateway.example.com"

    def test_campus_base_url_wins_over_bare_alias(self, config, monkeypatch):
        monkeypatch.setenv("CAMPUS_BASE_URL", "https://campus-gw.example.com")
        monkeypatch.setenv("BASE_URL", "https://gw.example.com")
        assert config.audit_url == "https://campus-gw.example.com"

    def test_explicit_env_var_wins(self, config, monkeypatch):
        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("CAMPUS_AUDIT_URL", AUDIT_URL)
        assert config.audit_url == AUDIT_URL

    def test_bare_alias_wins(self, config, monkeypatch):
        monkeypatch.setenv("AUDIT_URL", AUDIT_URL)
        assert config.audit_url == AUDIT_URL

    def test_config_file_key_beats_base_url(self, config, monkeypatch):
        monkeypatch.setenv("BASE_URL", "https://gateway.example.com")
        config.audit_url = AUDIT_URL
        assert config.audit_url == AUDIT_URL

    def test_malformed_base_url_raises(self, config, monkeypatch):
        monkeypatch.setenv("BASE_URL", "gateway.example.com")
        with pytest.raises(ValueError, match="BASE_URL"):
            _ = config.audit_url

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

    def test_summary_appends_ua_family_and_size(self):
        line = _format_trace_summary({
            "trace_id": "a" * 32,
            "span_count": 1,
            "duration_ms": 387,
            "root_span": {
                "method": "GET",
                "path": "/assignments/new",
                "status_code": 200,
                "user_agent": ("Mozilla/5.0 (Windows NT 10.0) Chrome/157.0.0.0"),
                "response_headers": {"Content-Type": "text/html",
                                     "Content-Length": "6951"},
            },
        })
        assert "Chrome/157" in line
        assert "~6.8 kB" in line

    def test_summary_omits_missing_ua_and_size(self):
        line = _format_trace_summary({
            "trace_id": "a" * 32,
            "span_count": 1,
            "duration_ms": 5,
            "root_span": {"method": "GET", "path": "/", "status_code": 200},
        })
        assert "·" not in line

    def test_ua_family_variants(self):
        assert _ua_family("Mozilla/5.0 Edg/157.0.0.0") == "Edge/157"
        assert _ua_family("curl/8.12.1") == "curl/8"
        assert _ua_family("some-exotic-agent") == "some-exotic-agent"
        assert _ua_family(None) is None
        assert _ua_family("") is None

    def test_content_length_case_insensitive_and_bad_values(self):
        assert _content_length({"response_headers":
                                {"content-length": "42"}}) == 42
        assert _content_length({"response_headers":
                                {"Content-Length": "oops"}}) is None
        assert _content_length({"response_headers": {}}) is None
        assert _content_length({}) is None


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


class TestKeyStatus:
    """Key status distinguishes revoked, expired, and still-active keys."""

    def test_future_expiry_is_still_active(self):
        # The server counts a key as active when it is neither revoked
        # nor expired, so a future expiry must not read as a status.
        record = {
            "id": "k1",
            "name": "Alice",
            "owner_id": "alice@school.edu",
            "scopes": ["traces:read"],
            "expires_at": "2999-12-31T23:59:59+00:00",
            "revoked_at": None,
        }
        assert "active" in _key_status(record)

    def test_past_expiry_is_expired(self):
        record = {
            "id": "k2",
            "name": "Bob",
            "owner_id": "bob@school.edu",
            "scopes": ["traces:read"],
            "expires_at": "2000-01-01T00:00:00+00:00",
            "revoked_at": None,
        }
        assert "expired" in _key_status(record)

    def test_revoked_wins_over_expiry(self):
        record = {
            "id": "k3",
            "name": "Carol",
            "owner_id": "carol@school.edu",
            "scopes": ["traces:read"],
            "expires_at": "2000-01-01T00:00:00+00:00",
            "revoked_at": "2026-10-05T00:00:00+00:00",
        }
        assert "revoked" in _key_status(record)

    def test_no_expiry_is_active(self):
        record = {
            "id": "k4",
            "name": "Dan",
            "owner_id": "dan@school.edu",
            "scopes": ["traces:read"],
            "expires_at": None,
            "revoked_at": None,
        }
        assert "active" in _key_status(record)

    def test_unparsable_expiry_is_not_expired(self):
        record = {
            "id": "k5",
            "name": "Eve",
            "owner_id": "eve@school.edu",
            "scopes": ["traces:read"],
            "expires_at": "not-a-date",
            "revoked_at": None,
        }
        assert "active" in _key_status(record)

    def test_timestamp_parsing_handles_zulu_and_naive(self):
        assert _parse_timestamp("2026-12-31T23:59:59Z") is not None
        assert _parse_timestamp("2026-12-31T23:59:59") is not None
        assert _parse_timestamp("nonsense") is None
        assert _parse_timestamp(None) is None


class TestFailApiMessage:
    """Failed audit calls report one clean sentence plus the remedy."""

    def _message(self, error):
        with (
            mock.patch("campus_cli.audit.client.print_error") as mock_print,
            pytest.raises(typer.Exit),
        ):
            fail_api("list API keys", error)
        return mock_print.call_args[0][0]

    def test_no_double_full_stop(self):
        message = self._message(
            errors.APIError(
                status_code=403,
                error_description="Missing required scope: apikeys:read.",
            )
        )
        assert "apikeys:read.. " not in message
        assert "apikeys:read." in message

    def test_missing_stop_is_added(self):
        message = self._message(
            errors.APIError(
                status_code=400, error_description="bad request"
            )
        )
        assert "Failed to list API keys: bad request." in message

    def test_401_carries_the_relogin_remedy(self):
        message = self._message(
            errors.APIError(status_code=401, error_description="Invalid API key")
        )
        assert "Re-run 'campus audit login'" in message


class TestCredentialStoreFailures:
    """A broken credential store is reported, not raised as a traceback."""

    def test_login_reports_a_store_failure(self):
        creds = mock.Mock()
        creds.set_audit_api_key.side_effect = CredentialError("keyring locked")
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
        assert result.exit_code == 1
        assert "Failed to store the audit API key" in result.stderr

    def test_client_reports_an_unreadable_store(self, monkeypatch):
        creds = mock.Mock()
        creds.get_audit_api_key.side_effect = CredentialError("keyring locked")
        monkeypatch.setattr("campus_cli.audit.client.credentials", creds)
        with pytest.raises(typer.Exit):
            get_audit_client()


class TestKeysRevokeJson:
    """`keys revoke --json` reports the revocation as JSON."""

    def test_json_output(self):
        api = mock.MagicMock()
        with mock.patch("campus_cli.audit.keys.get_audit_client", return_value=api):
            result = CliRunner().invoke(
                app, ["audit", "keys", "revoke", "--key-id", "k1", "-y", "--json"]
            )
        assert result.exit_code == 0, result.output
        assert '"revoked": true' in result.stdout
        api.apikeys.__getitem__.assert_called_once_with("k1")


class TestKeysListDryRun:
    """The keys list snippet carries only the fields the caller set."""

    def test_no_filters_means_no_arguments(self):
        result = CliRunner().invoke(
            app, ["audit", "keys", "list", "--dry-run"]
        )
        assert result.exit_code == 0, result.output
        assert "campus_audit.apikeys.list()" in result.stdout
        assert "owner_id=" not in result.stdout
        assert "active_only=" not in result.stdout

    def test_only_the_given_filters_appear(self):
        result = CliRunner().invoke(
            app,
            [
                "audit", "keys", "list", "--owner", "alice@school.edu",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "owner_id='alice@school.edu'" in result.stdout
        assert "active_only=" not in result.stdout
        assert "limit=" not in result.stdout

    def test_all_flag_widens_active_only(self):
        result = CliRunner().invoke(
            app, ["audit", "keys", "list", "--all", "--dry-run"]
        )
        assert result.exit_code == 0, result.output
        assert "active_only=False" in result.stdout


class TestApiErrorFallbacks:
    """Failures with no description still carry their status; 422s name fields."""

    def test_missing_description_falls_back_to_status(self):
        # A proxy's HTML 502 or an empty body: APIError with no
        # description must not render as an empty message.
        error = errors.APIError(status_code=502)
        status, message = api_error_details(error)
        assert status == 502
        assert message == "HTTP 502"

    def test_field_level_errors_are_surfaced(self):
        error = errors.APIError(
            status_code=422,
            error_description="One or more fields are invalid",
            errors=[
                errors.FieldError(
                    field="scopes",
                    code="EMPTY",
                    message="must be a non-empty list",
                )
            ],
        )
        status, message = api_error_details(error)
        assert status == 422
        assert "One or more fields are invalid" in message
        assert "scopes (EMPTY: must be a non-empty list)" in message

    def test_field_errors_append_to_status_fallback(self):
        error = errors.APIError(
            status_code=422,
            errors=[
                errors.FieldError(field="rate_limit", code="INVALID", message=""),
            ],
        )
        _, message = api_error_details(error)
        assert message.startswith("HTTP 422")
        assert "rate_limit (INVALID)" in message


class TestMismatchMessage:
    """The guard and status share one mismatch sentence (#62)."""

    def test_mismatch_sentence_matches_the_guard(self):
        from campus_cli.audit.client import mismatch_message

        message = mismatch_message("https://audit-old.test", AUDIT_URL)
        assert message == (
            "Stored audit API key was stored for https://audit-old.test"
            f" but the CLI is targeting {AUDIT_URL}."
            f" Re-run 'campus audit login' against {AUDIT_URL}."
        )

    def test_matching_or_missing_urls_give_none(self):
        from campus_cli.audit.client import mismatch_message

        assert mismatch_message(AUDIT_URL, AUDIT_URL + "/") is None
        assert mismatch_message(None, AUDIT_URL) is None
        assert mismatch_message(AUDIT_URL, None) is None


class TestAuditStatusCmd:
    """campus audit status is a purely offline local view (#62)."""

    def _invoke(self, creds, *args):
        with (
            mock.patch("campus_cli.audit.login.credentials", creds),
            mock.patch.dict(
                "os.environ", {"CAMPUS_AUDIT_URL": AUDIT_URL}
            ),
        ):
            return CliRunner().invoke(app, ["audit", "status", *args])

    def test_makes_no_network_call(self):
        creds = mock.Mock()
        creds.get_audit_api_key.return_value = "audit_v1_k"
        creds.get_audit_key_url.return_value = AUDIT_URL
        creds.get_audit_key_stored_at.return_value = None
        with (
            mock.patch("campus_cli.audit.login.credentials", creds),
            mock.patch.dict("os.environ", {"CAMPUS_AUDIT_URL": AUDIT_URL}),
            mock.patch(
                "campus_python.CampusRequest",
                side_effect=AssertionError("status must not build a client"),
            ),
        ):
            result = CliRunner().invoke(app, ["audit", "status"])
        assert result.exit_code == 0, result.output

    def test_not_logged_in_exits_1(self):
        creds = mock.Mock()
        creds.get_audit_api_key.return_value = None
        creds.get_audit_key_url.return_value = None
        creds.get_audit_key_stored_at.return_value = None
        result = self._invoke(creds)
        assert result.exit_code == 1
        assert "Not logged in" in result.output

    def test_stored_key_reports_binding_and_target(self):
        creds = mock.Mock()
        creds.get_audit_api_key.return_value = "audit_v1_k"
        creds.get_audit_key_url.return_value = AUDIT_URL
        creds.get_audit_key_stored_at.return_value = "2026-10-20T04:00:00+00:00"
        result = self._invoke(creds)
        assert result.exit_code == 0, result.output
        assert "Audit API key stored." in result.stdout
        assert AUDIT_URL in result.stdout
        assert "Stored:" in result.stdout

    def test_mismatch_is_called_out_like_the_guard(self):
        creds = mock.Mock()
        creds.get_audit_api_key.return_value = "audit_v1_k"
        creds.get_audit_key_url.return_value = "https://audit-old.test"
        creds.get_audit_key_stored_at.return_value = None
        result = self._invoke(creds)
        # Informational: exit 0, but the standing mismatch sentence
        # (print_error writes stderr; result.output mixes both streams).
        assert result.exit_code == 0, result.output
        assert "was stored for https://audit-old.test" in result.output
        assert "Re-run 'campus audit login'" in result.output

    def test_unknown_stored_at_is_reported_as_unknown(self):
        creds = mock.Mock()
        creds.get_audit_api_key.return_value = "audit_v1_k"
        creds.get_audit_key_url.return_value = AUDIT_URL
        creds.get_audit_key_stored_at.return_value = None
        result = self._invoke(creds)
        assert result.exit_code == 0, result.output
        assert "Stored: unknown" in result.stdout

    def test_json_shape(self):
        creds = mock.Mock()
        creds.get_audit_api_key.return_value = "audit_v1_k"
        creds.get_audit_key_url.return_value = AUDIT_URL
        creds.get_audit_key_stored_at.return_value = "2026-10-20T04:00:00+00:00"
        result = self._invoke(creds, "--json")
        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload == {
            "authenticated": True,
            "audit_url": AUDIT_URL,
            "key_url": AUDIT_URL,
            "endpoint_match": True,
            "stored_at": "2026-10-20T04:00:00+00:00",
        }

    def test_json_not_logged_in_still_parses(self):
        creds = mock.Mock()
        creds.get_audit_api_key.return_value = None
        creds.get_audit_key_url.return_value = None
        creds.get_audit_key_stored_at.return_value = None
        result = self._invoke(creds, "--json")
        assert result.exit_code == 1
        payload = json.loads(result.stdout)
        assert payload["authenticated"] is False

    def test_invalid_env_still_reports_the_local_state(self, tmp_path):
        creds = mock.Mock()
        creds.get_audit_api_key.return_value = "audit_v1_k"
        creds.get_audit_key_url.return_value = AUDIT_URL
        creds.get_audit_key_stored_at.return_value = None
        isolated = Config(config_path=tmp_path / "config.json")
        with (
            mock.patch("campus_cli.audit.login.credentials", creds),
            mock.patch("campus_cli.audit.login.config", isolated),
            mock.patch.dict("os.environ", {"ENV": "qa"}),
        ):
            result = CliRunner().invoke(app, ["audit", "status"])
        assert result.exit_code == 0, result.output
        assert "unknown" in result.stdout

    def test_store_failure_is_reported(self):
        creds = mock.Mock()
        creds.get_audit_api_key.side_effect = CredentialError("keyring locked")
        result = self._invoke(creds)
        assert result.exit_code == 1
        assert "Failed to read the stored audit API key" in result.stderr


class TestAuditJsonShapes:
    """Every --json output prints the server response verbatim (#61)."""

    def test_keys_list_json_keeps_the_envelope(self):
        server_response = {
            "api_keys": [{"id": "k1", "name": "Alice"}],
            "count": 1,
        }
        api = mock.Mock()
        api.apikeys.list.return_value = server_response
        with mock.patch("campus_cli.audit.keys.get_audit_client", return_value=api):
            result = CliRunner().invoke(app, ["audit", "keys", "list", "--json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == server_response

    def test_traces_list_json_keeps_the_envelope(self):
        server_response = {
            "traces": [{"trace_id": "a" * 32}],
            "cursor": {"next": None, "has_more": False},
        }
        api = mock.Mock()
        api.traces.list.return_value = server_response
        with (
            mock.patch("campus_cli.audit.traces.get_audit_client", return_value=api),
            mock.patch.dict("os.environ", {"CAMPUS_AUDIT_URL": AUDIT_URL}),
        ):
            result = CliRunner().invoke(app, ["audit", "traces", "list", "--json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == server_response

    def test_json_values_longer_than_the_console_width_round_trip(self):
        """--json never soft-wraps values to the console width (#69).

        Rich's display renderable used to insert literal newlines into
        long string values, corrupting machine-readable output.
        """
        long_name = "a" * 110
        server_response = {
            "api_keys": [{"id": "k1", "name": long_name}],
            "count": 1,
        }
        api = mock.Mock()
        api.apikeys.list.return_value = server_response
        with mock.patch("campus_cli.audit.keys.get_audit_client", return_value=api):
            result = CliRunner().invoke(app, ["audit", "keys", "list", "--json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == server_response
        assert "\n" not in json.loads(result.stdout)["api_keys"][0]["name"]


class TestTracesSearchJourney:
    """traces search forwards --journey as the journey_id kwarg (#63)."""

    def _invoke_search(self, args):
        api = mock.Mock()
        api.traces.search.return_value = {"traces": []}
        with (
            mock.patch("campus_cli.audit.traces.get_audit_client", return_value=api),
            mock.patch.dict("os.environ", {"CAMPUS_AUDIT_URL": AUDIT_URL}),
        ):
            result = CliRunner().invoke(app, ["audit", "traces", "search", *args])
        return result, api

    def test_journey_is_forwarded_as_journey_id(self):
        result, api = self._invoke_search([
            "--journey", "jrn-orientation-2026", "--path", "/auth/v1/token",
        ])

        assert result.exit_code == 0, result.output
        assert api.traces.search.call_args.kwargs["journey_id"] == \
            "jrn-orientation-2026"

    def test_absent_journey_is_none(self):
        """Without --journey, journey_id is passed as None like the rest."""
        result, api = self._invoke_search(["--user", "alice@school.edu"])

        assert result.exit_code == 0, result.output
        assert api.traces.search.call_args.kwargs["journey_id"] is None


class _Sdk011Response:
    """Stands in for SDK v0.11.0's CampusResponse wrapper (campus-cli#112).

    The v0.11.0 query methods are annotated -> JsonResponse but return
    this wrapper; parsed payloads come out of .json().
    """

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _Sdk011TracesList:
    """Traces.list with the exact SDK v0.11.0 signature (campus-cli#112).

    The real list() takes no cursor kwarg — passing one is the TypeError
    bug — so the fake carries the strict signature instead of a Mock.
    """

    def __init__(self, payload):
        self._payload = payload
        self.calls: list[dict] = []

    def list(self, *, since=None, until=None, limit=50):
        self.calls.append({"since": since, "until": until, "limit": limit})
        return _Sdk011Response(self._payload)


class TestTracesSdk011Compat:
    """Traces commands speak SDK v0.11.0's shapes (campus-cli#112).

    The pinned v0.11.0 wheel: list() has no cursor kwarg, query methods
    return CampusResponse wrappers (not the parsed payloads their
    JsonResponse annotation suggests), and the single-trace accessor is
    get_tree() — Resource.get is gone. The CLI unwraps .json() before
    rendering and passes plain-dict payloads through untouched.
    """

    PAGE = {
        "traces": [{"trace_id": "a" * 32}],
        "cursor": {"next": "tok-2", "has_more": True},
    }

    def _invoke(self, argv, api):
        with (
            mock.patch("campus_cli.audit.traces.get_audit_client", return_value=api),
            mock.patch.dict("os.environ", {"CAMPUS_AUDIT_URL": AUDIT_URL}),
        ):
            return CliRunner().invoke(app, ["audit", "traces", *argv])

    def test_list_json_unwraps_sdk_response_wrapper(self):
        api = mock.Mock()
        api.traces = _Sdk011TracesList(self.PAGE)

        result = self._invoke(["list", "--json"], api)

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == self.PAGE

    def test_list_human_output_renders_without_cursor_hint(self):
        """A list page cannot be continued via --cursor (no such SDK
        kwarg), so the continuation hint must not offer one."""
        api = mock.Mock()
        api.traces = _Sdk011TracesList(self.PAGE)

        result = self._invoke(["list"], api)

        assert result.exit_code == 0, result.output
        assert "Showing 1 trace(s)" in result.output
        assert "--cursor" not in result.output

    def test_list_does_not_pass_cursor_to_sdk(self):
        api = mock.Mock()
        api.traces = _Sdk011TracesList(self.PAGE)

        result = self._invoke(["list"], api)

        assert result.exit_code == 0, result.output
        assert api.traces.calls == [{"since": None, "until": None, "limit": None}]

    def test_list_rejects_removed_cursor_option(self):
        """The removed --cursor must be a usage error, not a silent no-op."""
        api = mock.Mock()
        api.traces = _Sdk011TracesList(self.PAGE)

        result = self._invoke(["list", "--cursor", "tok-1"], api)

        assert result.exit_code == 2
        assert api.traces.calls == []

    def test_search_json_unwraps_sdk_response_wrapper(self):
        api = mock.Mock()
        api.traces.search.return_value = _Sdk011Response(self.PAGE)

        result = self._invoke(
            ["search", "--since", "2026-11-17", "--json"], api
        )

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == self.PAGE

    def test_search_human_output_keeps_cursor_hint(self):
        api = mock.Mock()
        api.traces.search.return_value = _Sdk011Response(self.PAGE)

        result = self._invoke(["search"], api)

        assert result.exit_code == 0, result.output
        assert "--cursor tok-2" in result.output

    def test_search_forwards_cursor_to_sdk(self):
        api = mock.Mock()
        api.traces.search.return_value = _Sdk011Response({"traces": []})

        result = self._invoke(["search", "--cursor", "tok-1"], api)

        assert result.exit_code == 0, result.output
        assert api.traces.search.call_args.kwargs["cursor"] == "tok-1"

    def test_get_calls_get_tree_and_unwraps(self):
        """Resource.get is gone in v0.11.0 — the accessor is get_tree()."""
        tree = {"trace_id": "b" * 32, "root_span": {"path": "/x"}}
        api = mock.MagicMock()
        api.traces.__getitem__.return_value.get_tree.return_value = \
            _Sdk011Response(tree)

        result = self._invoke(["get", "--trace-id", "b" * 32, "--json"], api)

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == tree
        api.traces.__getitem__.return_value.get_tree.assert_called_once()


class TestKeysRole:
    """`campus audit keys new/update --role` grants a named role (#67).

    The role is the service's own vocabulary (campus#918); the CLI
    passes the name through and lets the server refuse an unknown one.
    """

    def _invoke_new(self, args):
        api = mock.Mock()
        api.apikeys.new.return_value = {"id": "k1", "api_key": "audit_v1_x"}
        with (
            mock.patch("campus_cli.audit.keys.get_audit_client", return_value=api),
            mock.patch.dict("os.environ", {"CAMPUS_AUDIT_URL": AUDIT_URL}),
        ):
            result = CliRunner().invoke(app, ["audit", "keys", "new", *args])
        return result, api

    def test_role_is_passed_and_no_scopes(self):
        result, api = self._invoke_new([
            "--name", "Alice", "--owner", "alice@school.edu",
            "--role", "traces-viewer",
        ])

        assert result.exit_code == 0, result.output
        kwargs = api.apikeys.new.call_args.kwargs
        assert kwargs["role"] == "traces-viewer"
        assert kwargs["scopes"] is None

    def test_scopes_still_work(self):
        result, api = self._invoke_new([
            "--name", "Alice", "--owner", "alice@school.edu",
            "--scope", "traces:read",
        ])

        assert result.exit_code == 0, result.output
        kwargs = api.apikeys.new.call_args.kwargs
        assert kwargs["scopes"] == ["traces:read"]
        assert kwargs["role"] is None

    def test_role_and_scopes_together_are_refused(self):
        result, api = self._invoke_new([
            "--name", "Alice", "--owner", "alice@school.edu",
            "--role", "traces-viewer", "--scope", "traces:read",
        ])

        assert result.exit_code == 1
        assert "not both" in result.output
        api.apikeys.new.assert_not_called()

    def test_neither_role_nor_scopes_is_refused(self):
        result, api = self._invoke_new([
            "--name", "Alice", "--owner", "alice@school.edu",
        ])

        assert result.exit_code == 1
        assert "--role" in result.output
        api.apikeys.new.assert_not_called()

    def test_update_accepts_a_role(self):
        api = mock.MagicMock()
        api.apikeys.__getitem__.return_value.update.return_value = {"id": "k1"}
        with (
            mock.patch("campus_cli.audit.keys.get_audit_client", return_value=api),
            mock.patch.dict("os.environ", {"CAMPUS_AUDIT_URL": AUDIT_URL}),
        ):
            result = CliRunner().invoke(app, [
                "audit", "keys", "update", "--key-id", "k1",
                "--role", "traces-searcher",
            ])

        assert result.exit_code == 0, result.output
        kwargs = api.apikeys.__getitem__.return_value.update.call_args.kwargs
        assert kwargs["role"] == "traces-searcher"
        assert kwargs["scopes"] is None

    def test_update_refuses_role_and_scopes_together(self):
        api = mock.MagicMock()
        with (
            mock.patch("campus_cli.audit.keys.get_audit_client", return_value=api),
            mock.patch.dict("os.environ", {"CAMPUS_AUDIT_URL": AUDIT_URL}),
        ):
            result = CliRunner().invoke(app, [
                "audit", "keys", "update", "--key-id", "k1",
                "--role", "traces-viewer", "--scope", "traces:read",
            ])

        assert result.exit_code == 1
        assert "not both" in result.output
