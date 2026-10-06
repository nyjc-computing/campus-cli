"""Unit tests for the CLI device lane (#837).

The CLI presents a stable, config-persisted device id: minted once per
install, passed at login-session creation, revoked on logout, and set
as a default header on API calls (X-Campus-Device) so server-side
spans attribute to this device.
"""

import json
from unittest import mock

import pytest
import requests

from campus_cli.auth.login import create_login_session, delete_login_session
from campus_cli.config import Config


@pytest.fixture
def temp_config(tmp_path):
    """Create a temporary config file for testing."""
    config_path = tmp_path / "config.json"
    return Config(config_path=config_path)


class TestDeviceId:
    """config.get_device_id() mints once and persists."""

    def test_mints_uid_device_shaped_id(self, temp_config):
        device_id = temp_config.get_device_id()
        assert device_id.startswith("uid-device-")

    def test_persists_across_config_reloads(self, tmp_path):
        config_path = tmp_path / "config.json"
        first = Config(config_path=config_path).get_device_id()
        second = Config(config_path=config_path).get_device_id()
        assert first == second

    def test_minted_id_written_to_config_file(self, temp_config, tmp_path):
        device_id = temp_config.get_device_id()
        on_disk = json.loads(
            (tmp_path / "config.json").read_text(encoding="utf-8")
        )
        assert on_disk["device_id"] == device_id


class TestCreateLoginSession:
    """create_login_session posts the device-attributed login record."""

    def test_posts_device_id_and_returns_session_id(self):
        response = mock.Mock(spec=requests.Response)
        response.status_code = 200
        response.json.return_value = {"id": "uid-campus-login_session-abc"}
        with mock.patch(
            "campus_cli.auth.login.requests.post", return_value=response
        ) as posted, mock.patch(
            "campus_cli.auth.login.config"
        ) as config:
            config.get_device_id.return_value = "uid-device-cli42"
            session_id = create_login_session(
                "https://auth.example.com/auth/v1", "user@nyjc.edu.sg"
            )

        assert session_id == "uid-campus-login_session-abc"
        kwargs = posted.call_args.kwargs
        assert kwargs["json"]["device_id"] == "uid-device-cli42"
        assert kwargs["json"]["user_id"] == "user@nyjc.edu.sg"
        assert kwargs["json"]["client_id"] == "guest"
        assert "campus-cli/" in kwargs["json"]["agent_string"]
        assert posted.call_args.args[0] == (
            "https://auth.example.com/auth/v1/logins/"
        )

    def test_network_failure_returns_none(self):
        with mock.patch(
            "campus_cli.auth.login.requests.post",
            side_effect=requests.ConnectionError("refused"),
        ):
            session_id = create_login_session(
                "https://auth.example.com/auth/v1", "user@nyjc.edu.sg"
            )
        assert session_id is None

    def test_http_error_returns_none(self):
        response = mock.Mock(spec=requests.Response)
        response.status_code = 404
        response.raise_for_status.side_effect = requests.HTTPError(
            "404", response=response
        )
        with mock.patch(
            "campus_cli.auth.login.requests.post", return_value=response
        ):
            session_id = create_login_session(
                "https://auth.example.com/auth/v1", "user@nyjc.edu.sg"
            )
        assert session_id is None


class TestDeleteLoginSession:
    """delete_login_session revokes via the bearer-owned path."""

    def test_returns_true_on_200(self):
        response = mock.Mock(spec=requests.Response)
        response.status_code = 200
        with mock.patch(
            "campus_cli.auth.login.requests.delete", return_value=response
        ) as dele:
            ok = delete_login_session(
                "https://auth.example.com/auth/v1",
                "uid-campus-login_session-abc",
                "token-1",
            )
        assert ok is True
        assert dele.call_args.args[0] == (
            "https://auth.example.com/auth/v1/logins/"
            "uid-campus-login_session-abc/"
        )
        assert dele.call_args.kwargs["headers"] == {
            "Authorization": "Bearer token-1"
        }

    def test_returns_false_on_error_status(self):
        response = mock.Mock(spec=requests.Response)
        response.status_code = 404
        with mock.patch(
            "campus_cli.auth.login.requests.delete", return_value=response
        ):
            ok = delete_login_session(
                "https://auth.example.com/auth/v1", "sess-1", "token-1"
            )
        assert ok is False

    def test_returns_false_on_network_error(self):
        with mock.patch(
            "campus_cli.auth.login.requests.delete",
            side_effect=requests.ConnectionError("refused"),
        ):
            ok = delete_login_session(
                "https://auth.example.com/auth/v1", "sess-1", "token-1"
            )
        assert ok is False


class TestCampusClientDeviceHeader:
    """CampusClient presents the device id on API and auth calls."""

    def test_sets_default_header_on_both_clients(self):
        from campus_cli.api import CampusClient

        campus = mock.MagicMock()
        with mock.patch(
            "campus_python.Campus", return_value=campus
        ), mock.patch("campus_cli.api.config") as config:
            config.get_device_id.return_value = "uid-device-cli42"
            client = CampusClient("token-1")
            _ = client.campus  # trigger the lazy Campus construction

        campus.api.client.set_default_header.assert_called_once_with(
            "X-Campus-Device", "uid-device-cli42"
        )
        campus.auth.client.set_default_header.assert_called_once_with(
            "X-Campus-Device", "uid-device-cli42"
        )
        campus.api.client.set_bearer_authorization.assert_called_once_with(
            "token-1"
        )
