"""Integration tests for `campus client update` field handling (issue #15).

The command must forward only the fields the admin passed — including
--redirect-uri, which the API layer replaces wholesale — and reject a
call that would update nothing.
"""

from json import loads as json_loads
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from campus_cli.cli import app

runner = CliRunner()


def _updated_client(**overrides):
    """A client model as the API layer would return after an update."""
    fields = {
        "id": "uid-x",
        "name": "New Name",
        "description": "Updated description",
        "created_at": "2026-09-30T06:31:24+00:00",
        "permissions": {"campus.api": 1},
        "redirect_uris": [],
        "is_public": False,
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _invoke_update(args):
    """Run `campus client update` against a mocked API client."""
    api = MagicMock()
    api.auth_clients["uid-x"].update.return_value = _updated_client()
    with patch("campus_cli.auth.client.get_api_client", return_value=api):
        result = runner.invoke(app, ["client", "update", *args])
    return result, api


def test_update_requires_at_least_one_field():
    """With no field options, the command errors and calls nothing."""
    result, api = _invoke_update(["--client-id", "uid-x"])

    assert result.exit_code == 1
    assert "At least one of" in result.stderr
    api.auth_clients["uid-x"].update.assert_not_called()


def test_update_passes_redirect_uris_through():
    """--redirect-uri is forwarded as redirect_uris in given order."""
    result, api = _invoke_update([
        "--client-id", "uid-x",
        "--redirect-uri", "https://a/cb",
        "--redirect-uri", "http://localhost:8000/cb",
    ])

    assert result.exit_code == 0
    api.auth_clients["uid-x"].update.assert_called_once_with(
        redirect_uris=["https://a/cb", "http://localhost:8000/cb"]
    )


def test_update_combines_name_and_redirect_uris():
    """Multiple fields are forwarded together; absent ones are omitted."""
    result, api = _invoke_update([
        "--client-id", "uid-x",
        "--name", "New Name",
        "--redirect-uri", "https://a/cb",
    ])

    assert result.exit_code == 0
    api.auth_clients["uid-x"].update.assert_called_once_with(
        name="New Name", redirect_uris=["https://a/cb"]
    )


def test_update_json_output_includes_redirect_uris():
    """issue #21: update --json surfaces redirect_uris and is_public."""
    api = MagicMock()
    api.auth_clients["uid-x"].update.return_value = _updated_client(
        redirect_uris=["https://a/cb"]
    )
    with patch("campus_cli.auth.client.get_api_client", return_value=api):
        result = runner.invoke(app, [
            "client", "update", "--client-id", "uid-x",
            "--redirect-uri", "https://a/cb", "--json",
        ])

    assert result.exit_code == 0
    payload = json_loads(result.stdout)
    assert payload["redirect_uris"] == ["https://a/cb"]
    assert payload["is_public"] is False
