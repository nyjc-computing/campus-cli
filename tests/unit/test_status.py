"""Unit tests for `campus auth status` (#45): assembly, formatting, probe.

All tests run against a mocked credential store and a mocked probe, so
no test ever touches the network.
"""

import json
from datetime import datetime, timedelta, timezone
from unittest import mock

import requests
from typer.testing import CliRunner

from campus_cli.auth.status import (
    VALIDITY_INVALID,
    VALIDITY_NOT_CHECKED,
    VALIDITY_UNKNOWN,
    VALIDITY_UNREACHABLE,
    VALIDITY_VALID,
    build_status,
    probe_token_validity,
)
from campus_cli.cli import app

runner = CliRunner()


def _mock_credentials(**overrides):
    """Build a credential-store mock describing an authenticated user."""
    creds = mock.Mock()
    creds.get_token.return_value = "test_access_token"
    creds.get_refresh_token.return_value = "test_refresh_token"
    # Default expiry: one hour out, so is_token_expired-style parsing
    # has a valid timestamp to work with.
    creds.get_token_expires_at.return_value = (
        datetime.now(timezone.utc) + timedelta(hours=1)
    ).isoformat()
    creds.is_token_expired.return_value = False
    creds.get_token_auth_url.return_value = (
        "https://auth-minted.example.com/auth/v1"
    )
    creds.get_token_scopes.return_value = ["read", "write"]
    creds.get_token_user_id.return_value = "user-alice@example.com"
    for key, value in overrides.items():
        setattr(creds, key, mock.Mock(return_value=value))
    return creds


class TestProbeTokenValidity:
    """The probe maps status codes to the three-state machine."""

    def _get(self, status_code):
        response = mock.Mock(spec=requests.Response)
        response.status_code = status_code
        with mock.patch(
            "campus_cli.auth.status.requests.get", return_value=response
        ) as mock_get:
            result = probe_token_validity(
                "https://auth.example.com/auth/v1", "tok-123"
            )
        mock_get.assert_called_once_with(
            "https://auth.example.com/auth/v1/users/",
            headers={"Authorization": "Bearer tok-123"},
            timeout=mock.ANY,
        )
        return result

    def test_forbidden_means_valid(self):
        """403 FORBIDDEN: authenticated, just not allowed to list users."""
        assert self._get(403) == (VALIDITY_VALID, None)

    def test_ok_means_valid(self):
        """200: a users:read token that listed users is valid too."""
        assert self._get(200) == (VALIDITY_VALID, None)

    def test_unauthorized_means_invalid(self):
        """401 UNAUTHORIZED: the server rejected the token."""
        assert self._get(401) == (VALIDITY_INVALID, None)

    def test_other_status_is_unknown(self):
        """Anything else (e.g. 5xx) is inconclusive, with a note."""
        validity, note = self._get(500)
        assert validity == VALIDITY_UNKNOWN
        assert "500" in note

    def test_network_error_is_unreachable(self):
        """Connection failures are their own state, not a verdict."""
        with mock.patch(
            "campus_cli.auth.status.requests.get",
            side_effect=requests.ConnectionError("connection refused"),
        ):
            validity, note = probe_token_validity(
                "https://auth.example.com/auth/v1", "tok-123"
            )
        assert validity == VALIDITY_UNREACHABLE
        assert "connection refused" in note


class TestBuildStatusOffline:
    """--offline assembles everything the store holds, network-free."""

    def test_offline_reports_stored_identity_without_probe(self):
        """The full identity block comes from the store; no probe call."""
        creds = _mock_credentials()
        with (
            mock.patch("campus_cli.auth.common.credentials", creds),
            mock.patch(
                "campus_cli.auth.status.probe_token_validity"
            ) as mock_probe,
        ):
            status = build_status(offline=True)

        mock_probe.assert_not_called()
        assert status["authenticated"] is True
        assert status["client_id"] == "guest"
        assert status["user_id"] == "user-alice@example.com"
        assert status["scopes"] == ["read", "write"]
        assert status["token_validity"] == VALIDITY_NOT_CHECKED
        assert status["probe_url"] is None
        assert status["expires_in_seconds"] is not None
        assert 3500 < status["expires_in_seconds"] <= 3600

    def test_offline_keeps_get_token_status_fields(self):
        """The pre-#45 --json keys stay present and unchanged."""
        creds = _mock_credentials()
        with mock.patch("campus_cli.auth.common.credentials", creds):
            status = build_status(offline=True)

        assert status["auth_url"]
        assert status["token_auth_url"] == (
            "https://auth-minted.example.com/auth/v1"
        )
        # The mock's issuing endpoint is never the resolved target,
        # so the mismatch verdict is deterministically False here.
        assert status["endpoint_match"] is False
        assert status["can_refresh"] is True
        assert status["expires_at"] == creds.get_token_expires_at.return_value

    def test_unrecorded_scopes_and_principal_are_none(self):
        """Credentials stored before #45 read as unknown, not empty."""
        creds = _mock_credentials(
            get_token_scopes=None, get_token_user_id=None
        )
        with mock.patch("campus_cli.auth.common.credentials", creds):
            status = build_status(offline=True)

        assert status["scopes"] is None
        assert status["user_id"] is None


class TestBuildStatusProbe:
    """The default path probes the endpoint the token is bound to."""

    def test_probe_targets_issuing_endpoint(self):
        """A bound token is checked against the endpoint that minted it."""
        creds = _mock_credentials()
        with (
            mock.patch("campus_cli.auth.common.credentials", creds),
            mock.patch(
                "campus_cli.auth.status.probe_token_validity",
                return_value=(VALIDITY_VALID, None),
            ) as mock_probe,
        ):
            status = build_status(offline=False)

        mock_probe.assert_called_once_with(
            "https://auth-minted.example.com/auth/v1", "test_access_token"
        )
        assert status["token_validity"] == VALIDITY_VALID
        assert status["probe_url"] == (
            "https://auth-minted.example.com/auth/v1"
        )

    def test_unbound_token_probes_current_target(self):
        """Pre-endpoint-binding credentials fall back to the target."""
        creds = _mock_credentials(get_token_auth_url=None)
        with (
            mock.patch("campus_cli.auth.common.credentials", creds),
            mock.patch(
                "campus_cli.auth.status.probe_token_validity",
                return_value=(VALIDITY_VALID, None),
            ) as mock_probe,
        ):
            status = build_status(offline=False)

        assert status["probe_url"] == status["auth_url"]
        assert mock_probe.call_args.args[0] == status["auth_url"]

    def test_unreachable_probe_carries_note(self):
        """The probe's note lands in the payload for both outputs."""
        creds = _mock_credentials()
        with (
            mock.patch("campus_cli.auth.common.credentials", creds),
            mock.patch(
                "campus_cli.auth.status.probe_token_validity",
                return_value=(VALIDITY_UNREACHABLE, "connection refused"),
            ),
        ):
            status = build_status(offline=False)

        assert status["token_validity"] == VALIDITY_UNREACHABLE
        assert "connection refused" in status["probe_note"]

    def test_not_authenticated_skips_probe_and_identity(self):
        """No stored token: no probe, no identity, no validity verdict."""
        creds = _mock_credentials(get_token=None)
        with (
            mock.patch("campus_cli.auth.common.credentials", creds),
            mock.patch(
                "campus_cli.auth.status.probe_token_validity"
            ) as mock_probe,
        ):
            status = build_status(offline=False)

        mock_probe.assert_not_called()
        assert status["authenticated"] is False
        assert status["user_id"] is None
        assert status["scopes"] is None
        assert status["token_validity"] is None


class TestStatusCliOutput:
    """Human and JSON rendering of the assembled payload."""

    def test_json_includes_all_fields(self):
        """--json emits the same fields machine-readably, exit 0."""
        creds = _mock_credentials()
        with (
            mock.patch("campus_cli.auth.common.credentials", creds),
            mock.patch(
                "campus_cli.auth.status.probe_token_validity",
                return_value=(VALIDITY_VALID, None),
            ),
        ):
            result = runner.invoke(app, ["auth", "status", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["authenticated"] is True
        assert payload["client_id"] == "guest"
        assert payload["user_id"] == "user-alice@example.com"
        assert payload["scopes"] == ["read", "write"]
        assert payload["token_validity"] == "valid"

    def test_human_output_shows_client_principal_and_scopes(self):
        """The terminal report names client, principal and scopes."""
        creds = _mock_credentials()
        with (
            mock.patch("campus_cli.auth.common.credentials", creds),
            mock.patch(
                "campus_cli.auth.status.probe_token_validity",
                return_value=(VALIDITY_VALID, None),
            ),
        ):
            result = runner.invoke(app, ["auth", "status"])

        assert result.exit_code == 0
        assert "Authenticated" in result.stdout
        assert "guest" in result.stdout
        assert "user-alice@example.com" in result.stdout
        assert "read" in result.stdout
        assert "valid" in result.stdout

    def test_human_output_notes_unrecorded_scopes(self):
        """Pre-#45 credentials say 'not recorded', never an empty list."""
        creds = _mock_credentials(
            get_token_scopes=None, get_token_user_id=None
        )
        with (
            mock.patch("campus_cli.auth.common.credentials", creds),
            mock.patch(
                "campus_cli.auth.status.probe_token_validity",
                return_value=(VALIDITY_VALID, None),
            ),
        ):
            result = runner.invoke(app, ["auth", "status", "--offline"])

        assert result.exit_code == 0
        assert "not recorded" in result.stdout

    def test_human_output_renders_empty_scope_list(self):
        """A token recorded with zero scopes prints '(none)'."""
        creds = _mock_credentials(get_token_scopes=[])
        with (
            mock.patch("campus_cli.auth.common.credentials", creds),
            mock.patch(
                "campus_cli.auth.status.probe_token_validity",
                return_value=(VALIDITY_VALID, None),
            ),
        ):
            result = runner.invoke(app, ["auth", "status", "--offline"])

        assert result.exit_code == 0
        assert "(none)" in result.stdout

    def test_offline_flag_skips_the_probe(self):
        """--offline says the check was skipped and never calls it."""
        creds = _mock_credentials()
        with (
            mock.patch("campus_cli.auth.common.credentials", creds),
            mock.patch(
                "campus_cli.auth.status.probe_token_validity"
            ) as mock_probe,
        ):
            result = runner.invoke(app, ["auth", "status", "--offline"])

        mock_probe.assert_not_called()
        assert result.exit_code == 0
        assert "skipped" in result.stdout

    def test_invalid_token_exits_nonzero_with_remedy(self):
        """A 401 verdict is actionable: exit 1 and name re-login."""
        creds = _mock_credentials()
        with (
            mock.patch("campus_cli.auth.common.credentials", creds),
            mock.patch(
                "campus_cli.auth.status.probe_token_validity",
                return_value=(VALIDITY_INVALID, None),
            ),
        ):
            result = runner.invoke(app, ["auth", "status"])

        assert result.exit_code == 1
        assert "invalid" in result.stdout
        assert "campus auth login" in result.stdout

    def test_invalid_token_nonzero_in_json_mode_too(self):
        """--json keeps the same exit contract for scripts."""
        creds = _mock_credentials()
        with (
            mock.patch("campus_cli.auth.common.credentials", creds),
            mock.patch(
                "campus_cli.auth.status.probe_token_validity",
                return_value=(VALIDITY_INVALID, None),
            ),
        ):
            result = runner.invoke(app, ["auth", "status", "--json"])

        assert result.exit_code == 1
        payload = json.loads(result.stdout)
        assert payload["token_validity"] == "invalid"

    def test_unreachable_server_is_nonfatal(self):
        """Network failure warns but exits 0: identity still printed."""
        creds = _mock_credentials()
        with (
            mock.patch("campus_cli.auth.common.credentials", creds),
            mock.patch(
                "campus_cli.auth.status.probe_token_validity",
                return_value=(VALIDITY_UNREACHABLE, "connection refused"),
            ),
        ):
            result = runner.invoke(app, ["auth", "status"])

        assert result.exit_code == 0
        # Rich wraps long lines; compare on normalized whitespace.
        flattened = " ".join(result.stdout.split())
        assert "could not reach server" in flattened
        assert "Authenticated" in result.stdout

    def test_not_logged_in_human_mode(self):
        """No stored credential: friendly message and exit 1."""
        creds = _mock_credentials(get_token=None)
        with mock.patch("campus_cli.auth.common.credentials", creds):
            result = runner.invoke(app, ["auth", "status"])

        assert result.exit_code == 1
        assert "Not authenticated" in result.stdout
        assert "campus auth login" in result.stdout

    def test_not_logged_in_json_mode(self):
        """No stored credential with --json: structured, still exit 1."""
        creds = _mock_credentials(get_token=None)
        with mock.patch("campus_cli.auth.common.credentials", creds):
            result = runner.invoke(app, ["auth", "status", "--json"])

        assert result.exit_code == 1
        payload = json.loads(result.stdout)
        assert payload["authenticated"] is False
        assert payload["token_validity"] is None
