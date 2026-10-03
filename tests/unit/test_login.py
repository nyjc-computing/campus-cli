"""Unit tests for the login module's device-code error handling."""

from unittest import mock

import pytest
import requests

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


def test_revoke_token_sends_rfc7009_payload_and_reports_success():
    """A 200 response confirms revocation and the payload follows RFC 7009."""
    response = mock.Mock(spec=requests.Response, status_code=200)
    with mock.patch(
        "campus_cli.auth.common.requests.post", return_value=response
    ) as mock_post:
        assert revoke_token("tok-123", "refresh_token") is True

    mock_post.assert_called_once()
    assert mock_post.call_args.kwargs["data"] == {
        "token": "tok-123",
        "token_type_hint": "refresh_token",
        "client_id": "guest",
    }


def test_revoke_token_reports_failure_on_http_error():
    """Non-200 responses (e.g. endpoint not deployed) mean not revoked."""
    response = mock.Mock(spec=requests.Response, status_code=404)
    with mock.patch(
        "campus_cli.auth.common.requests.post", return_value=response
    ):
        assert revoke_token("tok-123", "access_token") is False


def test_revoke_token_reports_failure_on_network_error():
    """Network errors degrade to False instead of raising from logout."""
    with mock.patch(
        "campus_cli.auth.common.requests.post",
        side_effect=requests.ConnectionError("connection refused"),
    ):
        assert revoke_token("tok-123", "refresh_token") is False


def test_revoke_token_targets_issuing_endpoint_when_given():
    """auth_url overrides the current target for the revocation request."""
    response = mock.Mock(spec=requests.Response, status_code=200)
    with mock.patch(
        "campus_cli.auth.common.requests.post", return_value=response
    ) as mock_post:
        assert revoke_token(
            "tok-123",
            "access_token",
            auth_url="https://auth-old.example.com/auth/v1",
        ) is True

    assert mock_post.call_args.args[0] == (
        "https://auth-old.example.com/auth/v1/oauth/revoke"
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
