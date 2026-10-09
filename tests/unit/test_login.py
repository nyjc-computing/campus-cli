"""Unit tests for the login module's device-code error handling."""

from unittest import mock

import pytest
import requests
from campus_python import errors

from campus_cli.auth.common import revoke_token
from campus_cli.auth.login import (
    DeviceAuthError,
    poll_for_token,
    request_device_code,
)


def _http_error(error_body):
    """Build an HTTPError whose response carries the given JSON error body."""
    response = mock.Mock(spec=requests.Response)
    if error_body is None:
        response.json.side_effect = ValueError("no json body")
    else:
        response.json.return_value = error_body
    return requests.HTTPError("400 Client Error", response=response)


def test_request_device_code_surfaces_structured_error():
    """Campus-style structured errors surface their message."""
    error = _http_error({
        "error": {
            "code": "AUTH_INVALID_REQUEST",
            "message": "Client 'guest' not found",
        }
    })
    with (
        mock.patch("campus_cli.auth.login.requests.post", side_effect=error),
        pytest.raises(DeviceAuthError, match="Client 'guest' not found"),
    ):
        request_device_code()


def test_request_device_code_falls_back_to_code_without_message():
    """Structured errors without a message surface the error code."""
    error = _http_error({"error": {"code": "AUTH_SERVER_ERROR"}})
    with (
        mock.patch("campus_cli.auth.login.requests.post", side_effect=error),
        pytest.raises(DeviceAuthError, match="AUTH_SERVER_ERROR"),
    ):
        request_device_code()


def test_request_device_code_falls_back_on_plain_oauth_error():
    """Plain OAuth 2.0 {"error": "..."} bodies surface the error string."""
    error = _http_error({"error": "invalid_client"})
    with (
        mock.patch("campus_cli.auth.login.requests.post", side_effect=error),
        pytest.raises(DeviceAuthError, match="invalid_client"),
    ):
        request_device_code()


def test_request_device_code_falls_back_on_non_json_body():
    """Non-JSON responses degrade to the original exception text."""
    error = _http_error(None)
    with (
        mock.patch("campus_cli.auth.login.requests.post", side_effect=error),
        pytest.raises(DeviceAuthError, match="400 Client Error"),
    ):
        request_device_code()


def test_request_device_code_network_error():
    """Connection errors (no response attached) keep the exception text."""
    with (
        mock.patch(
            "campus_cli.auth.login.requests.post",
            side_effect=requests.ConnectionError("connection refused"),
        ),
        pytest.raises(DeviceAuthError, match="connection refused"),
    ):
        request_device_code()


def test_request_device_code_passes_scope_through():
    """Requested scopes ride along as the RFC 6749 scope parameter (#865)."""
    with mock.patch(
        "campus_cli.auth.login.requests.post"
    ) as mock_post, mock.patch(
        "campus_cli.auth.login.requests.Response.raise_for_status"
    ):
        mock_post.return_value.json.return_value = {"device_code": "dc"}
        request_device_code(scopes=["clients:read", "clients:write"])

    _, kwargs = mock_post.call_args
    assert kwargs["data"]["scope"] == "clients:read clients:write"


def test_request_device_code_omits_scope_when_absent():
    """No --scope means no scope parameter: the server default applies."""
    with mock.patch(
        "campus_cli.auth.login.requests.post"
    ) as mock_post, mock.patch(
        "campus_cli.auth.login.requests.Response.raise_for_status"
    ):
        mock_post.return_value.json.return_value = {"device_code": "dc"}
        request_device_code()

    _, kwargs = mock_post.call_args
    assert "scope" not in kwargs["data"]


def test_request_device_code_invalid_scope_appends_allowlist_hint():
    """invalid_scope failures name the operator remedy (#36)."""
    error = _http_error({
        "error": {
            "code": "AUTH_INVALID_SCOPE",
            "message": (
                "Requested scopes not allowed for this client:"
                " clients:write"
            ),
            "details": {"oauth_error": "invalid_scope"},
        }
    })
    with (
        mock.patch("campus_cli.auth.login.requests.post", side_effect=error),
        pytest.raises(
            DeviceAuthError,
            match="outside this CLI client's registered allowlist"
            ".*campus client update --client-id",
        ),
    ):
        request_device_code(scopes=["clients:write"])


def test_request_device_code_plain_invalid_scope_appends_allowlist_hint():
    """Plain OAuth 2.0 invalid_scope bodies get the same hint."""
    error = _http_error({"error": "invalid_scope"})
    with (
        mock.patch("campus_cli.auth.login.requests.post", side_effect=error),
        pytest.raises(
            DeviceAuthError, match="allowlist.*--allowed-scope"
        ),
    ):
        request_device_code(scopes=["clients:write"])


def test_request_device_code_generic_error_has_no_allowlist_hint():
    """Only invalid_scope failures carry the operator remedy."""
    error = _http_error({
        "error": {
            "code": "AUTH_INVALID_REQUEST",
            "message": "Client 'guest' not found",
            "details": {"oauth_error": "invalid_client"},
        }
    })
    with (
        mock.patch("campus_cli.auth.login.requests.post", side_effect=error),
        pytest.raises(DeviceAuthError, match="Client 'guest' not found")
        as exc_info,
    ):
        request_device_code()

    assert "allowlist" not in str(exc_info.value)


def test_revoke_token_sends_rfc7009_payload_and_reports_success():
    """A clean library call confirms revocation with the RFC 7009 args."""
    with mock.patch.multiple(
        "campus_python", AuthRoot=mock.DEFAULT, CampusRequest=mock.DEFAULT
    ) as mocked:
        auth_root = mocked["AuthRoot"].return_value
        assert revoke_token("tok-123", "refresh_token") is True

    auth_root.oauth.revoke.assert_called_once_with(
        "tok-123", client_id="guest", token_type_hint="refresh_token"
    )
    mocked["CampusRequest"].assert_called_once_with(
        base_url=mock.ANY, mode="device", timeout=10
    )


def test_revoke_token_reports_failure_on_http_error():
    """API errors (e.g. a deployment without the endpoint) mean not revoked."""
    with mock.patch.multiple(
        "campus_python", AuthRoot=mock.DEFAULT, CampusRequest=mock.DEFAULT
    ) as mocked:
        auth_root = mocked["AuthRoot"].return_value
        auth_root.oauth.revoke.side_effect = errors.NotFoundError(
            status_code=404, error_description="no revoke endpoint"
        )
        assert revoke_token("tok-123", "access_token") is False


def test_revoke_token_reports_failure_on_network_error():
    """Network errors degrade to False instead of raising from logout."""
    with mock.patch.multiple(
        "campus_python", AuthRoot=mock.DEFAULT, CampusRequest=mock.DEFAULT
    ) as mocked:
        auth_root = mocked["AuthRoot"].return_value
        auth_root.oauth.revoke.side_effect = requests.ConnectionError(
            "connection refused"
        )
        assert revoke_token("tok-123", "refresh_token") is False


def test_revoke_token_reports_failure_when_library_unavailable():
    """A missing client library degrades to False (logout still clears)."""
    with mock.patch.dict("sys.modules", {"campus_python": None}):
        assert revoke_token("tok-123", "refresh_token") is False


def test_revoke_token_targets_issuing_endpoint_when_given():
    """auth_url overrides the current target for the revocation request."""
    with mock.patch.multiple(
        "campus_python", AuthRoot=mock.DEFAULT, CampusRequest=mock.DEFAULT
    ) as mocked:
        assert revoke_token(
            "tok-123",
            "access_token",
            auth_url="https://auth-old.example.com/auth/v1",
        ) is True

    mocked["CampusRequest"].assert_called_once_with(
        base_url="https://auth-old.example.com/auth/v1",
        mode="device",
        timeout=10,
    )


def _oauth_400(oauth_error):
    """Build a 400 response carrying Campus's structured oauth_error body."""
    response = mock.Mock(spec=requests.Response, status_code=400)
    response.json.return_value = {
        "error": {
            "code": "AUTH_DEVICE_FLOW",
            "message": "oauth error",
            "details": {"oauth_error": oauth_error},
        }
    }
    return response


def test_poll_for_token_slow_down_persists_increased_interval():
    """slow_down raises the poll interval for the rest of the flow (RFC 8628)."""
    responses = [
        _oauth_400("authorization_pending"),
        _oauth_400("slow_down"),
        _oauth_400("slow_down"),
        _oauth_400("access_denied"),
    ]
    with (
        mock.patch("campus_cli.auth.login.requests.post", side_effect=responses),
        mock.patch("campus_cli.auth.login.time.sleep") as mock_sleep,
        pytest.raises(DeviceAuthError, match="denied"),
    ):
        poll_for_token("device_code", interval=5, max_attempts=10)

    assert [c.args[0] for c in mock_sleep.call_args_list] == [5, 10, 15]


def test_poll_for_token_clamps_zero_interval():
    """A zero interval from the server is clamped to 1s, not zero-divided."""
    responses = [_oauth_400("authorization_pending")] * 3
    with (
        mock.patch("campus_cli.auth.login.requests.post", side_effect=responses),
        mock.patch("campus_cli.auth.login.time.sleep") as mock_sleep,
        pytest.raises(DeviceAuthError, match="timed out"),
    ):
        poll_for_token("device_code", interval=0, max_attempts=3)

    assert [c.args[0] for c in mock_sleep.call_args_list] == [1, 1, 1]


def _run_login_with_token_data(token_data):
    """Drive login_cmd through a mocked device flow with token_data.

    Returns the mocked credential store so tests can assert what was
    persisted.
    """
    from typer.testing import CliRunner

    from campus_cli.cli import app

    device_data = {
        "device_code": "dc",
        "user_code": "ABCD-EFGH",
        "verification_uri": "https://auth.example.com/activate",
        "interval": 1,
        "expires_in": 300,
    }
    creds = mock.Mock()
    creds.get_token.return_value = None  # no short-circuit
    with (
        mock.patch("campus_cli.auth.login.credentials", creds),
        mock.patch(
            "campus_cli.auth.login.request_device_code", return_value=device_data
        ),
        mock.patch(
            "campus_cli.auth.login.poll_for_token", return_value=token_data
        ),
        mock.patch("campus_cli.auth.login.webbrowser.open"),
        mock.patch("campus_cli.auth.login.copy_to_clipboard"),
        mock.patch(
            "campus_cli.auth.login.create_login_session", return_value=None
        ),
    ):
        result = CliRunner().invoke(app, ["auth", "login"])
    assert result.exit_code == 0, result.output
    return creds


def test_login_records_scopes_and_principal():
    """The granted scopes and authorizing user are stored (#45)."""
    creds = _run_login_with_token_data({
        "access_token": "tok-123",
        "refresh_token": "refresh-123",
        "expires_in": 3600,
        "scope": "read clients:write",
        "user_id": "user-alice@example.com",
    })

    creds.set_token_scopes.assert_called_once_with(["read", "clients:write"])
    creds.set_token_user_id.assert_called_once_with("user-alice@example.com")
    creds.set_token_auth_url.assert_called_once()


def test_login_without_scope_response_records_neither():
    """Older servers that omit scope/user_id store neither (#45)."""
    creds = _run_login_with_token_data({
        "access_token": "tok-123",
        "refresh_token": "refresh-123",
        "expires_in": 3600,
    })

    creds.set_token_scopes.assert_not_called()
    creds.set_token_user_id.assert_not_called()
