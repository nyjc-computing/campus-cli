"""Unit tests for the login module's device-code error handling."""

from unittest import mock

import pytest
import requests

from campus_cli.auth.login import DeviceAuthError, request_device_code


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
